from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from jhtdb_pipeline.config import FILTER_TYPES, PipelineConfig, load_config
from jhtdb_pipeline.store import open_complete_result

try:
    from block_statistics.compute_block_statistics import (
        _block_keys, _block_shape, _divisions3, _sha256, _validate_filter_metadata,
    )
except ModuleNotFoundError as error:  # direct ``python block_statistics/...py`` use
    if error.name != "block_statistics":
        raise
    from compute_block_statistics import (  # type: ignore[no-redef]
        _block_keys, _block_shape, _divisions3, _sha256, _validate_filter_metadata,
    )


REPORT_VERSION = 1
PAIR_SPECS = {
    "1_4": ((1, 2), (5, 6)),  # legacy Q1=(1+,1-), Q4=(4+,4-)
    "2_3": ((3,), (4,)),
}
DIRECTIONS = ("backscatter", "forward", "total")


def normalized_difference(left: float, right: float) -> float:
    """Return (left-right)/(left+right), or NaN when both are zero."""
    denominator = left + right
    return (left - right) / denominator if denominator != 0.0 else math.nan


def pair_asymmetry(
    left_backscatter: float,
    left_forward: float,
    right_backscatter: float,
    right_forward: float,
) -> dict[str, float]:
    """Return bounded directional and signed-total asymmetry for one pair."""
    activity = left_backscatter + left_forward + right_backscatter + right_forward
    total = (
        ((left_backscatter - left_forward) - (right_backscatter - right_forward))
        / activity
        if activity != 0.0 else math.nan
    )
    return {
        "backscatter": normalized_difference(left_backscatter, right_backscatter),
        "forward": normalized_difference(left_forward, right_forward),
        "total": total,
    }


def _directional_sums(
    pi: np.ndarray, regime: np.ndarray, codes: Iterable[int]
) -> tuple[float, float, int]:
    mask = np.isin(regime, tuple(codes))
    values = pi[mask]
    backscatter = values[values > 0.0].sum(dtype=np.float64)
    forward = -values[values < 0.0].sum(dtype=np.float64)
    return float(backscatter), float(forward), int(mask.sum(dtype=np.int64))


def compute_regime_pair_asymmetry(
    pi_field: Any,
    regime_field: Any,
    strain_rows: list[dict[str, str]],
    divisions: int | Iterable[int] = 16,
) -> list[dict[str, Any]]:
    """Compute exact blockwise Q1/Q4 and Q2/Q3 Pi asymmetries."""
    shape = tuple(int(value) for value in pi_field.shape)
    if shape != tuple(int(value) for value in regime_field.shape) or len(shape) != 3:
        raise ValueError("pi and regime must be same-shape three-dimensional fields")
    divisions_zyx = _divisions3(divisions)
    _block_shape(shape, divisions_zyx)
    expected = int(np.prod(divisions_zyx, dtype=np.int64))
    if len(strain_rows) != expected:
        raise ValueError(f"strain CSV has {len(strain_rows)} rows; expected {expected}")
    rows_by_id = {int(row["block_id"]): row for row in strain_rows}
    if len(rows_by_id) != expected:
        raise ValueError("strain CSV block_id values are not unique and complete")

    output: list[dict[str, Any]] = []
    for block_id, ((bz, by, bx), key) in enumerate(_block_keys(shape, divisions_zyx)):
        source = rows_by_id.get(block_id)
        if source is None:
            raise ValueError(f"strain CSV is missing block_id {block_id}")
        coordinates = (int(source["block_x"]), int(source["block_y"]), int(source["block_z"]))
        if coordinates != (bx, by, bz):
            raise ValueError(f"strain CSV coordinates disagree for block_id {block_id}")
        pi = np.asarray(pi_field[key], dtype=np.float32)
        regime = np.asarray(regime_field[key], dtype=np.uint8)
        if not np.all(np.isfinite(pi)):
            raise ValueError("pi contains NaN or Inf")
        row: dict[str, Any] = {
            "block_id": block_id, "block_x": bx, "block_y": by, "block_z": bz,
            "point_count": int(pi.size),
            "sij_sij_mean": float(source["sij_sij_mean"]),
        }
        covered = 0
        for pair_name, (left_codes, right_codes) in PAIR_SPECS.items():
            lb, lf, left_count = _directional_sums(pi, regime, left_codes)
            rb, rf, right_count = _directional_sums(pi, regime, right_codes)
            covered += left_count + right_count
            values = pair_asymmetry(lb, lf, rb, rf)
            row[f"pair_{pair_name}_left_count"] = left_count
            row[f"pair_{pair_name}_right_count"] = right_count
            for direction in DIRECTIONS:
                row[f"a_{pair_name}_{direction}"] = values[direction]
        row["classified_count"] = covered
        row["uncertain_count"] = int(pi.size) - covered
        output.append(row)
    return output


