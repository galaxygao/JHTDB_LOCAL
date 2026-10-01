from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from filelock import FileLock

from jhtdb_pipeline.config import FILTER_TYPES, PipelineConfig, load_config
from jhtdb_pipeline.store import open_complete_result
from jhtdb_pipeline.strain import STRAIN_CACHE_VERSION, ensure_strain_cache


FIELD_NAMES = ("work_resolved", "work_full", "pi")
REPORT_VERSION = 3


def _divisions3(divisions: int | Iterable[int]) -> tuple[int, int, int]:
    if isinstance(divisions, (int, np.integer)):
        values = (int(divisions),) * 3
    else:
        values = tuple(int(value) for value in divisions)
    if len(values) != 3 or any(value <= 0 for value in values):
        raise ValueError("divisions must contain three positive integers")
    return values


def _block_shape(
    shape_zyx: tuple[int, int, int], divisions_zyx: tuple[int, int, int]
) -> tuple[int, int, int]:
    if any(size % count for size, count in zip(shape_zyx, divisions_zyx)):
        raise ValueError("every spatial dimension must be divisible by its block count")
    return tuple(size // count for size, count in zip(shape_zyx, divisions_zyx))


def _block_keys(
    shape_zyx: tuple[int, int, int], divisions_zyx: tuple[int, int, int]
):
    block_zyx = _block_shape(shape_zyx, divisions_zyx)
    for bz in range(divisions_zyx[0]):
        for by in range(divisions_zyx[1]):
            for bx in range(divisions_zyx[2]):
                index = (bz, by, bx)
                yield index, tuple(
                    slice(block_index * block_size, (block_index + 1) * block_size)
                    for block_index, block_size in zip(index, block_zyx)
                )


def block_moments(
    field: Any, divisions: int | Iterable[int] = 16
) -> dict[str, np.ndarray | int | tuple[int, int, int]]:
    """Return exact per-block moments without sampling any grid points.

    Spatial array order is ``(z, y, x)``. Sums and squared sums accumulate in
    float64 even when the stored field is float32.
    """
    shape = tuple(int(value) for value in field.shape)
    if len(shape) != 3:
        raise ValueError("field must be a three-dimensional scalar array")
    divisions_zyx = _divisions3(divisions)
    block_zyx = _block_shape(shape, divisions_zyx)
    sums = np.empty(divisions_zyx, dtype=np.float64)
    sums_squared = np.empty(divisions_zyx, dtype=np.float64)
    minima = np.empty(divisions_zyx, dtype=np.float64)
    maxima = np.empty(divisions_zyx, dtype=np.float64)
    for index, key in _block_keys(shape, divisions_zyx):
        values = np.asarray(field[key], dtype=np.float32)
        if not np.all(np.isfinite(values)):
            raise ValueError("field contains NaN or Inf")
        sums[index] = values.sum(dtype=np.float64)
        sums_squared[index] = np.square(values, dtype=np.float64).sum(dtype=np.float64)
        minima[index] = float(values.min())
        maxima[index] = float(values.max())
    point_count = int(np.prod(block_zyx, dtype=np.int64))
    means = sums / point_count
    variances = np.maximum(sums_squared / point_count - np.square(means), 0.0)
    return {
        "sum": sums,
        "mean": means,
        "std": np.sqrt(variances),
        "min": minima,
        "max": maxima,
        "point_count": point_count,
        "block_shape_zyx": block_zyx,
        "divisions_zyx": divisions_zyx,
    }


def strain_contraction_block_sums(
    gradient: Any, divisions: int | Iterable[int] = 16
) -> np.ndarray:
    """Compute block sums of S_ij S_ij from ``gradient[i,j]=d_j u_i``.

    The contraction includes all nine tensor positions, so every off-diagonal
    symmetric component contributes twice.
    """
    shape = tuple(int(value) for value in gradient.shape)
    if len(shape) != 5 or shape[:2] != (3, 3):
        raise ValueError("gradient must have shape (3, 3, z, y, x)")
    spatial_shape = shape[2:]
    divisions_zyx = _divisions3(divisions)
    _block_shape(spatial_shape, divisions_zyx)
    sums = np.zeros(divisions_zyx, dtype=np.float64)
    for index, key in _block_keys(spatial_shape, divisions_zyx):
        value = 0.0
        for i in range(3):
            diagonal = np.asarray(gradient[(i, i) + key], dtype=np.float32)
            value += float(np.square(diagonal, dtype=np.float64).sum())
        for i in range(3):
            for j in range(i + 1, 3):
                left = np.asarray(gradient[(i, j) + key], dtype=np.float32)
                right = np.asarray(gradient[(j, i) + key], dtype=np.float32)
                value += float(
                    (0.5 * np.square(left + right, dtype=np.float64)).sum()
                )
        sums[index] = value
    return sums


def _validate_filter_metadata(cfg: PipelineConfig, sigma: float, attrs: Any) -> None:
    actual_type = str(attrs.get("filter_type", "gaussian"))
    if actual_type != cfg.filter_type:
        raise ValueError(
            f"result filter is {actual_type}, but configuration selects {cfg.filter_type}"
        )
    if cfg.filter_type == "smooth_sharp":
        actual_fraction = float(attrs.get("sharp_edge_width_fraction"))
        if not np.isclose(
            actual_fraction,
            cfg.sharp_edge_width_fraction,
            rtol=1e-12,
            atol=0.0,
        ):
            raise ValueError(
                "result and configuration use different smooth-sharp width fractions"
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(
    path: Path,
    cfg: PipelineConfig,
    divisions_zyx: tuple[int, int, int],
    strain_sums: np.ndarray,
    moments: dict[str, dict[str, Any]],
) -> None:
    full_shape = cfg.full_shape_zyx
    block_shape = _block_shape(full_shape, divisions_zyx)
    points = int(np.prod(block_shape, dtype=np.int64))
    dx = cfg.domain_length / cfg.grid_shape[0]
    columns = [
        "block_id", "block_x", "block_y", "block_z",
        "ix_start", "ix_stop", "iy_start", "iy_stop", "iz_start", "iz_stop",
        "x_start", "x_stop", "y_start", "y_stop", "z_start", "z_stop",
        "point_count", "sij_sij_mean", "sij_sij_sum",
    ]
    for name in FIELD_NAMES:
        columns.extend(
            [f"{name}_mean", f"{name}_sum", f"{name}_std", f"{name}_min", f"{name}_max"]
        )
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for (bz, by, bx), _ in _block_keys(full_shape, divisions_zyx):
            ix0, iy0, iz0 = bx * block_shape[2], by * block_shape[1], bz * block_shape[0]
            ix1, iy1, iz1 = ix0 + block_shape[2], iy0 + block_shape[1], iz0 + block_shape[0]
            index = (bz, by, bx)
            row: dict[str, Any] = {
                "block_id": bz * divisions_zyx[1] * divisions_zyx[2] + by * divisions_zyx[2] + bx,
                "block_x": bx, "block_y": by, "block_z": bz,
                "ix_start": ix0, "ix_stop": ix1,
                "iy_start": iy0, "iy_stop": iy1,
                "iz_start": iz0, "iz_stop": iz1,
                "x_start": ix0 * dx, "x_stop": ix1 * dx,
                "y_start": iy0 * dx, "y_stop": iy1 * dx,
                "z_start": iz0 * dx, "z_stop": iz1 * dx,
                "point_count": points,
                "sij_sij_mean": strain_sums[index] / points,
                "sij_sij_sum": strain_sums[index],
            }
            for name in FIELD_NAMES:
                for statistic in ("mean", "sum", "std", "min", "max"):
                    row[f"{name}_{statistic}"] = moments[name][statistic][index]
            writer.writerow(row)
    temporary.replace(path)


def compute_block_statistics(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grid: float,
    *,
    blocks_per_axis: int = 16,
    output_root: Path | str = Path("block_statistics/output"),
    scratch_root: Path | str = Path("block_statistics/.scratch"),
    overwrite: bool = False,
) -> Path:
    """Compute block means for raw-velocity strain, Wres, Wfull and Pi."""
    sigma = float(sigma_grid)
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma_grid must be finite and positive")
    divisions_zyx = _divisions3(blocks_per_axis)
    result_dir = cfg.result_path(time_index, sigma)
    result = open_complete_result(result_dir)
    _validate_filter_metadata(cfg, sigma, result.attrs)
    if tuple(result["work_full"].shape) != cfg.full_shape_zyx:
        raise ValueError("block statistics require a full-domain result")

    output_dir = Path(output_root) / result_dir.name
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"block_statistics_{blocks_per_axis}x{blocks_per_axis}x{blocks_per_axis}.csv"
    metadata_path = output_dir / "metadata.json"
    if csv_path.is_file() and metadata_path.is_file() and not overwrite:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            metadata.get("report_version") == REPORT_VERSION
            and metadata.get("result_manifest_hash") == result.attrs.get("manifest_hash")
            and metadata.get("blocks_per_axis") == blocks_per_axis
            and metadata.get("csv_sha256") == _sha256(csv_path)
        ):
            return csv_path

    lock = FileLock(str(output_dir / ".compute.lock"), timeout=0)
    with lock:
        input_hash = str(result.attrs.get("input_manifest_hash", ""))
        if not input_hash:
            raise RuntimeError("result is missing its input manifest hash")
        strain_field = ensure_strain_cache(cfg, time_index, input_hash)
        strain_sums = np.asarray(
            block_moments(strain_field, divisions_zyx)["sum"], dtype=np.float64
        )
        moments = {name: block_moments(result[name], divisions_zyx) for name in FIELD_NAMES}
        _write_csv(csv_path, cfg, divisions_zyx, strain_sums, moments)
        block_shape = _block_shape(cfg.full_shape_zyx, divisions_zyx)
        points = int(np.prod(block_shape, dtype=np.int64))
        metadata = {
            "report_version": REPORT_VERSION,
            "status": "complete",
            "result_id": result_dir.name,
            "result_path": str(result_dir.resolve()),
            "result_manifest_hash": result.attrs.get("manifest_hash"),
            "time_index": time_index,
            "physical_time": float(result.attrs.get("physical_time", cfg.physical_time(time_index))),
            "filter_type": cfg.filter_type,
            "sigma_grid": sigma,
            "sharp_edge_width_fraction": result.attrs.get("sharp_edge_width_fraction"),
            "scope": "full_domain",
            "sampling": "none; every grid point belongs to exactly one block",
            "array_axis_order": ["z", "y", "x"],
            "csv_block_axis_order": ["x", "y", "z"],
            "blocks_per_axis": blocks_per_axis,
            "block_count": blocks_per_axis**3,
            "block_shape_zyx": list(block_shape),
            "points_per_block": points,
            "domain_length": cfg.domain_length,
            "definitions": {
                "gradient_ij": "d_j velocity_i (unfiltered/raw velocity)",
                "strain_ij": "0.5 * (gradient_ij + gradient_ji)",
                "sij_sij": "sum over i,j of strain_ij * strain_ij",
                "primary_statistic": "arithmetic mean over all points in each block",
            },
            "strain_velocity_source": "validated full-domain raw velocity cache",
            "strain_cache": {
                "path": str(cfg.strain_store_path(time_index).resolve()),
                "version": STRAIN_CACHE_VERSION,
                "input_manifest_hash": input_hash,
            },
            "global_means_from_blocks": {
                "sij_sij": float(strain_sums.sum() / np.prod(cfg.full_shape_zyx)),
                **{
                    name: float(np.asarray(moments[name]["sum"]).sum() / np.prod(cfg.full_shape_zyx))
                    for name in FIELD_NAMES
                },
            },
            "csv_path": str(csv_path.resolve()),
            "csv_sha256": _sha256(csv_path),
        }
        temporary = metadata_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(metadata_path)
    return csv_path


__all__ = [
    "block_moments",
    "compute_block_statistics",
    "strain_contraction_block_sums",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute exact 16^3 full-domain block statistics for raw-velocity "
            "S_ij S_ij, W_resolved, W_full and Pi"
        )
    )
    parser.add_argument("--config", default="configs/pipeline.yaml")
    parser.add_argument("--time-index", type=int, required=True)
    parser.add_argument("--sigma-grid", type=float, required=True)
    parser.add_argument("--filter-type", choices=FILTER_TYPES)
    parser.add_argument("--sharp-edge-width-fraction", type=float)
    parser.add_argument("--blocks-per-axis", type=int, default=16)
    parser.add_argument("--output-root", type=Path, default=Path("block_statistics/output"))
    parser.add_argument("--scratch-root", type=Path, default=Path("block_statistics/.scratch"))
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    if args.filter_type is not None:
        cfg = cfg.with_filter(args.filter_type)
    if args.sharp_edge_width_fraction is not None:
        cfg = cfg.with_sharp_edge_width_fraction(args.sharp_edge_width_fraction)
    output = compute_block_statistics(
        cfg,
        args.time_index,
        args.sigma_grid,
        blocks_per_axis=args.blocks_per_axis,
        output_root=args.output_root,
        scratch_root=args.scratch_root,
        overwrite=args.overwrite,
    )
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
