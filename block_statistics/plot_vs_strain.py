from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PLOT_VERSION = 1
X_COLUMN = "sij_sij_mean"
Y_FIELDS = (
    ("work_resolved_mean", "W_res", "#1f77b4"),
    ("work_full_mean", "W_full", "#ff7f0e"),
    ("pi_mean", "Pi", "#2ca02c"),
)
REQUIRED_COLUMNS = {
    "block_id",
    "block_x",
    "block_y",
    "block_z",
    X_COLUMN,
    *(name for name, _, _ in Y_FIELDS),
}


def resolve_input_csv(path: Path | str) -> Path:
    """Accept either a block-statistics CSV or its containing result directory."""
    source = Path(path)
    if source.is_dir():
        preferred = source / "block_statistics_16x16x16.csv"
        if preferred.is_file():
            return preferred
        candidates = sorted(source.glob("block_statistics_*x*x*.csv"))
        candidates = [
            candidate
            for candidate in candidates
            if "sorted_by_sij_sij" not in candidate.name
        ]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise FileNotFoundError(
                f"no block-statistics CSV found in {source}; run "
                "compute_block_statistics.py for this result first"
            )
        raise ValueError(
            f"multiple block-statistics CSV files found in {source}; "
            "pass the desired CSV path explicitly"
        )
    if not source.is_file():
        raise FileNotFoundError(f"block-statistics CSV does not exist: {source}")
    return source


def load_and_sort_blocks(csv_path: Path | str) -> tuple[list[dict[str, str]], list[str]]:
    """Load all blocks and return them in ascending block-mean S_ij S_ij order."""
    path = resolve_input_csv(csv_path)
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = list(reader.fieldnames or ())
        missing = sorted(REQUIRED_COLUMNS - set(columns))
        if missing:
            raise ValueError(f"block CSV is missing columns: {', '.join(missing)}")
        rows = list(reader)
    if not rows:
        raise ValueError("block CSV contains no rows")
    for row in rows:
        values = [float(row[X_COLUMN]), *(float(row[name]) for name, _, _ in Y_FIELDS)]
        if not np.all(np.isfinite(values)):
            raise ValueError("block CSV contains NaN or Inf")
    rows.sort(key=lambda row: (float(row[X_COLUMN]), int(row["block_id"])))
    for rank, row in enumerate(rows, start=1):
        row["sij_sij_rank"] = str(rank)
    return rows, columns


def write_sorted_blocks(
    rows: list[dict[str, str]], original_columns: list[str], output_path: Path | str
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["sij_sij_rank", *original_columns]
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)
    return path


def _custom_data(rows: list[dict[str, str]]) -> np.ndarray:
    return np.asarray(
        [
            [
                int(row["sij_sij_rank"]),
                int(row["block_id"]),
                int(row["block_x"]),
                int(row["block_y"]),
                int(row["block_z"]),
            ]
            for row in rows
        ],
        dtype=np.int64,
    )


def build_figure(rows: list[dict[str, str]], title: str) -> go.Figure:
    strain = np.asarray([float(row[X_COLUMN]) for row in rows], dtype=np.float64)
    custom = _custom_data(rows)
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.075,
        subplot_titles=[
            "W_res versus S_ij S_ij",
            "W_full versus S_ij S_ij",
            "Pi versus S_ij S_ij",
        ],
    )
    for panel, (field, label, color) in enumerate(Y_FIELDS, start=1):
        values = np.asarray([float(row[field]) for row in rows], dtype=np.float64)
        figure.add_trace(
            go.Scattergl(
                x=strain,
                y=values,
                mode="markers",
                name=label,
                marker={"size": 6, "color": color, "opacity": 0.68},
                customdata=custom,
                hovertemplate=(
                    "S rank=%{customdata[0]}<br>"
                    "block_id=%{customdata[1]}<br>"
                    "block (x,y,z)=(%{customdata[2]}, %{customdata[3]}, %{customdata[4]})<br>"
                    "mean S_ij S_ij=%{x:.7g}<br>"
                    f"mean {label}=%{{y:.7g}}<extra>{label}</extra>"
                ),
            ),
            row=panel,
            col=1,
        )
        figure.add_hline(
            y=0.0,
            line={"color": "#555", "width": 1, "dash": "dash"},
            row=panel,
            col=1,
        )
        figure.update_yaxes(title_text=f"block mean {label}", row=panel, col=1)
    figure.update_xaxes(
        title_text="block mean S_ij S_ij (ascending)", row=3, col=1
    )
    figure.update_layout(
        title={"text": title, "x": 0.5},
        height=1450,
        width=1150,
        template="plotly_white",
        hovermode="closest",
        legend={"orientation": "h", "x": 0.5, "xanchor": "center", "y": 1.015},
        margin={"l": 105, "r": 45, "t": 105, "b": 80},
    )
    return figure


def visualize_block_statistics(
    csv_path: Path | str,
    *,
    output_dir: Path | str | None = None,
) -> dict[str, Path]:
    """Sort blocks by mean strain contraction and plot all block-level pairs."""
    source = resolve_input_csv(csv_path)
    destination = Path(output_dir) if output_dir is not None else source.parent
    destination.mkdir(parents=True, exist_ok=True)
    rows, columns = load_and_sort_blocks(source)
    sorted_path = write_sorted_blocks(
        rows, columns, destination / "block_statistics_sorted_by_sij_sij.csv"
    )
    html_path = destination / "quantities_vs_sij_sij.html"
    figure = build_figure(rows, f"Block distributions: {source.parent.name}")
    figure.write_html(
        html_path,
        include_plotlyjs="cdn",
        full_html=True,
        config={"displaylogo": False, "scrollZoom": True},
    )
    metadata_path = destination / "visualization_metadata.json"
    metadata: dict[str, Any] = {
        "plot_version": PLOT_VERSION,
        "status": "complete",
        "source_csv": str(source.resolve()),
        "sorted_csv": str(sorted_path.resolve()),
        "html": str(html_path.resolve()),
        "block_count": len(rows),
        "sampling": "none; every CSV block is plotted",
        "sort": {"field": X_COLUMN, "direction": "ascending"},
        "x_axis": X_COLUMN,
        "y_axes": [name for name, _, _ in Y_FIELDS],
        "point_representation": "one marker per 64^3 block; values are block means",
    }
    temporary = metadata_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(metadata_path)
    return {"html": html_path, "sorted_csv": sorted_path, "metadata": metadata_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plot W_res, W_full and Pi against block-mean S_ij S_ij"
    )
    parser.add_argument(
        "--input-csv",
        "--input",
        dest="input_csv",
        type=Path,
        required=True,
        help="block CSV path or its containing result directory",
    )
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outputs = visualize_block_statistics(args.input_csv, output_dir=args.output_dir)
    print(json.dumps({name: str(path.resolve()) for name, path in outputs.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
