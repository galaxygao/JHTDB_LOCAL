from __future__ import annotations

import json
import os
import shutil

from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .config import RESULT_SCHEMA_VERSION, PipelineConfig, result_zarr_name
from .disk_fft import build_spectrum, filter_spectrum, mapped_array, release_pages
from .cq import compute_cq, ensure_cq_result, write_cq_artifacts
from .physics import (
    ComponentView,
    ProductView,
    accumulate_product,
    axis2_spectrum,
    close_memmap,
    derivative_field,
    filter_field,
    filter_field_from_axis2_spectrum,
    filter_smooth_sharp_field,
    filter_smooth_sharp_from_spectrum,
    full_spectrum,
    regime_codes_from_thresholds,
    memmap,
    subtract_product,
    zero_field,
)
from .store import (
    create_result_group,
    create_shared_gradient_group,
    hash_zarr_array,
    open_complete_result,
)
from .sbar_qa import compute_sbar_qa, ensure_sbar_result, write_sbar_artifacts
from .validation import atomic_json, input_manifest_hash
from .weak_asymmetry import write_weak_asymmetry_artifacts


RESULT_FIELDS = {
    "velocity_bar": ("<f4", 4),
    "gradient_bar": ("<f4", 5),
    "work_full": ("<f4", 3),
    "work_resolved": ("<f4", 3),
    "pi": ("<f4", 3),
    "s_bar": ("<f4", 3),
    "regime": ("u1", 3),
}


def _sharp_edge_metadata(cfg: PipelineConfig, sigma: float) -> dict[str, Any]:
    if cfg.filter_type != "smooth_sharp":
        return {"sharp_edge_width_fraction": None}
    return {"sharp_edge_width_fraction": cfg.sharp_edge_width_fraction}


def _filter_metadata_matches(
    metadata: Any,
    cfg: PipelineConfig,
    sigma: float,
) -> bool:
    if str(metadata.get("filter_type", "gaussian")) != cfg.filter_type:
        return False
    if cfg.filter_type == "gaussian":
        return True
    try:
        actual_fraction = float(metadata.get("sharp_edge_width_fraction", -1.0))
    except (TypeError, ValueError):
        return False
    return bool(
        np.isclose(actual_fraction, cfg.sharp_edge_width_fraction, rtol=1e-12)
    )


def _filter_with_optional_spectrum(
    source: Any,
    destination: Any,
    temp_a: Any,
    temp_b: Any,
    sigma: float,
    cfg: PipelineConfig,
    spectra: dict[tuple[Any, ...], np.ndarray] | None,
    key: tuple[Any, ...],
) -> None:
    if cfg.filter_type == "smooth_sharp" and cfg.fft_cache_mode == "memmap":
        # temp_a is already a per-sigma disk workspace. Never allocate a full FFT in RAM.
        directory = Path(temp_a.filename).parent
        with TemporaryDirectory(prefix="fft-", dir=directory) as temporary:
            scratch = Path(temporary)
            cached = spectra.get(key) if spectra is not None else None
            owned = cached is None
            if owned:
                cached = build_spectrum(source, scratch / "source.c64", cfg.fft_slab_width,
                                        workers=cfg.fft_workers, full=True)
            try:
                filter_spectrum(cached, destination, scratch / "filtered.c64", sigma,
                                cfg.domain_length, cfg.sharp_edge_width_fraction,
                                cfg.fft_slab_width, workers=cfg.fft_workers)
            finally:
                release_pages(cached)
                if owned:
                    close_memmap(cached)
        return
    if cfg.filter_type == "smooth_sharp":
        if spectra is not None and key in spectra:
            filter_smooth_sharp_from_spectrum(
                spectra[key],
                destination,
                sigma,
                cfg.domain_length,
                cfg.sharp_edge_width_fraction,
                cfg.fft_slab_width,
                workers=cfg.fft_workers,
            )
        else:
            filter_smooth_sharp_field(
                source,
                destination,
                sigma,
                cfg.domain_length,
                cfg.sharp_edge_width_fraction,
                cfg.fft_slab_width,
                workers=cfg.fft_workers,
            )
        return
    if spectra is not None and key in spectra:
        filter_field_from_axis2_spectrum(
            spectra[key],
            destination,
            temp_a,
            temp_b,
            sigma,
            cfg.fft_slab_width,
            workers=cfg.fft_workers,
        )
        return
    filter_field(
        source,
        destination,
        temp_a,
        temp_b,
        sigma,
        cfg.fft_slab_width,
        workers=cfg.fft_workers,
    )


def _complete_result_schema(path: Path, sigma_grid: float) -> int | None:
    if not (path / "COMPLETE").is_file():
        return None
    zarr_path = path / result_zarr_name(sigma_grid)
    if not zarr_path.is_dir():
        return None
    try:
        root = zarr.open_group(str(zarr_path), mode="r")
        if root.attrs.get("status") != "complete" or any(
            name not in root for name in RESULT_FIELDS
        ):
            return None
        return int(root.attrs.get("result_schema_version"))
    except Exception:
        return None


def _complete_result_is_current(
    cfg: PipelineConfig, path: Path, sigma_grid: float
) -> bool:
    if _complete_result_schema(path, sigma_grid) != RESULT_SCHEMA_VERSION:
        return False
    try:
        root = open_complete_result(path)
        return (
            _filter_metadata_matches(root.attrs, cfg, sigma_grid)
            and root.attrs.get("input_manifest_hash") == input_manifest_hash(cfg, int(root.attrs["time_index"]))
            and
            tuple(root["velocity"].shape) == (3, *cfg.full_shape_zyx)
            and tuple(root["gradient"].shape) == (3, 3, *cfg.full_shape_zyx)
            and tuple(root["velocity_bar"].shape) == (3, *cfg.full_shape_zyx)
            and tuple(root["gradient_bar"].shape) == (3, 3, *cfg.full_shape_zyx)
            and all(
                tuple(root[name].shape) == cfg.full_shape_zyx
                for name in ("work_full", "work_resolved", "pi", "s_bar", "regime")
            )
        )
    except Exception:
        return False


def _shared_result_is_current(
    cfg: PipelineConfig, time_index: int, manifest_hash: str
) -> bool:
    directory = cfg.shared_result_path(time_index)
    manifest_path = directory / "shared_manifest.json"
    complete_path = directory / "COMPLETE"
    store_path = directory / "full_raw.zarr"
    if not manifest_path.is_file() or not complete_path.is_file() or not store_path.is_dir():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        root = zarr.open_group(str(store_path), mode="r")
        return (
            manifest.get("schema_version") == RESULT_SCHEMA_VERSION
            and manifest.get("status") == "complete"
            and manifest.get("input_manifest_hash") == manifest_hash
            and root.attrs.get("status") == "complete"
            and root.attrs.get("input_manifest_hash") == manifest_hash
            and tuple(root["gradient"].shape)
            == (3, 3, *cfg.full_shape_zyx)
            and np.dtype(root["gradient"].dtype) == np.dtype("<f4")
        )
    except Exception:
        return False


