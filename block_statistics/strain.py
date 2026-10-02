from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from jhtdb_pipeline.config import PipelineConfig
from jhtdb_pipeline.physics import ComponentView, close_memmap, derivative_field, memmap
from jhtdb_pipeline.store import compressor, spatial_slices


STRAIN_CACHE_VERSION = 1


def _cache_is_current(cfg: PipelineConfig, time_index: int, input_hash: str) -> bool:
    path = cfg.strain_store_path(time_index)
    if not path.is_dir():
        return False
    try:
        root = zarr.open_group(str(path), mode="r")
        field = root["sij_sij"]
        return (
            root.attrs.get("status") == "complete"
            and root.attrs.get("strain_cache_version") == STRAIN_CACHE_VERSION
            and root.attrs.get("input_manifest_hash") == input_hash
            and tuple(field.shape) == cfg.full_shape_zyx
            and np.dtype(field.dtype) == np.dtype("<f4")
        )
    except Exception:
        return False


def _accumulate(destination: Any, contribution: Any, *, pair: Any | None = None) -> None:
    for key in spatial_slices(destination.shape, destination.chunks):
        left = np.asarray(contribution[key], dtype=np.float32)
        if pair is None:
            increment = np.square(left, dtype=np.float32)
        else:
            right = np.asarray(pair[key], dtype=np.float32)
            increment = np.float32(0.5) * np.square(left + right, dtype=np.float32)
        destination[key] = np.asarray(destination[key], dtype=np.float32) + increment


def _build_cache(cfg: PipelineConfig, time_index: int, input_hash: str) -> Path:
    raw_root = zarr.open_group(str(cfg.raw_store_path(time_index)), mode="r")
    raw = raw_root["velocity"]
    expected = (3, *cfg.full_shape_zyx)
    if tuple(raw.shape) != expected or np.dtype(raw.dtype) != np.dtype("<f4"):
        raise ValueError("validated velocity cache has an unexpected schema")
    if raw_root.attrs.get("manifest_hash") != input_hash:
        raise RuntimeError("raw velocity cache manifest changed while building strain cache")

    final = cfg.strain_store_path(time_index)
    staging = final.with_name(final.name + ".staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.parent.mkdir(parents=True, exist_ok=True)
    root = zarr.open_group(str(staging), mode="w")
    chunks = tuple(min(64, size) for size in cfg.full_shape_zyx)
    field = root.create_dataset(
        "sij_sij",
        shape=cfg.full_shape_zyx,
        chunks=chunks,
        dtype="<f4",
        compressor=compressor(cfg),
        fill_value=0.0,
    )
    root.attrs.update(
        {
            "status": "computing",
            "strain_cache_version": STRAIN_CACHE_VERSION,
            "dataset": cfg.dataset,
            "time_index": time_index,
            "physical_time": cfg.physical_time(time_index),
            "input_manifest_hash": input_hash,
            "velocity_source": str(cfg.raw_store_path(time_index).resolve()),
            "axis_order": ["z", "y", "x"],
            "definition": "sum_ij S_ij*S_ij; S_ij=0.5*(d_j u_i+d_i u_j); u is unfiltered",
        }
    )

    scratch = Path(__file__).resolve().parent / ".scratch" / f"t{time_index:06d}" / "shared_strain_workspace"
    scratch.mkdir(parents=True, exist_ok=True)
    temp_a = memmap(scratch / "temp_a.f32", cfg.full_shape_zyx)
    temp_b = memmap(scratch / "temp_b.f32", cfg.full_shape_zyx)
    try:
        with Progress(
            SpinnerColumn("line"), TextColumn("{task.description}"), BarColumn(),
            "{task.completed}/{task.total}", TimeElapsedColumn(), console=Console(),
        ) as progress:
            task = progress.add_task("shared raw-velocity SijSij", total=9)
            for component in range(3):
                derivative_field(
                    ComponentView(raw, component), temp_a, component,
                    cfg.domain_length, cfg.fft_slab_width, workers=cfg.fft_workers,
                )
                temp_a.flush()
                _accumulate(field, temp_a)
                progress.advance(task)
            for i in range(3):
                for j in range(i + 1, 3):
                    derivative_field(
                        ComponentView(raw, i), temp_a, j, cfg.domain_length,
                        cfg.fft_slab_width, workers=cfg.fft_workers,
                    )
                    derivative_field(
                        ComponentView(raw, j), temp_b, i, cfg.domain_length,
                        cfg.fft_slab_width, workers=cfg.fft_workers,
                    )
                    temp_a.flush()
                    temp_b.flush()
                    _accumulate(field, temp_a, pair=temp_b)
                    progress.advance(task, advance=2)
        root.attrs["status"] = "complete"
        if final.exists():
            if _cache_is_current(cfg, time_index, input_hash):
                shutil.rmtree(staging)
                return final
            shutil.rmtree(final)
        os.replace(staging, final)
        return final
    finally:
        close_memmap(temp_a)
        close_memmap(temp_b)
        if scratch.exists():
            shutil.rmtree(scratch)


def ensure_strain_cache(cfg: PipelineConfig, time_index: int, input_hash: str) -> Any:
    """Return the shared full-domain raw-velocity S_ij S_ij array."""
    if not _cache_is_current(cfg, time_index, input_hash):
        cfg.lock_path.mkdir(parents=True, exist_ok=True)
        lock = cfg.lock_path / f"strain-t{time_index:06d}.lock"
        with FileLock(str(lock), timeout=0):
            if not _cache_is_current(cfg, time_index, input_hash):
                _build_cache(cfg, time_index, input_hash)
    return zarr.open_group(str(cfg.strain_store_path(time_index)), mode="r")["sij_sij"]


__all__ = ["STRAIN_CACHE_VERSION", "ensure_strain_cache"]
