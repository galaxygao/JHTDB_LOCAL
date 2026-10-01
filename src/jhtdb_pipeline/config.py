from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


RESULT_SCHEMA_VERSION = 6
FILTER_TYPES = ("gaussian", "smooth_sharp")


def _tuple3(value: Any, name: str) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError(f"{name} must contain exactly three integers")
    result = tuple(int(item) for item in value)
    if any(item <= 0 for item in result):
        raise ValueError(f"{name} values must be positive")
    return result


def _path(value: Any, name: str) -> Path:
    text = os.path.expandvars(str(value)).strip()
    if not text or "<username>" in text:
        raise ValueError(f"{name} must be configured")
    return Path(text)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    return value


def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], name: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ValueError(f"unknown {name} fields: {', '.join(unknown)}")


def sigma_tag(value: float) -> str:
    return format(float(value), ".8g").replace("-", "m").replace(".", "p")


def result_zarr_name(sigma_grid: float) -> str:
    return f"center_result_sigma_{sigma_tag(sigma_grid)}.zarr"


def _sigma_values(value: Any) -> tuple[float, ...]:
    items = value if isinstance(value, (list, tuple)) else (value,)
    if not items:
        raise ValueError("physics.sigma_grid must contain at least one value")
    result = tuple(float(item) for item in items)
    if any(not math.isfinite(item) or item <= 0 for item in result):
        raise ValueError("physics.sigma_grid values must be finite and positive")
    if len(set(result)) != len(result):
        raise ValueError("physics.sigma_grid values must be unique")
    if len({sigma_tag(item) for item in result}) != len(result):
        raise ValueError("physics.sigma_grid values must have unique result tags")
    return result