def _prepare_shared_gradient(
    cfg: PipelineConfig, time_index: int, manifest_hash: str
) -> tuple[Any, bool]:
    if _shared_result_is_current(cfg, time_index, manifest_hash):
        return (
            zarr.open_group(str(cfg.shared_gradient_store_path(time_index)), mode="r"),
            False,
        )
    staging = cfg.shared_staging_result_path(time_index)
    _safe_rmtree(staging, cfg.result_root / ".staging")
    root = create_shared_gradient_group(
        cfg, time_index, staging=True, overwrite=True
    )
    root.attrs["input_manifest_hash"] = manifest_hash
    return root, True


def _finalize_shared_gradient(
    cfg: PipelineConfig,
    time_index: int,
    manifest_hash: str,
    root: Any,
) -> Path:
    gradient = root["gradient"]
    digest, byte_count, minimum, maximum = hash_zarr_array(gradient)
    staging = cfg.shared_staging_result_path(time_index)
    final = cfg.shared_result_path(time_index)
    manifest = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "complete",
        "dataset": cfg.dataset,
        "time_index": time_index,
        "physical_time": cfg.physical_time(time_index),
        "input_manifest_hash": manifest_hash,
        "full_shape_xyz": list(cfg.grid_shape),
        "fields": {
            "gradient": {
                "shape": list(gradient.shape),
                "dtype": str(np.dtype(gradient.dtype)),
                "chunks": list(gradient.chunks),
                "sha256": digest,
                "byte_count": byte_count,
                "minimum": minimum,
                "maximum": maximum,
            }
        },
    }
    manifest_digest = atomic_json(staging / "shared_manifest.json", manifest)
    root.attrs.update(
        {
            "status": "complete",
            "result_schema_version": RESULT_SCHEMA_VERSION,
            "input_manifest_hash": manifest_hash,
            "manifest_hash": manifest_digest,
            "output_hashes": {"gradient": digest},
        }
    )
    if final.exists():
        if (final / "COMPLETE").is_file():
            if _shared_result_is_current(cfg, time_index, manifest_hash):
                _safe_rmtree(staging, cfg.result_root / ".staging")
                return final
            raise RuntimeError("refusing to replace a different complete shared result")
        _safe_rmtree(final, cfg.result_root)
    os.replace(staging, final)
    atomic_json(final / "COMPLETE", {"manifest_hash": manifest_digest})
    return final


def _shared_references(
    cfg: PipelineConfig, time_index: int, manifest_hash: str
) -> dict[str, Any]:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "time_index": time_index,
        "input_manifest_hash": manifest_hash,
        "velocity_store": str(cfg.raw_store_path(time_index).resolve()),
        "shared_gradient_store": str(cfg.shared_gradient_store_path(time_index).resolve()),
        "shared_complete": str((cfg.shared_result_path(time_index) / "COMPLETE").resolve()),


    }


def _safe_rmtree(path: Path, required_parent: Path) -> None:
    resolved = path.resolve(strict=False)
    parent = required_parent.resolve(strict=False)
    if resolved.parent != parent or resolved == parent:
        raise RuntimeError(f"refusing to remove unexpected path: {resolved}")
    if path.exists():
        shutil.rmtree(path)


def _spatial_keys(shape: tuple[int, int, int], chunks: tuple[int, int, int]) -> Iterator[tuple[slice, slice, slice]]:
    for z0 in range(0, shape[0], chunks[0]):
        for y0 in range(0, shape[1], chunks[1]):
            for x0 in range(0, shape[2], chunks[2]):
                yield (
                    slice(z0, min(z0 + chunks[0], shape[0])),
                    slice(y0, min(y0 + chunks[1], shape[1])),
                    slice(x0, min(x0 + chunks[2], shape[2])),
                )


def _copy_field(
    cfg: PipelineConfig,
    source: Any,
    destination: Any,
    prefix: tuple[int, ...] = (),
) -> None:
    shape = cfg.full_shape_zyx
    chunks = tuple(int(value) for value in destination.chunks[-3:])
    for relative in _spatial_keys(shape, chunks):
        values = np.ascontiguousarray(source[relative], dtype="<f4")
        if not np.all(np.isfinite(values)):
            raise ValueError("full field contains NaN or Inf")
        destination[prefix + relative] = values
        readback = np.asarray(destination[prefix + relative], dtype="<f4")
        if not np.array_equal(values, readback):
            raise IOError("persistent full field failed write/read verification")

    release_pages(source)


def _zero_zarr(array: Any) -> None:
    shape = tuple(int(value) for value in array.shape)
    chunks = tuple(int(value) for value in array.chunks)
    for key in _spatial_keys(shape, chunks):
        array[key] = np.zeros(tuple(item.stop - item.start for item in key), dtype=array.dtype)


def _accumulate_zarr(destination: Any, source: Any) -> None:
    shape = tuple(int(value) for value in destination.shape)
    chunks = tuple(int(value) for value in destination.chunks)
    for key in _spatial_keys(shape, chunks):
        current = np.asarray(destination[key], dtype=np.float32)
        values = np.asarray(source[key], dtype=np.float32)
        destination[key] = current + values


def _accumulate_zarr_product(destination: Any, left: Any, right: Any) -> None:
    shape = tuple(int(value) for value in destination.shape)
    chunks = tuple(int(value) for value in destination.chunks)
    for key in _spatial_keys(shape, chunks):
        current = np.asarray(destination[key], dtype=np.float32)
        left_values = np.asarray(left[key], dtype=np.float32)
        right_values = np.asarray(right[key], dtype=np.float32)
        destination[key] = current + left_values * right_values


def _copy_full(destination: Any, source: Any, slab: int) -> None:
    for start in range(0, destination.shape[0], slab):
        key = (
            slice(start, min(start + slab, destination.shape[0])),
            slice(None),
            slice(None),
        )
        destination[key] = np.asarray(source[key], dtype=np.float32)


def _accumulate_full(destination: Any, source: Any, slab: int) -> None:
    for start in range(0, destination.shape[0], slab):
        key = (
            slice(start, min(start + slab, destination.shape[0])),
            slice(None),
            slice(None),
        )
        destination[key] = np.asarray(
            destination[key], dtype=np.float32
        ) + np.asarray(source[key], dtype=np.float32)


def _field_statistics(field: Any, slab: int) -> tuple[float, float, int]:
    sumsq = 0.0
    maximum = 0.0
    count = 0
    for start in range(0, field.shape[0], slab):
        values = np.asarray(
            field[start : min(start + slab, field.shape[0]), :, :],
            dtype=np.float32,
        )
        if not np.all(np.isfinite(values)):
            raise ValueError("spectral workspace contains NaN or Inf")
        sumsq += float(np.square(values, dtype=np.float64).sum())
        maximum = max(maximum, float(np.max(np.abs(values))))
        count += values.size
    release_pages(field)
    return sumsq, maximum, count


