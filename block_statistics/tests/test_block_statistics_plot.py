from __future__ import annotations

import csv

from block_statistics.plot_vs_strain import (
    build_figure,
    load_and_sort_blocks,
    resolve_input_csv,
    visualize_block_statistics,
)


def _write_input(path) -> None:
    columns = [
        "block_id",
        "block_x",
        "block_y",
        "block_z",
        "sij_sij_mean",
        "work_resolved_mean",
        "work_full_mean",
        "pi_mean",
    ]
    rows = [
        [2, 0, 1, 0, 3.0, 20.0, 30.0, -2.0],
        [0, 0, 0, 0, 1.0, 10.0, 15.0, -1.0],
        [1, 1, 0, 0, 2.0, 12.0, 18.0, -1.5],
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)


def test_sort_and_figure_keep_every_block(tmp_path) -> None:
    source = tmp_path / "blocks.csv"
    _write_input(source)
    rows, _ = load_and_sort_blocks(source)
    assert [float(row["sij_sij_mean"]) for row in rows] == [1.0, 2.0, 3.0]
    assert [int(row["sij_sij_rank"]) for row in rows] == [1, 2, 3]
    figure = build_figure(rows, "test")
    marker_traces = [trace for trace in figure.data if trace.type == "scattergl"]
    assert len(marker_traces) == 3
    assert all(len(trace.x) == 3 for trace in marker_traces)


def test_visualization_writes_sorted_csv_and_html(tmp_path) -> None:
    source = tmp_path / "blocks.csv"
    _write_input(source)
    outputs = visualize_block_statistics(source)
    assert outputs["html"].is_file()
    assert outputs["sorted_csv"].is_file()
    assert outputs["metadata"].is_file()


def test_result_directory_resolves_default_csv(tmp_path) -> None:
    source = tmp_path / "block_statistics_16x16x16.csv"
    _write_input(source)
    assert resolve_input_csv(tmp_path) == source
    rows, _ = load_and_sort_blocks(tmp_path)
    assert len(rows) == 3
