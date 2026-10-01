from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from .config import PipelineConfig, result_zarr_name
from .cq import REGIME_KEYS
from .store import spatial_slices
from .validation import atomic_json


REGIME_PI_REPORT_VERSION = 1
DEFAULT_REGIME_PI_OUTPUT_ROOT = Path("regime_pi/output")


def _chunk_count(shape: tuple[int, ...], chunks: tuple[int, ...]) -> int:
    return int(
        np.prod(
            [(size + chunk - 1) // chunk for size, chunk in zip(shape, chunks)],
            dtype=np.int64,
        )
    )


def _regime_masks(full: np.ndarray, resolved: np.ndarray) -> tuple[np.ndarray, ...]:
    full_negative = full < 0.0
    resolved_negative = resolved < 0.0
    q1 = ~full_negative & ~resolved_negative
    q4 = full_negative & resolved_negative
    delta_nonnegative = (full - resolved) >= 0.0
    return (
        q1 & delta_nonnegative,
        q1 & ~delta_nonnegative,
        ~full_negative & resolved_negative,
        full_negative & ~resolved_negative,
        q4 & delta_nonnegative,
        q4 & ~delta_nonnegative,
    )


def compute_regime_pi_statistics(root: Any, cfg: PipelineConfig) -> dict[str, Any]:
    """Split stored Pi into backscatter/forward parts inside every Cq regime."""
    pi = root["pi"]
    work_full = root["work_full"]
    work_resolved = root["work_resolved"]
    expected = cfg.full_shape_zyx
    arrays = (pi, work_full, work_resolved)
    if any(tuple(array.shape) != expected for array in arrays):
        raise RuntimeError("regime Pi statistics require full-domain fields")
    if any(np.dtype(array.dtype) != np.dtype("<f4") for array in arrays):
        raise RuntimeError("regime Pi statistics require float32 fields")

    regime_counts = np.zeros(6, dtype=np.int64)
    direction_counts = np.zeros((6, 2), dtype=np.int64)
    magnitude_sums = np.zeros((6, 2), dtype=np.float64)
    zero_counts = np.zeros(6, dtype=np.int64)
    signed_sums = np.zeros(6, dtype=np.float64)
    point_count = 0
    chunks = tuple(int(value) for value in pi.chunks)
    with Progress(
        SpinnerColumn("line"),
        TextColumn("{task.description}"),
        BarColumn(),
        "{task.completed}/{task.total}",
        TimeElapsedColumn(),
        console=Console(),
    ) as progress:
        task = progress.add_task(
            "full-domain Pi direction by regime",
            total=_chunk_count(expected, chunks),
        )
        for key in spatial_slices(expected, chunks):
            values = np.asarray(pi[key], dtype=np.float32)
            full = np.asarray(work_full[key], dtype=np.float32)
            resolved = np.asarray(work_resolved[key], dtype=np.float32)
            if any(not np.all(np.isfinite(field)) for field in (values, full, resolved)):
                raise ValueError("Pi or work field contains NaN or Inf")
            values64 = values.astype(np.float64)
            for index, mask in enumerate(_regime_masks(full, resolved)):
                count = int(np.count_nonzero(mask))
                regime_counts[index] += count
                if not count:
                    continue
                selected = values64[mask]
                positive = selected > 0.0
                negative = selected < 0.0
                backscatter_count = int(np.count_nonzero(positive))
                forward_count = int(np.count_nonzero(negative))
                direction_counts[index, 0] += backscatter_count
                direction_counts[index, 1] += forward_count
                zero_counts[index] += count - backscatter_count - forward_count
                if backscatter_count:
                    magnitude_sums[index, 0] += float(selected[positive].sum(dtype=np.float64))
                if forward_count:
                    magnitude_sums[index, 1] += float(-selected[negative].sum(dtype=np.float64))
                signed_sums[index] += float(selected.sum(dtype=np.float64))
            point_count += values.size
            progress.advance(task)

    expected_count = int(np.prod(expected, dtype=np.int64))
    regimes: dict[str, Any] = {}
    closure_residual_max = 0.0
    for index, name in enumerate(REGIME_KEYS):
        count = int(regime_counts[index])
        directions: dict[str, Any] = {}
        for direction_index, direction_name in enumerate(("backscatter", "forward")):
            direction_count = int(direction_counts[index, direction_index])
            magnitude_sum = float(magnitude_sums[index, direction_index])
            mean = magnitude_sum / direction_count if direction_count else None
            fraction = direction_count / count if count else None
            intensity = magnitude_sum / count if count else None
            directions[direction_name] = {
                "count": direction_count,
                "magnitude_sum": magnitude_sum,
                "mean": mean,
                "fraction": fraction,
                "intensity": intensity,
            }
        signed_sum = float(signed_sums[index])
        signed_mean = signed_sum / count if count else None
        reconstructed_sum = (
            directions["backscatter"]["magnitude_sum"]
            - directions["forward"]["magnitude_sum"]
        )
        residual = reconstructed_sum - signed_sum
        scale = (
            directions["backscatter"]["magnitude_sum"]
            + directions["forward"]["magnitude_sum"]
        )
        relative = abs(residual) / scale if scale else (0.0 if residual == 0.0 else None)
        if relative is not None:
            closure_residual_max = max(closure_residual_max, relative)
        regimes[name] = {
            "count": count,
            "volume_fraction": count / point_count,
            "zero_count": int(zero_counts[index]),
            "zero_fraction": int(zero_counts[index]) / count if count else None,
            "signed_pi_sum": signed_sum,
            "signed_pi_mean": signed_mean,
            "directions": directions,
            "closure": {
                "identity": "backscatter magnitude sum - forward magnitude sum = signed Pi sum",
                "reconstructed_signed_sum": reconstructed_sum,
                "residual_sum": residual,
                "relative_to_absolute_transfer": relative,
            },
        }

    coverage = int(regime_counts.sum(dtype=np.int64))
    tolerance = cfg.cq_partition_relative_max
    passed = bool(
        point_count == expected_count
        and coverage == expected_count
        and closure_residual_max <= tolerance
    )
    return {
        "report_version": REGIME_PI_REPORT_VERSION,
        "status": "complete",
        "scope": "full_domain",
        "point_count": point_count,
        "regime_definition": "same threshold-independent six Cq regimes as cq.json",
        "sign_convention": {
            "stored_pi": "pi = tau:S",
            "backscatter": "pi > 0",
            "forward": "pi < 0; displayed magnitude is -pi",
            "zero": "pi == 0",
        },
        "metric_definitions": {
            "mean": "sum(abs(pi_direction)) / N_q_direction",
            "fraction": "N_q_direction / N_q",
            "intensity": "sum(abs(pi_direction)) / N_q = mean * fraction",
        },
        "regime_order": list(REGIME_KEYS),
        "regimes": regimes,
        "coverage": {
            "regime_point_count": coverage,
            "target_point_count": expected_count,
            "complete": coverage == expected_count == point_count,
        },
        "closure": {
            "maximum_relative_residual": closure_residual_max,
            "threshold": tolerance,
            "passed": passed,
        },
        "passed": passed,
    }


def regime_pi_output_dir(
    result_dir: Path | str,
    output_root: Path | str = DEFAULT_REGIME_PI_OUTPUT_ROOT,
) -> Path:
    return Path(output_root) / Path(result_dir).name


def regime_pi_report_is_current(path: Path, result_manifest_hash: str | None) -> bool:
    if not path.is_file():
        return False
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        report.get("report_version") == REGIME_PI_REPORT_VERSION
        and report.get("status") == "complete"
        and report.get("result_manifest_hash") == result_manifest_hash
    )