def _divergence_metrics(
    cfg: PipelineConfig,
    divergence_sumsq: float,
    divergence_maximum: float,
    point_count: int,
    gradient_sumsq: float,
    gradient_maximum: float,
    gradient_count: int,
) -> dict[str, float | int | bool | str]:
    divergence_rms = float(np.sqrt(divergence_sumsq / point_count))
    gradient_rms = float(np.sqrt(gradient_sumsq / gradient_count))
    relative_rms = divergence_rms / max(gradient_rms, 1.0e-30)
    relative_maximum = divergence_maximum / max(gradient_maximum, 1.0e-30)
    return {
        "passed": (
            relative_rms <= cfg.divergence_relative_rms_max
            and relative_maximum <= cfg.divergence_relative_max_max
        ),
        "divergence_rms": divergence_rms,
        "gradient_rms": gradient_rms,
        "relative_divergence_rms": relative_rms,
        "maximum_abs_divergence": divergence_maximum,
        "maximum_abs_gradient_component": gradient_maximum,
        "relative_maximum_divergence": relative_maximum,
        "point_count": point_count,
    }


def _reusable_filtered_velocity(
    cfg: PipelineConfig,
    time_index: int,
    sigma: float,
    manifest_hash: str,
    expected_shape: tuple[int, ...],
) -> np.memmap | None:
    workspace = cfg.workspace_path(time_index, sigma)
    path = workspace / "filtered_velocity.f32"
    if not path.is_file() or path.stat().st_size != int(np.prod(expected_shape)) * 4:
        return None
    metadata_path = workspace / "filtered_velocity.json"
    trusted = False
    if metadata_path.is_file():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            trusted = (
                metadata.get("schema_version") == RESULT_SCHEMA_VERSION
                and metadata.get("status") == "complete"
                and metadata.get("input_manifest_hash") == manifest_hash
                and float(metadata.get("sigma_grid")) == sigma
                and _filter_metadata_matches(metadata, cfg, sigma)
                and tuple(metadata.get("shape", ())) == expected_shape
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            trusted = False
    mapped = memmap(path, expected_shape, mode="r+")
    if trusted:
        for component in range(3):
            _field_statistics(
                ComponentView(mapped, component), cfg.fft_slab_width
            )
        return mapped

    close_memmap(mapped)
    return None


def _write_full_regime(
    work_full: Any,
    work_resolved: Any,
    regime: Any,
    cfg: PipelineConfig,
) -> dict[str, Any]:
    expected = cfg.full_shape_zyx
    if (
        tuple(work_full.shape) != expected
        or tuple(work_resolved.shape) != expected
        or tuple(regime.shape) != expected
    ):
        raise RuntimeError("full-domain regime inputs and output must share the full shape")
    chunks = tuple(int(value) for value in regime.chunks)
    chunk_count = int(
        np.prod(
            [
                (size + chunk - 1) // chunk
                for size, chunk in zip(expected, chunks)
            ],
            dtype=np.int64,
        )
    )
    full_sumsq = 0.0
    resolved_sumsq = 0.0
    point_count = 0
    console = Console()
    with Progress(
        SpinnerColumn("line"),
        TextColumn("{task.description}"),
        BarColumn(),
        "{task.completed}/{task.total}",
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("full-domain regime", total=2 * chunk_count)
        for key in _spatial_keys(expected, chunks):
            full = np.asarray(work_full[key], dtype=np.float32)
            resolved = np.asarray(work_resolved[key], dtype=np.float32)
            if not np.all(np.isfinite(full)) or not np.all(np.isfinite(resolved)):
                raise ValueError("work fields contain NaN or Inf")
            full_sumsq += float(np.square(full, dtype=np.float64).sum())
            resolved_sumsq += float(np.square(resolved, dtype=np.float64).sum())
            point_count += full.size
            progress.advance(task)
        epsilon_full = max(
            cfg.epsilon_abs,
            cfg.epsilon_rel * float(np.sqrt(full_sumsq / point_count)),
        )
        epsilon_resolved = max(
            cfg.epsilon_abs,
            cfg.epsilon_rel * float(np.sqrt(resolved_sumsq / point_count)),
        )
        occupancy = np.zeros(7, dtype=np.int64)
        for key in _spatial_keys(expected, chunks):
            full = np.asarray(work_full[key], dtype=np.float32)
            resolved = np.asarray(work_resolved[key], dtype=np.float32)
            codes = regime_codes_from_thresholds(
                full, resolved, epsilon_full, epsilon_resolved
            )
            regime[key] = codes
            occupancy += np.bincount(codes.ravel(), minlength=7)
            progress.advance(task)
    labels = ("uncertain", "1+", "1-", "2", "3", "4+", "4-")
    occupancy_fraction = {
        label: float(value / point_count)
        for label, value in zip(labels, occupancy)
    }
    return {
        "scope": "full_domain",
        "point_count": point_count,
        "epsilon_full": float(epsilon_full),
        "epsilon_resolved": float(epsilon_resolved),
        "occupancy": occupancy_fraction,
    }


def resource_plan(cfg: PipelineConfig) -> dict[str, float | str]:
    full_points = int(np.prod(cfg.grid_shape, dtype=np.int64))
    scalar_bytes = full_points * 4
    raw_gradient_cache_bytes = 9 * scalar_bytes
    axis2_spectrum_bytes = (
        cfg.full_shape_zyx[0]
        * cfg.full_shape_zyx[1]
        * (cfg.full_shape_zyx[2] // 2 + 1)
        * 8
        * 12
    )
    # filtered velocity (3) + SGS transport (3) + derivative + acceleration
    # + two filter buffers.
    workspace_bytes = 10 * scalar_bytes
    mapped_cache_bytes = (raw_gradient_cache_bytes + axis2_spectrum_bytes
                          if cfg.fft_cache_mode == "memmap" else 0)
    mapped_extra_bytes = (2 * axis2_spectrum_bytes // 12 + scalar_bytes
                          if cfg.fft_cache_mode == "memmap" else 0)
    scratch_bytes = workspace_bytes + mapped_cache_bytes + mapped_extra_bytes
    batch_result_bytes = len(cfg.sigma_grids) * cfg.result_uncompressed_bytes
    shared_gradient_bytes = cfg.shared_gradient_uncompressed_bytes
    batch_persistent_bytes = (
        batch_result_bytes + shared_gradient_bytes + cfg.bytes_per_snapshot
    )
    return {
        "filter_type": cfg.filter_type,
        "fft_cache_mode": cfg.fft_cache_mode,
        "memory_note": "Estimates exclude OS file cache, Python, Zarr, and QA; mapped files are reclaimable.",
        "shared_cache_disk_GiB": ((raw_gradient_cache_bytes + axis2_spectrum_bytes) / 1024**3
                                  if cfg.fft_cache_mode == "memmap" else 0.0),
        "fft_slab_working_estimate_GiB": cfg.fft_slab_width * max(cfg.grid_shape)**2 * 64 / 1024**3,
        **_sharp_edge_metadata(cfg, cfg.sigma_grid),
        "velocity_cache_GiB": cfg.bytes_per_snapshot / 1024**3,
        "shared_gradient_GiB": shared_gradient_bytes / 1024**3,
        "workspace_GiB": workspace_bytes / 1024**3,
        "batch_raw_gradient_RAM_GiB": raw_gradient_cache_bytes / 1024**3 if cfg.fft_cache_mode == "memory" else 0.0,
        "batch_first_axis_spectra_RAM_GiB": axis2_spectrum_bytes / 1024**3 if cfg.fft_cache_mode == "memory" else 0.0,
        "batch_shared_RAM_GiB": (
            raw_gradient_cache_bytes + axis2_spectrum_bytes
        )
        / 1024**3 if cfg.fft_cache_mode == "memory" else 0.0,
        "batch_filter_working_estimate_GiB": (
            raw_gradient_cache_bytes
            + axis2_spectrum_bytes
            + (2 * scalar_bytes if cfg.filter_type == "smooth_sharp" else 0)
        )
        / 1024**3 if cfg.fft_cache_mode == "memory" else cfg.fft_slab_width * max(cfg.grid_shape)**2 * 64 / 1024**3,
        "scratch_peak_GiB": scratch_bytes / 1024**3,
        "result_GiB": cfg.result_uncompressed_bytes / 1024**3,
        "configured_sigma_count": len(cfg.sigma_grids),
        "batch_result_GiB": (
            batch_result_bytes / 1024**3
        ),
        "batch_persistent_GiB": batch_persistent_bytes / 1024**3,
        "batch_with_reserve_GiB": (
            batch_persistent_bytes / 1024**3
            + cfg.persistent_safety_reserve_gib
        ),
        "batch_peak_with_workspace_and_reserve_GiB": (
            (batch_persistent_bytes + scratch_bytes) / 1024**3
            + cfg.persistent_safety_reserve_gib
        ),
        "result_reserve_GiB": cfg.persistent_safety_reserve_gib,
        "fft_workers": cfg.fft_workers,
        "compression_threads": cfg.compression_threads,
        "fft_input_block_MiB": (
            cfg.fft_slab_width
            * cfg.grid_shape[0]
            * cfg.grid_shape[1]
            * 4
            / 1024**2
        ),
    }


def _preflight_batch_space(cfg: PipelineConfig, time_index: int, count: int) -> None:
    cfg.result_root.mkdir(parents=True, exist_ok=True)
    run = cfg.run_path(time_index)
    run.mkdir(parents=True, exist_ok=True)
    points = int(np.prod(cfg.grid_shape))
    spectrum_bytes = cfg.full_shape_zyx[0] * cfg.full_shape_zyx[1] * (cfg.full_shape_zyx[2] // 2 + 1) * 8
    output = count * cfg.result_uncompressed_bytes + cfg.shared_gradient_uncompressed_bytes
    scratch = 10 * points * 4
    if cfg.fft_cache_mode == "memmap":
        # Gradients, twelve reusable spectra, acceleration and two FFT temporaries.
        scratch += cfg.shared_gradient_uncompressed_bytes + 14 * spectrum_bytes + points * 4
    output_reserve = int(cfg.persistent_safety_reserve_gib * 1024**3)
    scratch_reserve = int(cfg.scratch_safety_reserve_gib * 1024**3)
    if cfg.result_root.stat().st_dev == run.stat().st_dev:
        requirements = [(run, output + scratch + max(output_reserve, scratch_reserve))]
    else:
        requirements = [(cfg.result_root, output + output_reserve), (run, scratch + scratch_reserve)]
    for path, required in requirements:
        free = shutil.disk_usage(path).free
        if free < required:
            raise RuntimeError(f"insufficient batch space on {path}: {free / 1024**3:.2f} GiB free, "
                               f"need {required / 1024**3:.2f} GiB including shared cache and reserve")


def _preflight_result_space(cfg: PipelineConfig) -> dict[str, float]:
    cfg.result_root.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(cfg.result_root)
    required = cfg.result_uncompressed_bytes + cfg.shared_gradient_uncompressed_bytes + int(
        cfg.persistent_safety_reserve_gib * 1024**3
    )
    if usage.free < required:
        raise RuntimeError(
            f"insufficient result space: {usage.free / 1024**3:.2f} GiB free, "
            f"need {required / 1024**3:.2f} GiB including reserve"
        )
    return {
        "filesystem_free_GiB": usage.free / 1024**3,
        "required_GiB": required / 1024**3,
        "result_root": str(cfg.result_root),
    }


def _preflight_workspace_space(cfg: PipelineConfig, time_index: int) -> None:
    path = cfg.run_path(time_index)
    path.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(path)
    full_points = int(np.prod(cfg.grid_shape, dtype=np.int64))
    workspace_bytes = 10 * full_points * 4
    if cfg.fft_cache_mode == "memmap":
        workspace_bytes += 2 * full_points * 4 + 2 * cfg.grid_shape[0] * cfg.grid_shape[1] * 8
    required = workspace_bytes + int(cfg.scratch_safety_reserve_gib * 1024**3)
    if usage.free < required:
        raise RuntimeError(
            f"insufficient scratch workspace: {usage.free / 1024**3:.2f} GiB free, "
            f"need {required / 1024**3:.2f} GiB in addition to the velocity cache"
        )


def process_full(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grid: float | None = None,
    *,
    _raw_gradients: np.ndarray | None = None,
    _filter_spectra: dict[tuple[Any, ...], np.ndarray] | None = None,
    _acquire_lock: bool = True,
) -> Path:
    if _acquire_lock:
        cfg.lock_path.mkdir(parents=True, exist_ok=True)
        with FileLock(str(cfg.lock_path / "process.lock"), timeout=0):
            return process_full(cfg, time_index, sigma_grid,
                                _raw_gradients=_raw_gradients, _filter_spectra=_filter_spectra,
                                _acquire_lock=False)
    sigma = cfg.sigma_grid if sigma_grid is None else float(sigma_grid)
    if sigma <= 0:
        raise ValueError("sigma_grid must be positive")
    final = cfg.result_path(time_index, sigma)
    existing = reuse_complete_result(cfg, time_index, sigma)
    if existing is not None:
        return existing
    manifest_hash = input_manifest_hash(cfg, time_index)
    _preflight_result_space(cfg)
    _preflight_workspace_space(cfg, time_index)

    raw_root = zarr.open_group(str(cfg.raw_store_path(time_index)), mode="r")
    raw = raw_root["velocity"]
    expected = (3, cfg.grid_shape[2], cfg.grid_shape[1], cfg.grid_shape[0])
    if raw.shape != expected or np.dtype(raw.dtype) != np.dtype("<f4"):
        raise ValueError("validated velocity cache has an unexpected schema")
    if raw_root.attrs.get("manifest_hash") != manifest_hash:
        raise RuntimeError("velocity cache and persistent input manifest disagree")

    staging = cfg.staging_result_path(time_index, sigma)
    workspace = cfg.workspace_path(time_index, sigma)
    _safe_rmtree(staging, cfg.result_root / ".staging")
    filtered_velocity = _reusable_filtered_velocity(
        cfg, time_index, sigma, manifest_hash, expected
    )
    reused_filtered_velocity = filtered_velocity is not None
    if filtered_velocity is None:
        _safe_rmtree(workspace, cfg.run_path(time_index))
    workspace.mkdir(parents=True, exist_ok=True)
    result = create_result_group(cfg, time_index, sigma, overwrite=True)
    result.attrs.update(
        {
            "input_manifest_hash": manifest_hash,
            "result_schema_version": RESULT_SCHEMA_VERSION,
            "algorithm": f"full_periodic_{cfg.filter_type}_spectral_pi_sbar_regime_v7",
            "filter_type": cfg.filter_type,
            "filter_cutoff_definition": (
                None
                if cfg.filter_type == "gaussian"
                else "k_c = pi / (sigma_grid * dx)"
            ),
            **_sharp_edge_metadata(cfg, sigma),
            "pi_definition": "tau_ij * d_j(velocity_bar_i)",
            "pi_sign_convention": "Equation (2): W_full = W_resolved - pi + s_bar",
            "s_bar_definition": "d_j(velocity_bar_i * tau_ij)",
            "tau_definition": "filter(velocity_i * velocity_j) - velocity_bar_i * velocity_bar_j",
        }
    )

    full_shape = expected[1:]
    if filtered_velocity is None:
        filtered_velocity = memmap(workspace / "filtered_velocity.f32", expected)
    derivative = memmap(workspace / "derivative.f32", full_shape)
    acceleration = memmap(workspace / "acceleration.f32", full_shape)
    temp_a = memmap(workspace / "filter_a.f32", full_shape)
    temp_b = memmap(workspace / "filter_b.f32", full_shape)
    sgs_transport = memmap(workspace / "sgs_transport.f32", expected)
    cfg.lock_path.mkdir(parents=True, exist_ok=True)
    console = Console()
    gradient_sumsq = 0.0
    gradient_maximum = 0.0
    gradient_count = 0
    filtered_gradient_sumsq = 0.0
    filtered_gradient_maximum = 0.0
    filtered_gradient_count = 0

    shared_root, write_shared_gradient = _prepare_shared_gradient(
        cfg, time_index, manifest_hash
    )
    with Progress(
        SpinnerColumn("line"),
        TextColumn("{task.description}"),
        BarColumn(),
        "{task.completed}/{task.total}",
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("periodic spectral pipeline", total=39)
        for component in range(3):
            if not reused_filtered_velocity:
                _filter_with_optional_spectrum(
                    ComponentView(raw, component),
                    ComponentView(filtered_velocity, component),
                    temp_a,
                    temp_b,
                    sigma,
                    cfg,
                    _filter_spectra,
                    ("velocity", component),
                )
            filtered_velocity.flush()
            _copy_field(
                cfg,
                ComponentView(filtered_velocity, component),
                result["velocity_bar"],
                (component,),
            )
            progress.advance(task)

        atomic_json(
            workspace / "filtered_velocity.json",
            {
                "schema_version": RESULT_SCHEMA_VERSION,
                "status": "complete",
                "input_manifest_hash": manifest_hash,
                "sigma_grid": sigma,
                "filter_type": cfg.filter_type,
                **_sharp_edge_metadata(cfg, sigma),
                "shape": list(expected),
                "reused": reused_filtered_velocity,
            },
        )

        _zero_zarr(result["work_full"])
        _zero_zarr(result["work_resolved"])
        _zero_zarr(result["pi"])
        _zero_zarr(result["s_bar"])
        filtered_divergence = ComponentView(sgs_transport, 0)
        zero_field(filtered_divergence, cfg.fft_slab_width)

        for component in range(3):
            zero_field(acceleration, cfg.fft_slab_width)
            for derivative_component in range(3):
                if _raw_gradients is None:
                    derivative_field(
                        ComponentView(raw, component),
                        derivative,
                        derivative_component,
                        cfg.domain_length,
                        cfg.fft_slab_width,
                        workers=cfg.fft_workers,
                    )
                    derivative.flush()
                    raw_derivative = derivative
                else:
                    raw_derivative = _raw_gradients[
                        component, derivative_component
                    ]
                if write_shared_gradient:
                    _copy_field(
                        cfg,
                        raw_derivative,
                        shared_root["gradient"],
                        (component, derivative_component),
                    )
                sumsq, maximum, count = _field_statistics(
                    raw_derivative, cfg.fft_slab_width
                )
                gradient_sumsq += sumsq
                gradient_maximum = max(gradient_maximum, maximum)
                gradient_count += count
                accumulate_product(
                    acceleration,
                    ComponentView(raw, derivative_component),
                    raw_derivative,
                    cfg.fft_slab_width,
                )
                progress.advance(task)

            _filter_with_optional_spectrum(
                acceleration,
                derivative,
                temp_a,
                temp_b,
                sigma,
                cfg,
                _filter_spectra,
                ("acceleration", component),
            )
            derivative.flush()
            _accumulate_zarr_product(
                result["work_full"],
                ComponentView(filtered_velocity, component),
                derivative,
            )
            progress.advance(task)

            zero_field(acceleration, cfg.fft_slab_width)
            for derivative_component in range(3):
                derivative_field(
                    ComponentView(filtered_velocity, component),
                    derivative,
                    derivative_component,
                    cfg.domain_length,
                    cfg.fft_slab_width,
                    workers=cfg.fft_workers,
                )
                derivative.flush()
                _copy_field(
                    cfg,
                    derivative,
                    result["gradient_bar"],
                    (component, derivative_component),
                )
                sumsq, maximum, count = _field_statistics(
                    derivative, cfg.fft_slab_width
                )
                filtered_gradient_sumsq += sumsq
                filtered_gradient_maximum = max(
                    filtered_gradient_maximum, maximum
                )
                filtered_gradient_count += count
                if derivative_component == component:
                    _accumulate_full(
                        filtered_divergence,
                        derivative,
                        cfg.fft_slab_width,
                    )
                accumulate_product(
                    acceleration,
                    ComponentView(filtered_velocity, derivative_component),
                    derivative,
                    cfg.fft_slab_width,
                )
                progress.advance(task)
            _accumulate_zarr_product(
                result["work_resolved"],
                ComponentView(filtered_velocity, component),
                acceleration,
            )
            progress.advance(task)

        (
            filtered_divergence_sumsq,
            filtered_divergence_maximum,
            filtered_point_count,
        ) = _field_statistics(filtered_divergence, cfg.fft_slab_width)

        for component in range(3):
            zero_field(
                ComponentView(sgs_transport, component), cfg.fft_slab_width
            )

        for left_component in range(3):
            for right_component in range(left_component, 3):
                product = ProductView(
                        ComponentView(raw, left_component),
                        ComponentView(raw, right_component),
                    )
                _filter_with_optional_spectrum(
                    product,
                    derivative,
                    temp_a,
                    temp_b,
                    sigma,
                    cfg,
                    _filter_spectra,
                    ("product", left_component, right_component),
                )
                subtract_product(
                    derivative,
                    ComponentView(filtered_velocity, left_component),
                    ComponentView(filtered_velocity, right_component),
                    cfg.fft_slab_width,
                )
                derivative.flush()
                _copy_full(temp_a, derivative, cfg.fft_slab_width)

                derivative_field(
                    ComponentView(filtered_velocity, left_component),
                    derivative,
                    right_component,
                    cfg.domain_length,
                    cfg.fft_slab_width,
                    workers=cfg.fft_workers,
                )
                _accumulate_zarr_product(result["pi"], temp_a, derivative)
                if left_component != right_component:
                    derivative_field(
                        ComponentView(filtered_velocity, right_component),
                        derivative,
                        left_component,
                        cfg.domain_length,
                        cfg.fft_slab_width,
                        workers=cfg.fft_workers,
                    )
                    _accumulate_zarr_product(result["pi"], temp_a, derivative)

                accumulate_product(
                    ComponentView(sgs_transport, right_component),
                    ComponentView(filtered_velocity, left_component),
                    temp_a,
                    cfg.fft_slab_width,
                )
                if left_component != right_component:
                    accumulate_product(
                        ComponentView(sgs_transport, left_component),
                        ComponentView(filtered_velocity, right_component),
                        temp_a,
                        cfg.fft_slab_width,
                    )
                progress.advance(task)

        sgs_transport.flush()
        for derivative_component in range(3):
            derivative_field(
                ComponentView(sgs_transport, derivative_component),
                derivative,
                derivative_component,
                cfg.domain_length,
                cfg.fft_slab_width,
                workers=cfg.fft_workers,
            )
            derivative.flush()
            _accumulate_zarr(result["s_bar"], derivative)
            progress.advance(task)

        zero_field(acceleration, cfg.fft_slab_width)
        for component in range(3):
            if _raw_gradients is None:
                derivative_field(
                    ComponentView(raw, component),
                    derivative,
                    component,
                    cfg.domain_length,
                    cfg.fft_slab_width,
                    workers=cfg.fft_workers,
                )
                raw_diagonal = derivative
            else:
                raw_diagonal = _raw_gradients[component, component]
            for start in range(0, acceleration.shape[0], cfg.fft_slab_width):
                key = (
                    slice(
                        start,
                        min(start + cfg.fft_slab_width, acceleration.shape[0]),
                    ),
                    slice(None),
                    slice(None),
                )
                acceleration[key] = np.asarray(acceleration[key]) + np.asarray(
                    raw_diagonal[key]
                )
            progress.advance(task)

    if write_shared_gradient:
        _finalize_shared_gradient(
            cfg, time_index, manifest_hash, shared_root
        )

    atomic_json(
        staging / "shared_refs.json",
        _shared_references(cfg, time_index, manifest_hash),
    )

    divergence_sumsq, divergence_maximum, point_count = _field_statistics(
        acceleration, cfg.fft_slab_width
    )
    for mapped in (
        filtered_velocity,
        derivative,
        acceleration,
        temp_a,
        temp_b,
        sgs_transport,
    ):
        close_memmap(mapped)
    unfiltered_divergence_report = _divergence_metrics(
        cfg,
        divergence_sumsq,
        divergence_maximum,
        point_count,
        gradient_sumsq,
        gradient_maximum,
        gradient_count,
    )
    unfiltered_divergence_report["scope"] = "full_domain"
    filtered_divergence_report = _divergence_metrics(
        cfg,
        filtered_divergence_sumsq,
        filtered_divergence_maximum,
        filtered_point_count,
        filtered_gradient_sumsq,
        filtered_gradient_maximum,
        filtered_gradient_count,
    )
    filtered_divergence_report["scope"] = "full_domain"
    divergence_report = {
        "passed": bool(
            unfiltered_divergence_report["passed"]
            and filtered_divergence_report["passed"]
        ),
        "unfiltered": unfiltered_divergence_report,
        "filtered": filtered_divergence_report,
    }
    atomic_json(
        staging / "divergence.json", divergence_report
    )
    if not divergence_report["passed"]:
        result.attrs["status"] = "failed_divergence"
        raise RuntimeError(
            "full-domain divergence validation failed: "
            "unfiltered_relative_rms="
            f"{unfiltered_divergence_report['relative_divergence_rms']:.3e}, "
            "unfiltered_relative_max="
            f"{unfiltered_divergence_report['relative_maximum_divergence']:.3e}, "
            "filtered_relative_rms="
            f"{filtered_divergence_report['relative_divergence_rms']:.3e}, "
            "filtered_relative_max="
            f"{filtered_divergence_report['relative_maximum_divergence']:.3e}"
        )

    s_bar_report = compute_sbar_qa(result, cfg, scope="full_domain")
    s_bar_report_hash = write_sbar_artifacts(staging, s_bar_report)
    identity_metric = s_bar_report["metrics"]["identity_relative_residual_rms"]
    decomposition_report = {
        "identity": "work_full = work_resolved - pi + s_bar",
        "scope": "full_domain",
        "relative_residual_rms": identity_metric["value"],
        "absolute_residual_rms": identity_metric["residual_rms"],
        "joint_energy_rms": identity_metric["joint_energy_rms"],
        "residual_maximum_abs": identity_metric["maximum_abs"],
    }

    regime_report = _write_full_regime(
        result["work_full"], result["work_resolved"], result["regime"], cfg
    )
    cq_report = compute_cq(result, cfg)
    cq_report_hash = write_cq_artifacts(staging, cq_report)
    weak_report = cq_report["weak_asymmetry"]
    weak_report_hash = write_weak_asymmetry_artifacts(staging, weak_report)

    qa = {
        "dataset": cfg.dataset,
        "time_index": time_index,
        "sigma_grid": sigma,
        "filter_type": cfg.filter_type,
        **_sharp_edge_metadata(cfg, sigma),
        "input_manifest_hash": manifest_hash,
        "divergence": divergence_report,
        "decomposition": decomposition_report,
        "s_bar_global": {
            "passed": s_bar_report["passed"],
            "scope": s_bar_report["scope"],
            "report_version": s_bar_report["report_version"],
            "report_hash": s_bar_report_hash,
            "metrics": s_bar_report["metrics"],
        },
        "reuse": {
            "velocity_cache": True,
            "filtered_velocity": reused_filtered_velocity,
            "raw_gradients": _raw_gradients is not None,
            "first_axis_fft_spectra": _filter_spectra is not None,
        },
        "epsilon_full": regime_report["epsilon_full"],
        "epsilon_resolved": regime_report["epsilon_resolved"],
        "regime_scope": regime_report["scope"],
        "regime_point_count": regime_report["point_count"],
        "occupancy": regime_report["occupancy"],
        "cq": {
            "passed": cq_report["passed"],
            "scope": cq_report["scope"],
            "report_version": cq_report["report_version"],
            "report_hash": cq_report_hash,
            "partition_check": cq_report["partition_check"],
        },
        "weak_asymmetry": {
            "passed": weak_report["passed"],
            "scope": weak_report["scope"],
            "report_version": weak_report["report_version"],
            "report_hash": weak_report_hash,
            "asymmetry_index": weak_report["global"]["asymmetry_index"],
            "ratio_p99": weak_report["global"]["ratio_p99"],
            "ratio_max": weak_report["global"]["ratio_max"],
            "closure": weak_report["closure"],
        },
    }
    atomic_json(staging / "qa.json", qa)
    result.attrs.update(
        {
            "status": "processed",
            "epsilon_full": regime_report["epsilon_full"],
            "epsilon_resolved": regime_report["epsilon_resolved"],
            "occupancy": qa["occupancy"],
            "regime_scope": regime_report["scope"],
            "cq_passed": cq_report["passed"],
            "cq_report_version": cq_report["report_version"],
            "cq_report_hash": cq_report_hash,
            "weak_asymmetry_passed": weak_report["passed"],
            "weak_asymmetry_report_version": weak_report["report_version"],
            "weak_asymmetry_report_hash": weak_report_hash,
            "decomposition": decomposition_report,
            "s_bar_qa_passed": s_bar_report["passed"],
            "s_bar_qa_report_version": s_bar_report["report_version"],
            "s_bar_qa_report_hash": s_bar_report_hash,
            "reused_filtered_velocity": reused_filtered_velocity,
        }
    )
    return staging


def finalize_result(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grid: float | None = None,
) -> Path:
    sigma = cfg.sigma_grid if sigma_grid is None else float(sigma_grid)
    staging = cfg.staging_result_path(time_index, sigma)
    final = cfg.result_path(time_index, sigma)
    existing = reuse_complete_result(cfg, time_index, sigma)
    if existing is not None:
        return existing
    if not staging.is_dir():
        raise RuntimeError("persistent result staging directory is missing")
    root = zarr.open_group(str(staging / result_zarr_name(sigma)), mode="a")
    if root.attrs.get("status") != "processed":
        raise RuntimeError("persistent result staging has not completed processing")

    expected_shapes = {
        "velocity": (3, *cfg.full_shape_zyx),
        "gradient": (3, 3, *cfg.full_shape_zyx),
        "velocity_bar": (3, *cfg.full_shape_zyx),
        "gradient_bar": (3, 3, *cfg.full_shape_zyx),
        "work_full": cfg.full_shape_zyx,
        "work_resolved": cfg.full_shape_zyx,
        "pi": cfg.full_shape_zyx,
        "s_bar": cfg.full_shape_zyx,
        "regime": cfg.full_shape_zyx,
    }
    fields: dict[str, Any] = {}
    for name, (dtype, rank) in RESULT_FIELDS.items():
        if name not in root:
            raise RuntimeError(f"result field is missing: {name}")
        array = root[name]
        if len(array.shape) != rank or tuple(array.shape) != expected_shapes[name]:
            raise RuntimeError(f"result field has invalid shape: {name}={array.shape}")
        if np.dtype(array.dtype) != np.dtype(dtype):
            raise RuntimeError(f"result field has invalid dtype: {name}={array.dtype}")
        digest, byte_count, minimum, maximum = hash_zarr_array(array)
        fields[name] = {
            "shape": list(array.shape),
            "dtype": str(np.dtype(array.dtype)),
            "chunks": list(array.chunks),
            "sha256": digest,
            "byte_count": byte_count,
            "minimum": minimum,
            "maximum": maximum,
        }

    manifest = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "complete",
        "dataset": cfg.dataset,
        "time_index": time_index,
        "physical_time": cfg.physical_time(time_index),
        "sigma_grid": sigma,
        "filter_type": cfg.filter_type,
        **_sharp_edge_metadata(cfg, sigma),
        "input_manifest_hash": input_manifest_hash(cfg, time_index),
        "algorithm": root.attrs.get("algorithm"),


        "full_shape_xyz": list(cfg.grid_shape),
        "field_scopes": dict(root.attrs.get("field_scopes", {})),
        "s_bar_qa_passed": bool(root.attrs.get("s_bar_qa_passed", False)),
        "s_bar_qa_report_version": root.attrs.get("s_bar_qa_report_version"),
        "s_bar_qa_report_hash": root.attrs.get("s_bar_qa_report_hash"),
        "cq_passed": bool(root.attrs.get("cq_passed", False)),
        "cq_report_version": root.attrs.get("cq_report_version"),
        "cq_report_hash": root.attrs.get("cq_report_hash"),
        "weak_asymmetry_passed": bool(
            root.attrs.get("weak_asymmetry_passed", False)
        ),
        "weak_asymmetry_report_version": root.attrs.get(
            "weak_asymmetry_report_version"
        ),
        "weak_asymmetry_report_hash": root.attrs.get(
            "weak_asymmetry_report_hash"
        ),
        "fields": fields,
    }
    manifest_hash = atomic_json(staging / "manifest.json", manifest)
    root.attrs.update(
        {
            "status": "complete",
            "manifest_hash": manifest_hash,
            "output_hashes": {name: item["sha256"] for name, item in fields.items()},
        }
    )

    if final.exists():
        if (final / "COMPLETE").is_file():
            _safe_rmtree(final, cfg.result_root)
        else:
            raise FileExistsError(f"refusing to replace incomplete result: {final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final)
    complete = final / "COMPLETE"
    with complete.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps({"manifest_hash": manifest_hash}) + "\n")
        handle.flush()
        os.fsync(handle.fileno())

    if cfg.cleanup_scratch_on_success:
        workspace = cfg.workspace_path(time_index, sigma)
        _safe_rmtree(workspace, cfg.run_path(time_index))
    return final


def _build_batch_reuse(
    cfg: PipelineConfig,
    raw: Any,
    cache_dir: Path | None = None,
) -> tuple[np.ndarray, dict[tuple[Any, ...], np.ndarray]]:
    """Build shared gradients and twelve spectra once, in RAM or mapped files."""
    full_shape = cfg.full_shape_zyx
    use_disk = cfg.fft_cache_mode == "memmap"
    if use_disk and cache_dir is None:
        raise ValueError("memmap cache requires a workspace directory")
    gradients = (mapped_array(cache_dir / "gradients.f32", (3, 3, *full_shape), "<f4")
                 if use_disk else np.empty((3, 3, *full_shape), dtype=np.float32))
    spectra: dict[tuple[Any, ...], np.ndarray] = {}
    try:
        console = Console()
        with Progress(
            SpinnerColumn("line"),
            TextColumn("{task.description}"),
            BarColumn(),
            "{task.completed}/{task.total}",
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("multi-sigma shared FFT cache", total=21)
            for component in range(3):
                for derivative_component in range(3):
                    derivative_field(
                        ComponentView(raw, component),
                        gradients[component, derivative_component],
                        derivative_component,
                        cfg.domain_length,
                        cfg.fft_slab_width,
                        workers=cfg.fft_workers,
                    )
                    release_pages(gradients)
                    progress.advance(task)

            spectrum_builder = (
                full_spectrum if cfg.filter_type == "smooth_sharp" else axis2_spectrum
            )

            if use_disk:
                sequence = 0

                def spectrum_builder(source, slab, *, workers):
                    nonlocal sequence
                    sequence += 1
                    return build_spectrum(source, cache_dir / f"spectrum_{sequence}.c64",
                                          slab, workers=workers, full=cfg.filter_type == "smooth_sharp")

            for component in range(3):
                spectra[("velocity", component)] = spectrum_builder(
                    ComponentView(raw, component),
                    cfg.fft_slab_width,
                    workers=cfg.fft_workers,
                )
                progress.advance(task)

            acceleration = (mapped_array(cache_dir / "acceleration.f32", full_shape, "<f4")
                            if use_disk else np.empty(full_shape, dtype=np.float32))
            for component in range(3):
                acceleration.fill(0.0)
                for derivative_component in range(3):
                    accumulate_product(
                        acceleration,
                        ComponentView(raw, derivative_component),
                        gradients[component, derivative_component],
                        cfg.fft_slab_width,
                    )
                spectra[("acceleration", component)] = spectrum_builder(
                    acceleration,
                    cfg.fft_slab_width,
                    workers=cfg.fft_workers,
                )
                progress.advance(task)
            if use_disk:
                close_memmap(acceleration)
                (cache_dir / "acceleration.f32").unlink()
            del acceleration

            for left_component in range(3):
                for right_component in range(left_component, 3):
                    spectra[("product", left_component, right_component)] = spectrum_builder(
                        ProductView(
                            ComponentView(raw, left_component),
                            ComponentView(raw, right_component),
                        ),
                        cfg.fft_slab_width,
                        workers=cfg.fft_workers,
                    )
                    progress.advance(task)
    except BaseException:
        for array in [gradients, *spectra.values(), locals().get("acceleration")]:
            if isinstance(array, np.memmap) and not array._mmap.closed:
                array._mmap.close()
        raise
    return gradients, spectra


def _write_filter_batch_manifest(
    cfg: PipelineConfig,
    time_index: int,
    sigmas: tuple[float, ...],
    results: dict[float, Path],
    status: str,
) -> None:
    cfg.result_root.mkdir(parents=True, exist_ok=True)
    all_sigmas = set(float(sigma) for sigma in sigmas)
    result_prefix = cfg.result_id(time_index, 1.0).rsplit("_sigma_", 1)[0]
    for path in cfg.result_root.glob(f"{result_prefix}_sigma_*"):
        manifest_path = path / "manifest.json"
        if not path.is_dir() or not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            sigma = float(manifest["sigma_grid"])
            if (
                manifest.get("schema_version") == RESULT_SCHEMA_VERSION
                and int(manifest.get("time_index", -1)) == time_index
                and _filter_metadata_matches(manifest, cfg, sigma)
            ):
                all_sigmas.add(sigma)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    ordered_sigmas = tuple(sorted(all_sigmas))
    atomic_json(
        cfg.batch_manifest_path(time_index),
        {
            "schema_version": 1,
            "status": status,
            "dataset": cfg.dataset,
            "time_index": time_index,
            "physical_time": cfg.physical_time(time_index),
            "filter_type": cfg.filter_type,
            "sharp_edge_width_fraction": (
                cfg.sharp_edge_width_fraction
                if cfg.filter_type == "smooth_sharp"
                else None
            ),
            "sigma_grids": list(ordered_sigmas),
            "results": [
                {
                    "sigma_grid": sigma,
                    "path": str(cfg.result_path(time_index, sigma).resolve()),
                    "complete": _complete_result_is_current(cfg, cfg.result_path(time_index, sigma), sigma),
                }
                for sigma in ordered_sigmas
            ],
        },
    )


def process_batch(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grids: tuple[float, ...] | None = None,
) -> list[Path]:
    """Process missing sigmas with shared raw gradients and filter spectra."""
    sigmas = cfg.sigma_grids if sigma_grids is None else tuple(sigma_grids)
    if not sigmas:
        raise ValueError("at least one sigma is required")
    sigmas = tuple(float(sigma) for sigma in sigmas)
    if any(not np.isfinite(sigma) or sigma <= 0 for sigma in sigmas):
        raise ValueError("sigma values must be finite and positive")
    if len(set(sigmas)) != len(sigmas):
        raise ValueError("sigma values must be unique")
    results: dict[float, Path] = {}
    pending: list[float] = []
    for sigma in sigmas:
        existing = reuse_complete_result(cfg, time_index, sigma)
        if existing is None:
            pending.append(float(sigma))
        else:
            results[float(sigma)] = existing
    _write_filter_batch_manifest(cfg, time_index, sigmas, results, "running")
    if not pending:
        paths = [results[float(sigma)] for sigma in sigmas]
        _write_filter_batch_manifest(cfg, time_index, sigmas, results, "complete")
        return paths
    if len(pending) == 1:
        sigma = pending[0]
        process_full(cfg, time_index, sigma)
        results[sigma] = finalize_result(cfg, time_index, sigma)
        paths = [results[float(value)] for value in sigmas]
        _write_filter_batch_manifest(cfg, time_index, sigmas, results, "complete")
        return paths

    manifest_hash = input_manifest_hash(cfg, time_index)
    raw_root = zarr.open_group(str(cfg.raw_store_path(time_index)), mode="r")
    if raw_root.attrs.get("manifest_hash") != manifest_hash:
        raise RuntimeError("velocity cache and persistent input manifest disagree")
    raw = raw_root["velocity"]
    expected = (3, *cfg.full_shape_zyx)
    if tuple(raw.shape) != expected or np.dtype(raw.dtype) != np.dtype("<f4"):
        raise RuntimeError("validated velocity cache has an unexpected schema")

    _preflight_batch_space(cfg, time_index, len(pending))
    cfg.lock_path.mkdir(parents=True, exist_ok=True)
    with FileLock(str(cfg.lock_path / "process.lock"), timeout=0), TemporaryDirectory(
        prefix="batch-cache-", dir=cfg.run_path(time_index)
    ) as cache_directory:
        try:
            gradients, spectra = _build_batch_reuse(cfg, raw, Path(cache_directory))
        except MemoryError as exc:
            raise RuntimeError(
                "insufficient RAM for the multi-sigma cache; approximately 84 GiB is required"
            ) from exc
        try:
            for sigma in pending:
                print(
                    f"batch frame={time_index} filter={cfg.filter_type} "
                    f"sigma_grid={sigma:g} shared_fft=true",
                    flush=True,
                )
                process_full(
                    cfg,
                    time_index,
                    sigma,
                    _raw_gradients=gradients,
                    _filter_spectra=spectra,
                    _acquire_lock=False,
                )
                results[sigma] = finalize_result(cfg, time_index, sigma)
                _write_filter_batch_manifest(
                    cfg, time_index, sigmas, results, "running"
                )
        finally:
            for spectrum in spectra.values():
                if isinstance(spectrum, np.memmap):
                    close_memmap(spectrum)
            spectra.clear()
            if isinstance(gradients, np.memmap):
                close_memmap(gradients)
            del gradients
    paths = [results[float(sigma)] for sigma in sigmas]
    _write_filter_batch_manifest(cfg, time_index, sigmas, results, "complete")
    return paths


def reuse_complete_result(cfg: PipelineConfig, time_index: int, sigma_grid: float | None = None) -> Path | None:
    sigma = cfg.sigma_grid if sigma_grid is None else float(sigma_grid)
    final = cfg.result_path(time_index, sigma)
    if _complete_result_is_current(cfg, final, sigma):
        ensure_sbar_result(cfg, time_index, sigma)
        return ensure_cq_result(cfg, time_index, sigma)
    return None
