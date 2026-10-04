from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import zarr
from numcodecs import Blosc
from numcodecs import blosc

from .config import READABLE_RESULT_SCHEMAS, RESULT_SCHEMA_VERSION, SAMPLED_FIELDS, PipelineConfig, field_sampling, result_zarr_name
from .planning import Tile


def array_sha256(values: np.ndarray) -> str:
    canonical = np.ascontiguousarray(values)
    return hashlib.sha256(canonical.view(np.uint8)).hexdigest()


def compressor(cfg: PipelineConfig) -> Blosc:
    blosc.set_nthreads(cfg.compression_threads)
    return Blosc(
        cname="zstd",
        clevel=cfg.compression_level,
        shuffle=Blosc.BITSHUFFLE,
    )


class VelocityStore:
    def __init__(self, cfg: PipelineConfig, time_index: int):
        self.cfg = cfg
        self.time_index = time_index
        path = cfg.raw_store_path(time_index)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.root = zarr.open_group(str(path), mode="a")
        if cfg.variable == "pressure_gradient" and len(self.root.attrs):
            expected = {"dataset": cfg.dataset, "variable": cfg.variable,
                        "time_index": time_index, "physical_time": cfg.physical_time(time_index),
                        "grid_shape_xyz": list(cfg.grid_shape),
                        **cfg.acquisition_metadata}
            if any(self.root.attrs.get(k) != v for k, v in expected.items()):
                raise ValueError("pressure-gradient cache metadata differs from requested acquisition")
        self.root.attrs.update(
            {
                "dataset": cfg.dataset,
                "variable": cfg.variable,
                "time_index": time_index,
                "physical_time": cfg.physical_time(time_index),
                "axis_order": ["component", "z", "y", "x"],
                "components": getattr(cfg, "components", ["ux", "uy", "uz"]),
                "domain": "[0,2pi)^3",
                "periodic": [True, True, True],
                "grid_shape_xyz": list(cfg.grid_shape),
                "dtype": "float32",
            }
        )

        self.root.attrs.update(getattr(self.cfg, "acquisition_metadata", {}))

    def ensure_array(self):
        gx, gy, gz = self.cfg.grid_shape
        tx, ty, tz = self.cfg.tile_shape
        return self.root.require_dataset(
            self.cfg.variable,
            shape=(3, gz, gy, gx),
            chunks=(3, tz, ty, tx),
            dtype="<f4",
            fill_value=np.nan,
            compressor=compressor(self.cfg),
            overwrite=False,
        )

    @property
    def array(self):
        return self.root[self.cfg.variable]

    def write_tile(self, tile: Tile, values: np.ndarray) -> str:
        expected = (3, tile.nz, tile.ny, tile.nx)
        canonical = np.ascontiguousarray(values, dtype="<f4")
        if canonical.shape != expected:
            raise ValueError(f"tile {tile.key} shape {canonical.shape}, expected {expected}")
        if not np.all(np.isfinite(canonical)):
            raise ValueError(f"tile {tile.key} contains NaN or Inf")
        self.array[tile.store_slices] = canonical
        readback = np.ascontiguousarray(self.array[tile.store_slices], dtype="<f4")
        digest = array_sha256(canonical)
        if array_sha256(readback) != digest:
            raise IOError(f"tile {tile.key} failed write/read checksum")
        return digest

    def mark_validated(self, manifest_hash: str) -> None:
        self.root.attrs.update({"status": "validated", "manifest_hash": manifest_hash})


