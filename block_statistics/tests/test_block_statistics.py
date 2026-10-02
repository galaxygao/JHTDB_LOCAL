from __future__ import annotations

import numpy as np
import pytest
import zarr

from block_statistics.compute_block_statistics import (
    block_moments,
    strain_contraction_block_sums,
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
