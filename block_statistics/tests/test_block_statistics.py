from __future__ import annotations

import csv
import math

import numpy as np
import pytest
import zarr

from block_statistics.compute_block_statistics import (
    block_moments,
    strain_contraction_block_sums,
)
from block_statistics.plot_vs_strain import (
    build_figure,
    load_and_sort_blocks,
    resolve_input_csv,
    visualize_block_statistics,
)
from block_statistics.regime_pair_asymmetry import (
    compute_regime_pair_asymmetry, normalized_difference, pair_asymmetry,
)
from jhtdb_pipeline.strain import _accumulate


def test_block_moments_uses_every_point() -> None:
    field = np.arange(8 * 8 * 8, dtype=np.float32).reshape(8, 8, 8)
    report = block_moments(field, 2)
    assert report["block_shape_zyx"] == (4, 4, 4)
    assert report["point_count"] == 64
    for bz in range(2):
        for by in range(2):
            for bx in range(2):
                values = field[
                    bz * 4 : (bz + 1) * 4,
                    by * 4 : (by + 1) * 4,
                    bx * 4 : (bx + 1) * 4,
                ]
                index = (bz, by, bx)
                assert report["sum"][index] == pytest.approx(values.sum(dtype=np.float64))
                assert report["mean"][index] == pytest.approx(values.mean(dtype=np.float64))

def test_strain_contraction_counts_off_diagonal_twice() -> None:
    gradient = np.zeros((3, 3, 4, 4, 4), dtype=np.float32)
    gradient[0, 0] = 1.0
    gradient[1, 1] = 2.0
    gradient[2, 2] = 3.0
    gradient[0, 1] = 4.0
    gradient[1, 0] = 6.0
    # Diagonal: 1 + 4 + 9. S01=S10=5, hence +2*25.
    expected_per_point = 64.0
    sums = strain_contraction_block_sums(gradient, 2)
    assert sums.shape == (2, 2, 2)
    assert np.all(sums == pytest.approx(expected_per_point * 8))

def test_block_partition_must_divide_domain() -> None:
    with pytest.raises(ValueError, match="divisible"):
        block_moments(np.zeros((5, 4, 4), dtype=np.float32), 2)

def test_shared_strain_field_accumulates_full_contraction(tmp_path) -> None:
    root = zarr.open_group(str(tmp_path / "strain.zarr"), mode="w")
    destination = root.create_dataset(
        "sij_sij", shape=(2, 2, 2), chunks=(1, 1, 1), dtype="<f4", fill_value=0
    )
    diagonal = np.full((2, 2, 2), 3.0, dtype=np.float32)
    left = np.full((2, 2, 2), 4.0, dtype=np.float32)
    right = np.full((2, 2, 2), 6.0, dtype=np.float32)
    _accumulate(destination, diagonal)
    _accumulate(destination, left, pair=right)
    # S_ii^2 + 2*S_ij^2 = 3^2 + 0.5*(4+6)^2 = 59.
    assert np.array_equal(np.asarray(destination[:]), np.full((2, 2, 2), 59.0))

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

def test_pair_asymmetry_is_bounded_and_uses_signed_total() -> None:
    values = pair_asymmetry(6.0, 2.0, 2.0, 4.0)
    assert values["backscatter"] == 0.5
    assert values["forward"] == -1.0 / 3.0
    assert values["total"] == 3.0 / 7.0
    assert math.isnan(normalized_difference(0.0, 0.0))

def test_block_regime_pair_asymmetry_aggregates_v6_to_legacy_pairs() -> None:
    regime = np.asarray([1, 2, 5, 6, 3, 3, 4, 4], dtype=np.uint8).reshape(2, 2, 2)
    pi = np.asarray([4, -2, 2, -4, 3, -1, 1, -3], dtype=np.float32).reshape(2, 2, 2)
    strain_rows = [{
        "block_id": "0", "block_x": "0", "block_y": "0", "block_z": "0",
        "sij_sij_mean": "7.5",
    }]
    row = compute_regime_pair_asymmetry(pi, regime, strain_rows, divisions=1)[0]
    assert row["a_1_4_backscatter"] == (4.0 - 2.0) / 6.0
    assert row["a_1_4_forward"] == (2.0 - 4.0) / 6.0
    assert row["a_1_4_total"] == ((4.0 - 2.0) - (2.0 - 4.0)) / 12.0
    assert row["a_2_3_backscatter"] == 0.5
    assert row["a_2_3_forward"] == -0.5
    assert row["a_2_3_total"] == 0.5
    assert row["classified_count"] == 8
    assert row["uncertain_count"] == 0