def create_result_group(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grid: float,
    *,
    overwrite: bool,
):
    staging = cfg.staging_result_path(time_index, sigma_grid)
    staging.mkdir(parents=True, exist_ok=True)
    path = staging / result_zarr_name(sigma_grid)
    root = zarr.open_group(str(path), mode="w" if overwrite else "a")
    nz, ny, nx = cfg.stored_shape_zyx("velocity_bar")
    cz, cy, cx = (min(64, nz), min(64, ny), min(64, nx))
    full_shape = cfg.full_shape_zyx
    spatial_chunks = tuple(min(64, size) for size in full_shape)
    codec = compressor(cfg)
    root.attrs.update(
        {
            "status": "computing",
            "dataset": cfg.dataset,
            "time_index": time_index,
            "physical_time": cfg.physical_time(time_index),
            "sigma_grid": float(sigma_grid),
            "filter_type": cfg.filter_type,
            "sharp_edge_width_fraction": (
                cfg.sharp_edge_width_fraction
                if cfg.filter_type == "smooth_sharp"
                else None
            ),
            "axis_order": ["component", "z", "y", "x"],
            "gradient_axis_order": [
                "velocity_component", "derivative_component", "z", "y", "x"
            ],
            "components": ["ux", "uy", "uz"],
            "derivative_components": ["x", "y", "z"],
            "full_shape_xyz": list(cfg.grid_shape),
            "field_sampling": cfg.field_sampling,
            "field_scopes": {
                "velocity": "full_domain",
                "gradient": "full_domain_stride2",
                "velocity_bar": "full_domain_stride2",
                "gradient_bar": "full_domain_stride2",
                "regime": "full_domain",
                "work_full": "full_domain",
                "work_resolved": "full_domain",
                "pi": "full_domain",
                "s_bar": "full_domain",
            },
        }
    )
    root.require_dataset(
        "velocity_bar", shape=(3, nz, ny, nx), chunks=(1, cz, cy, cx),
        dtype="<f4", compressor=codec, fill_value=np.nan,
    )
    root.require_dataset(
        "gradient_bar", shape=(3, 3, nz, ny, nx), chunks=(1, 1, cz, cy, cx),
        dtype="<f4", compressor=codec, fill_value=np.nan,
    )
    for name in ("work_full", "work_resolved", "pi", "s_bar"):
        root.require_dataset(
            name,
            shape=full_shape,
            chunks=spatial_chunks,
            dtype="<f4", compressor=codec, fill_value=np.nan,
        )
    root.require_dataset(
        "regime", shape=full_shape, chunks=spatial_chunks,
        dtype="u1", compressor=codec, fill_value=0,
    )
    return root