def run_regime_pi_statistics(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grid: float,
    *,
    output_root: Path | str = DEFAULT_REGIME_PI_OUTPUT_ROOT,
    overwrite: bool = False,
) -> Path:
    sigma = float(sigma_grid)
    result_dir = cfg.result_path(time_index, sigma)
    if not (result_dir / "COMPLETE").is_file():
        raise RuntimeError(f"complete result is missing: {result_dir}")
    root = zarr.open_group(str(result_dir / result_zarr_name(sigma)), mode="r")
    result_manifest_hash = root.attrs.get("manifest_hash")
    destination = regime_pi_output_dir(result_dir, output_root)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "regime_pi_transfer.json"
    if not overwrite and regime_pi_report_is_current(report_path, result_manifest_hash):
        return report_path
    with FileLock(str(destination / ".compute.lock"), timeout=0):
        report = compute_regime_pi_statistics(root, cfg)
        report.update(
            {
                "result_id": result_dir.name,
                "result_path": str(result_dir.resolve()),
                "result_manifest_hash": result_manifest_hash,
                "time_index": time_index,
                "physical_time": float(root.attrs.get("physical_time", cfg.physical_time(time_index))),
                "filter_type": str(root.attrs.get("filter_type", "gaussian")),
                "sigma_grid": sigma,
                "sharp_edge_width_fraction": root.attrs.get("sharp_edge_width_fraction"),
            }
        )
        atomic_json(report_path, report)
    return report_path


__all__ = [
    "DEFAULT_REGIME_PI_OUTPUT_ROOT",
    "REGIME_PI_REPORT_VERSION",
    "compute_regime_pi_statistics",
    "regime_pi_output_dir",
    "regime_pi_report_is_current",
    "run_regime_pi_statistics",
]