@dataclass(frozen=True)
class PipelineConfig:
    dataset: str
    variable: str
    grid_shape: tuple[int, int, int]
    domain_length: float
    stored_time_step: float
    state_root: Path
    run_root: Path
    result_root: Path
    token_file: Path | None
    request_shape: tuple[int, int, int]
    tile_shape: tuple[int, int, int]
    retries: int
    backoff_seconds: float
    request_cooldown_seconds: float
    compression_level: int
    compression_threads: int
    persistent_safety_reserve_gib: float
    scratch_safety_reserve_gib: float
    crop_start: tuple[int, int, int]
    crop_shape: tuple[int, int, int]
    divergence_relative_rms_max: float
    divergence_relative_max_max: float
    energy_identity_relative_rms_max: float
    s_bar_vs_pi_net_max: float
    cq_partition_relative_max: float
    sigma_grid: float
    epsilon_abs: float
    epsilon_rel: float
    fft_workers: int
    fft_slab_width: int
    cleanup_scratch_on_success: bool
    sigma_grids: tuple[float, ...]
    filter_type: str
    sharp_edge_width_fraction: float

    @property
    def sharp_edge_tag(self) -> str:
        return f"a{sigma_tag(self.sharp_edge_width_fraction)}kc"

    @property
    def catalog_path(self) -> Path:
        return self.state_root / "catalog.sqlite"

    @property
    def manifest_path(self) -> Path:
        return self.state_root / "manifests"

    @property
    def qa_path(self) -> Path:
        return self.state_root / "qa"

    @property
    def lock_path(self) -> Path:
        return self.state_root / "locks"

    def run_path(self, time_index: int) -> Path:
        self.physical_time(time_index)
        return self.run_root / f"t{time_index:06d}"

    def legacy_raw_store_path(self, time_index: int) -> Path:
        return self.run_path(time_index) / "velocity_cache.zarr"

    def persistent_input_path(self, time_index: int) -> Path:
        self.physical_time(time_index)
        return self.state_root / "inputs" / f"t{time_index:06d}"

    def persistent_raw_store_path(self, time_index: int) -> Path:
        return self.persistent_input_path(time_index) / "velocity_cache.zarr"

    def raw_store_path(self, time_index: int) -> Path:
        persistent = self.persistent_raw_store_path(time_index)
        legacy = self.legacy_raw_store_path(time_index)
        if persistent.is_dir() or not legacy.is_dir():
            return persistent
        return legacy

    def strain_store_path(self, time_index: int) -> Path:
        """Per-frame, filter-independent full-domain S_ij S_ij cache."""
        return self.persistent_input_path(time_index) / "strain_cache.zarr"

    def workspace_path(self, time_index: int, sigma_grid: float | None = None) -> Path:
        sigma = self.sigma_grid if sigma_grid is None else sigma_grid
        filter_tag = (
            ""
            if self.filter_type == "gaussian"
            else f"_{self.filter_type}_{self.sharp_edge_tag}"
        )
        return self.run_path(time_index) / f"work{filter_tag}_sigma_{sigma_tag(sigma)}"

    def result_id(self, time_index: int, sigma_grid: float | None = None) -> str:
        sigma = self.sigma_grid if sigma_grid is None else sigma_grid
        if self.filter_type == "gaussian":
            return f"t{time_index:06d}_sigma_{sigma_tag(sigma)}"
        return (
            f"t{time_index:06d}_filter_{self.filter_type}"
            f"_{self.sharp_edge_tag}_sigma_{sigma_tag(sigma)}"
        )

    def staging_result_path(self, time_index: int, sigma_grid: float | None = None) -> Path:
        return self.result_root / ".staging" / self.result_id(time_index, sigma_grid)

    def result_path(self, time_index: int, sigma_grid: float | None = None) -> Path:
        return self.result_root / self.result_id(time_index, sigma_grid)

    def batch_manifest_path(self, time_index: int) -> Path:
        self.physical_time(time_index)
        if self.filter_type == "gaussian":
            return self.result_root / (
                f"t{time_index:06d}_filter_gaussian_batch_manifest.json"
            )
        return self.result_root / (
            f"t{time_index:06d}_filter_{self.filter_type}"
            f"_{self.sharp_edge_tag}_batch_manifest.json"
        )

    def shared_result_path(self, time_index: int) -> Path:
        self.physical_time(time_index)
        return self.result_root / f"t{time_index:06d}_shared"

    def shared_staging_result_path(self, time_index: int) -> Path:
        self.physical_time(time_index)
        return self.result_root / ".staging" / f"t{time_index:06d}_shared"

    def shared_center_store_path(self, time_index: int) -> Path:
        return self.shared_result_path(time_index) / "center_raw.zarr"

    @property
    def crop_slices_zyx(self) -> tuple[slice, slice, slice]:
        x0, y0, z0 = self.crop_start
        nx, ny, nz = self.crop_shape
        return (
            slice(z0, z0 + nz),
            slice(y0, y0 + ny),
            slice(x0, x0 + nx),
        )

    @property
    def result_shape_zyx(self) -> tuple[int, int, int]:
        nx, ny, nz = self.crop_shape
        return nz, ny, nx

    @property
    def full_shape_zyx(self) -> tuple[int, int, int]:
        nx, ny, nz = self.grid_shape
        return nz, ny, nx

    @property
    def bytes_per_snapshot(self) -> int:
        nx, ny, nz = self.grid_shape
        return nx * ny * nz * 3 * 4

    @property
    def result_uncompressed_bytes(self) -> int:
        center_points = int(self.crop_shape[0] * self.crop_shape[1] * self.crop_shape[2])
        full_points = int(self.grid_shape[0] * self.grid_shape[1] * self.grid_shape[2])
        # Per-sigma v6 results retain only sigma-dependent center fields.
        center_fields = center_points * (3 + 9) * 4
        full_fields = full_points * (4 * 4 + 1)
        return center_fields + full_fields

    @property
    def shared_center_uncompressed_bytes(self) -> int:
        center_points = int(self.crop_shape[0] * self.crop_shape[1] * self.crop_shape[2])
        return center_points * 9 * 4

    def physical_time(self, time_index: int) -> float:
        if time_index < 1:
            raise ValueError("JHTDB cutout time_index must be >= 1")
        return (time_index - 1) * self.stored_time_step

    def with_sigma(self, sigma_grid: float) -> "PipelineConfig":
        from dataclasses import replace

        if not math.isfinite(sigma_grid) or sigma_grid <= 0:
            raise ValueError("sigma_grid must be positive")
        sigma = float(sigma_grid)
        return replace(self, sigma_grid=sigma, sigma_grids=(sigma,))

    def with_filter(self, filter_type: str) -> "PipelineConfig":
        from dataclasses import replace

        value = str(filter_type).strip().lower().replace("-", "_")
        if value not in FILTER_TYPES:
            raise ValueError(f"filter_type must be one of: {', '.join(FILTER_TYPES)}")
        return replace(self, filter_type=value)

    def with_sharp_edge_width_fraction(self, fraction: float) -> "PipelineConfig":
        from dataclasses import replace

        value = float(fraction)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("sharp edge width fraction must be finite and positive")
        return replace(self, sharp_edge_width_fraction=value)

    def validate(self) -> None:
        if self.dataset != "isotropic1024coarse":
            raise ValueError("only isotropic1024coarse is supported")
        if self.variable != "velocity":
            raise ValueError("only velocity may be fetched")
        if self.grid_shape != (1024, 1024, 1024):
            raise ValueError("isotropic1024coarse must use the complete 1024^3 grid")
        if any(n % tile != 0 for n, tile in zip(self.grid_shape, self.tile_shape)):
            raise ValueError("tile_shape must divide grid_shape exactly")
        if any(n % size != 0 for n, size in zip(self.grid_shape, self.request_shape)):
            raise ValueError("request_shape must divide grid_shape exactly")
        if any(size % tile != 0 for size, tile in zip(self.request_shape, self.tile_shape)):
            raise ValueError("request_shape must be an integer multiple of tile_shape")
        if self.tile_shape != (128, 128, 128):
            raise ValueError("the local store requires 128^3 checksum tiles")
        request_bytes = math.prod(self.request_shape) * 3 * 4
        if request_bytes > 100 * 1024**2:
            raise ValueError(
                "local request blocks must contain at most 100 MiB of velocity data"
            )
        if self.retries < 1 or self.backoff_seconds < 0 or self.request_cooldown_seconds < 0:
            raise ValueError("JHTDB retry settings are invalid")
        if not 0 <= self.compression_level <= 9:
            raise ValueError("compression_level must be between 0 and 9")
        if self.compression_threads < 1:
            raise ValueError("compression_threads must be positive")
        if self.persistent_safety_reserve_gib < 0 or self.scratch_safety_reserve_gib < 0:
            raise ValueError("storage safety reserves cannot be negative")
        for start, size, full in zip(self.crop_start, self.crop_shape, self.grid_shape):
            if start < 0 or start + size > full:
                raise ValueError("crop lies outside the complete periodic grid")
        if self.crop_start != (256, 256, 256) or self.crop_shape != (512, 512, 512):
            raise ValueError("the production crop must be [256:768)^3")
        if self.divergence_relative_rms_max <= 0 or self.divergence_relative_max_max <= 0:
            raise ValueError("divergence tolerances must be positive")
        if (
            self.energy_identity_relative_rms_max <= 0
            or self.s_bar_vs_pi_net_max <= 0
            or self.cq_partition_relative_max <= 0
        ):
            raise ValueError("energy QA tolerances must be positive")
        if (
            not self.sigma_grids
            or self.sigma_grid != self.sigma_grids[0]
            or any(not math.isfinite(item) or item <= 0 for item in self.sigma_grids)
            or len(set(self.sigma_grids)) != len(self.sigma_grids)
            or len({sigma_tag(item) for item in self.sigma_grids}) != len(self.sigma_grids)
            or self.epsilon_abs < 0
            or self.epsilon_rel < 0
        ):
            raise ValueError("physics parameters are invalid")
        if self.fft_workers < 1 or self.fft_slab_width < 1:
            raise ValueError("fft_workers and fft_slab_width must be positive")
        if self.filter_type not in FILTER_TYPES:
            raise ValueError(f"filter_type must be one of: {', '.join(FILTER_TYPES)}")
        if (
            not math.isfinite(self.sharp_edge_width_fraction)
            or self.sharp_edge_width_fraction <= 0
        ):
            raise ValueError("sharp_edge_width_fraction must be finite and positive")