def _read_strain_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"block_id", "block_x", "block_y", "block_z", "sij_sij_mean"}
        missing = required.difference(reader.fieldnames or ())
        if missing:
            raise ValueError(f"strain CSV is missing columns: {', '.join(sorted(missing))}")
        return list(reader)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _write_figure(path: Path, rows: list[dict[str, Any]], title: str) -> None:
    figure = make_subplots(
        rows=2, cols=3,
        subplot_titles=(
            "Q1 vs Q4: backscatter", "Q1 vs Q4: forward", "Q1 vs Q4: total",
            "Q2 vs Q3: backscatter", "Q2 vs Q3: forward", "Q2 vs Q3: total",
        ),
        horizontal_spacing=0.06, vertical_spacing=0.14,
    )
    x = np.asarray([row["sij_sij_mean"] for row in rows], dtype=np.float64)
    custom = np.asarray([
        [row["block_id"], row["block_x"], row["block_y"], row["block_z"]]
        for row in rows
    ])
    panels = [(pair, direction) for pair in PAIR_SPECS for direction in DIRECTIONS]
    for panel, (pair_name, direction) in enumerate(panels):
        panel_row, panel_col = divmod(panel, 3)
        y = np.asarray([row[f"a_{pair_name}_{direction}"] for row in rows], dtype=np.float64)
        finite = np.isfinite(x) & np.isfinite(y) & (x > 0.0)
        figure.add_trace(
            go.Scattergl(
                x=x[finite], y=y[finite], customdata=custom[finite], mode="markers",
                marker={"size": 5, "opacity": 0.65}, showlegend=False,
                hovertemplate=(
                    "block_id=%{customdata[0]}<br>"
                    "block=(%{customdata[1]}, %{customdata[2]}, %{customdata[3]})<br>"
                    "mean SijSij=%{x:.7g}<br>A=%{y:.7g}<extra></extra>"
                ),
            ), row=panel_row + 1, col=panel_col + 1,
        )
        figure.add_hline(
            y=0.0, line_dash="dash", line_color="#666",
            row=panel_row + 1, col=panel_col + 1,
        )
        figure.update_yaxes(
            range=[-1.05, 1.05], title_text="A",
            row=panel_row + 1, col=panel_col + 1,
        )
        figure.update_xaxes(
            type="log", title_text="block mean SijSij",
            row=panel_row + 1, col=panel_col + 1,
        )
    figure.update_layout(title={"text": title, "x": 0.5}, width=1500, height=900)
    figure.write_html(
        path, include_plotlyjs=True, full_html=True,
        config={"responsive": True, "displaylogo": False},
    )


def run_regime_pair_asymmetry(
    cfg: PipelineConfig,
    time_index: int,
    sigma_grid: float,
    *,
    blocks_per_axis: int = 16,
    output_root: Path | str = Path("block_statistics/output"),
    overwrite: bool = False,
) -> Path:
    sigma = float(sigma_grid)
    result_dir = cfg.result_path(time_index, sigma)
    root = open_complete_result(result_dir)
    _validate_filter_metadata(cfg, sigma, root.attrs)
    for name in ("pi", "regime"):
        if name not in root or tuple(root[name].shape) != cfg.full_shape_zyx:
            raise RuntimeError(f"block regime asymmetry requires full-domain {name}")
    destination = Path(output_root) / result_dir.name
    strain_path = destination / f"block_statistics_{blocks_per_axis}x{blocks_per_axis}x{blocks_per_axis}.csv"
    if not strain_path.is_file():
        raise FileNotFoundError(f"run compute_block_statistics first: {strain_path}")
    csv_path = destination / "regime_pair_pi_asymmetry.csv"
    html_path = destination / "regime_pair_pi_asymmetry_vs_sij_sij.html"
    metadata_path = destination / "regime_pair_pi_asymmetry.json"
    if csv_path.is_file() and html_path.is_file() and metadata_path.is_file() and not overwrite:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        current = (
            metadata.get("source_strain_csv_sha256") == _sha256(strain_path)
            and metadata.get("result_manifest_hash") == root.attrs.get("manifest_hash")
        )
        if current:
            return html_path

    rows = compute_regime_pair_asymmetry(
        root["pi"], root["regime"], _read_strain_csv(strain_path), blocks_per_axis
    )
    _write_csv(csv_path, rows)
    _write_figure(html_path, rows, f"Regime-pair Pi asymmetry: {result_dir.name}")
    metadata = {
        "report_version": REPORT_VERSION,
        "status": "complete",
        "result_id": result_dir.name,
        "result_manifest_hash": root.attrs.get("manifest_hash"),
        "blocks_per_axis": blocks_per_axis,
        "block_count": len(rows),
        "sampling": "none",
        "sign_convention": {
            "backscatter": "pi > 0", "forward": "pi < 0, accumulated as -pi",
        },
        "regime_pairs": {
            "1_4": ["Q1=(1+,1-)", "Q4=(4+,4-)"], "2_3": ["Q2", "Q3"],
        },
        "definitions": {
            "backscatter": "(B_left-B_right)/(B_left+B_right)",
            "forward": "(F_left-F_right)/(F_left+F_right)",
            "total": "((B_left-F_left)-(B_right-F_right))/(B_left+F_left+B_right+F_right)",
            "zero_denominator": "NaN",
        },
        "source_strain_csv": str(strain_path.resolve()),
        "source_strain_csv_sha256": _sha256(strain_path),
        "csv": str(csv_path.resolve()),
        "html": str(html_path.resolve()),
    }
    temporary = metadata_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(metadata_path)
    return html_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plot six blockwise regime-pair Pi asymmetries against SijSij"
    )
    parser.add_argument("--config", default="configs/pipeline.yaml")
    parser.add_argument("--time-index", type=int, required=True)
    parser.add_argument("--sigma-grid", type=float, required=True)
    parser.add_argument("--filter-type", choices=FILTER_TYPES)
    parser.add_argument("--sharp-edge-width-fraction", type=float)
    parser.add_argument("--blocks-per-axis", type=int, default=16)
    parser.add_argument("--output-root", type=Path, default=Path("block_statistics/output"))
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    if args.filter_type is not None:
        cfg = cfg.with_filter(args.filter_type)
    if args.sharp_edge_width_fraction is not None:
        cfg = cfg.with_sharp_edge_width_fraction(args.sharp_edge_width_fraction)
    output = run_regime_pair_asymmetry(
        cfg, args.time_index, args.sigma_grid,
        blocks_per_axis=args.blocks_per_axis,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