def create_shared_gradient_group(
    cfg: PipelineConfig,
    time_index: int,
    *,
    staging: bool,
    overwrite: bool,
):
    directory = (
        cfg.shared_staging_result_path(time_index)
        if staging
        else cfg.shared_result_path(time_index)
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "sampled_raw.zarr"
    root = zarr.open_group(str(path), mode="w" if overwrite else "a")
    nz, ny, nx = cfg.stored_shape_zyx("gradient")
    chunks = (1, 1, min(64, nz), min(64, ny), min(64, nx))
    root.attrs.update(
        {
            "status": "computing",
            "dataset": cfg.dataset,
            "time_index": time_index,
            "physical_time": cfg.physical_time(time_index),
            "full_shape_xyz": list(cfg.grid_shape),
            "field_scopes": {"gradient": "full_domain_stride2"},
            "field_sampling": {"gradient": cfg.field_sampling["gradient"]},
            "gradient_axis_order": [
                "velocity_component", "derivative_component", "z", "y", "x"
            ],
        }
    )
    root.require_dataset(
        "gradient",
        shape=(3, 3, nz, ny, nx),
        chunks=chunks,
        dtype="<f4",
        compressor=compressor(cfg),
        fill_value=np.nan,
    )
    return root


class CompositeResult:
    """Read-only logical result joining per-sigma and shared arrays."""

    def __init__(self, root: Any, shared: dict[str, Any]):
        self.root = root
        self.shared = shared
        self.attrs = root.attrs

    def __contains__(self, name: str) -> bool:
        return name in self.shared or name in self.root

    def __getitem__(self, name: str) -> Any:
        if name in self.shared:
            return self.shared[name]
        return self.root[name]

    def __iter__(self):
        return iter(dict.fromkeys([*self.shared, *self.root.array_keys()]))

    def keys(self):
        return list(iter(self))

    def array_keys(self):
        return iter(self.keys())


def chunk_count(shape: tuple[int, ...], chunks: tuple[int, ...]) -> int:
    """Number of chunks, including a partial chunk at each boundary."""
    counts = [(size + chunk - 1) // chunk for size, chunk in zip(shape, chunks)]
    return int(np.prod(counts, dtype=np.int64))


def report_summary(
    report: dict[str, Any], report_hash: str, **details: Any
) -> dict[str, Any]:
    """Common QA summary fields, followed by report-specific metrics."""
    return {
        "passed": report["passed"],
        "scope": report["scope"],
        "report_version": report["report_version"],
        "report_hash": report_hash,
        **details,
    }


def report_metadata(
    name: str, report: dict[str, Any], report_hash: str
) -> dict[str, Any]:
    """Prefixed report fields shared by result manifests and Zarr attributes."""
    return {
        f"{name}_passed": report["passed"],
        f"{name}_report_version": report["report_version"],
        f"{name}_report_hash": report_hash,
    }


def load_chained_report(
    result_dir: Path, root: Any, name: str, version: int, *, html_name: str | None = None,
) -> dict[str, Any] | None:
    """Read a QA report only when its version and complete hash chain match."""
    report_path = result_dir / f"{name}.json"
    manifest_path = result_dir / "manifest.json"
    complete_path = result_dir / "COMPLETE"
    html_path = result_dir / (html_name or f"{name}.html")
    if not all(path.is_file() for path in (report_path, html_path, manifest_path, complete_path)):
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        complete = json.loads(complete_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    valid = (
        report.get("report_version") == version
        and report.get("scope") == "full_domain"
        and manifest.get(f"{name}_report_version") == version
        and manifest.get(f"{name}_report_hash") == report_hash
        and root.attrs.get(f"{name}_report_version") == version
        and root.attrs.get(f"{name}_report_hash") == report_hash
        and root.attrs.get("manifest_hash") == manifest_hash
        and complete.get("manifest_hash") == manifest_hash
    )
    return report if valid else None


def spatial_slices(shape: tuple[int, ...], chunk_shape: tuple[int, ...]) -> Iterator[tuple[slice, ...]]:
    if len(shape) != len(chunk_shape):
        raise ValueError("shape and chunk_shape ranks differ")

    def walk(axis: int, prefix: tuple[slice, ...]):
        if axis == len(shape):
            yield prefix
            return
        for start in range(0, shape[axis], chunk_shape[axis]):
            stop = min(start + chunk_shape[axis], shape[axis])
            yield from walk(axis + 1, prefix + (slice(start, stop),))

    yield from walk(0, ())


def hash_zarr_array(array: Any) -> tuple[str, int, float, float]:
    hasher = hashlib.sha256()
    byte_count = 0
    minimum = float("inf")
    maximum = float("-inf")
    for key in spatial_slices(tuple(array.shape), tuple(array.chunks)):
        values = np.ascontiguousarray(array[key])
        if not np.all(np.isfinite(values)):
            raise ValueError("result array contains NaN or Inf")
        hasher.update(values.view(np.uint8))
        byte_count += values.nbytes
        minimum = min(minimum, float(values.min()))
        maximum = max(maximum, float(values.max()))
    return hasher.hexdigest(), byte_count, minimum, maximum


def array_metadata(array: Any) -> dict[str, Any]:
    """Full chunk-streamed hash, shape, storage format and finite-value bounds."""
    digest, byte_count, minimum, maximum = hash_zarr_array(array)
    return {
        "shape": list(array.shape),
        "dtype": str(np.dtype(array.dtype)),
        "chunks": list(array.chunks),
        "sha256": digest,
        "byte_count": byte_count,
        "minimum": minimum,
        "maximum": maximum,
    }


def open_complete_result(path: Path):
    if not (path / "COMPLETE").is_file():
        raise RuntimeError(f"result is not complete: {path}")
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    schema = manifest.get("schema_version")
    if schema not in READABLE_RESULT_SCHEMAS:
        raise RuntimeError("result requires schema v7 or v8; rebuild from validated velocity")
    root = zarr.open_group(str(path / result_zarr_name(float(manifest["sigma_grid"]))), mode="r")
    if root.attrs.get("status") != "complete" or root.attrs.get("result_schema_version") != schema:
        raise RuntimeError(f"result metadata is incomplete or outdated: {path}")
    references = json.loads((path / "shared_refs.json").read_text(encoding="utf-8"))
    shared_path = Path(references["shared_gradient_store"])
    if not Path(references["shared_complete"]).is_file():
        raise RuntimeError(f"shared full-domain data is not complete: {shared_path}")
    raw_root = zarr.open_group(str(references["velocity_store"]), mode="r")
    shared_root = zarr.open_group(str(shared_path), mode="r")
    reference_hash = references.get("input_manifest_hash")
    if (
        not reference_hash
        or root.attrs.get("input_manifest_hash") != reference_hash
        or raw_root.attrs.get("manifest_hash") != reference_hash
        or shared_root.attrs.get("input_manifest_hash") != reference_hash
        or shared_root.attrs.get("status") != "complete"
        or shared_root.attrs.get("result_schema_version") != schema
    ):
        raise RuntimeError("result and shared inputs have different or incomplete metadata")
    result = CompositeResult(root, {"velocity": raw_root["velocity"], "gradient": shared_root["gradient"]})
    sampling = field_sampling(manifest["full_shape_xyz"], schema)
    if schema == 8 and (
        manifest.get("field_sampling") != sampling
        or root.attrs.get("field_sampling") != sampling
        or shared_root.attrs.get("field_sampling") != {"gradient": sampling["gradient"]}
    ):
        raise RuntimeError("result sampling metadata does not match the original grid")
    for name in ("velocity", "gradient", "velocity_bar", "gradient_bar", "work_full", "work_resolved", "pi", "s_bar", "regime"):
        if name not in result:
            raise RuntimeError(f"result field is missing: {name}")
        prefix = (3, 3) if name in ("gradient", "gradient_bar") else (3,) if name in ("velocity", "velocity_bar") else ()
        shape = tuple(reversed(sampling[name]["shape_xyz"]))
        if tuple(result[name].shape) != prefix + shape:
            raise RuntimeError(f"result field has an unexpected storage shape: {name}")
    return result