def load_config(path: str | Path) -> PipelineConfig:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, Mapping):
        raise ValueError("configuration root must be a mapping")

    allowed_top = {
        "dataset", "variable", "grid_shape", "domain_length", "stored_time_step",
        "platform", "auth", "jhtdb", "storage", "validation", "physics",
    }
    _reject_unknown(data, allowed_top, "top-level")
    platform = _mapping(data.get("platform"), "platform")
    auth = _mapping(data.get("auth"), "auth")
    jhtdb = _mapping(data.get("jhtdb"), "jhtdb")
    storage = _mapping(data.get("storage"), "storage")
    validation = _mapping(data.get("validation"), "validation")
    physics = _mapping(data.get("physics"), "physics")
    _reject_unknown(platform, {"state_root", "run_root", "result_root"}, "platform")
    _reject_unknown(auth, {"token_file"}, "auth")
    _reject_unknown(jhtdb, {"request_shape", "tile_shape", "retries", "backoff_seconds", "request_cooldown_seconds"}, "jhtdb")
    _reject_unknown(storage, {"compression_level", "compression_threads", "persistent_safety_reserve_gib", "scratch_safety_reserve_gib"}, "storage")
    _reject_unknown(validation, {"divergence_relative_rms_max", "divergence_relative_max_max", "energy_identity_relative_rms_max", "s_bar_vs_pi_net_max", "cq_partition_relative_max"}, "validation")
    _reject_unknown(physics, {"sigma_grid", "filter_type", "sharp_edge_width_fraction", "crop_start", "crop_shape", "epsilon_abs", "epsilon_rel", "fft_workers", "fft_slab_width", "cleanup_scratch_on_success"}, "physics")

    token_value = auth.get("token_file")
    sigma_grids = _sigma_values(physics.get("sigma_grid", 1.0))
    cfg = PipelineConfig(
        dataset=str(data.get("dataset", "isotropic1024coarse")),
        variable=str(data.get("variable", "velocity")),
        grid_shape=_tuple3(data.get("grid_shape", [1024, 1024, 1024]), "grid_shape"),
        domain_length=float(data.get("domain_length", 2.0 * 3.141592653589793)),
        stored_time_step=float(data.get("stored_time_step", 0.002)),
        state_root=_path(platform.get("state_root", ""), "platform.state_root"),
        run_root=_path(platform.get("run_root", ""), "platform.run_root"),
        result_root=_path(platform.get("result_root", ""), "platform.result_root"),
        token_file=_path(token_value, "auth.token_file") if token_value else None,
        request_shape=_tuple3(jhtdb.get("request_shape", [256, 256, 128]), "jhtdb.request_shape"),
        tile_shape=_tuple3(jhtdb.get("tile_shape", [128, 128, 128]), "jhtdb.tile_shape"),
        retries=int(jhtdb.get("retries", 5)),
        backoff_seconds=float(jhtdb.get("backoff_seconds", 2.0)),
        request_cooldown_seconds=float(jhtdb.get("request_cooldown_seconds", 0.25)),
        compression_level=int(storage.get("compression_level", 3)),
        compression_threads=int(storage.get("compression_threads", 8)),
        persistent_safety_reserve_gib=float(storage.get("persistent_safety_reserve_gib", 15.0)),
        scratch_safety_reserve_gib=float(storage.get("scratch_safety_reserve_gib", 16.0)),
        crop_start=_tuple3(physics.get("crop_start", [256, 256, 256]), "physics.crop_start"),
        crop_shape=_tuple3(physics.get("crop_shape", [512, 512, 512]), "physics.crop_shape"),
        divergence_relative_rms_max=float(validation.get("divergence_relative_rms_max", 1.0e-4)),
        divergence_relative_max_max=float(validation.get("divergence_relative_max_max", 1.0e-3)),
        energy_identity_relative_rms_max=float(validation.get("energy_identity_relative_rms_max", 1.0e-4)),
        s_bar_vs_pi_net_max=float(validation.get("s_bar_vs_pi_net_max", 1.0e-2)),
        cq_partition_relative_max=float(validation.get("cq_partition_relative_max", 1.0e-12)),
        sigma_grid=sigma_grids[0],
        epsilon_abs=float(physics.get("epsilon_abs", 0.0)),
        epsilon_rel=float(physics.get("epsilon_rel", 0.001)),
        fft_workers=int(physics.get("fft_workers", 16)),
        fft_slab_width=int(physics.get("fft_slab_width", 32)),
        cleanup_scratch_on_success=bool(physics.get("cleanup_scratch_on_success", True)),
        sigma_grids=sigma_grids,
        filter_type=str(physics.get("filter_type", "gaussian")).strip().lower().replace("-", "_"),
        sharp_edge_width_fraction=float(
            physics.get("sharp_edge_width_fraction", 0.1171875)
        ),
    )
    cfg.validate()
    return cfg
