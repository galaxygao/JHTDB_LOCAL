from __future__ import annotations

import math

import numpy as np

from block_statistics.regime_pair_asymmetry import (
    compute_regime_pair_asymmetry, normalized_difference, pair_asymmetry,
)


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
