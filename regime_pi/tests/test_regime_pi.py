from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import zarr

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.regime_pi import compute_regime_pi_statistics


def test_regime_pi_mean_fraction_and_intensity_definitions(tmp_path: Path) -> None:
    cfg = replace(
        load_config("configs/pipeline.yaml"),
        grid_shape=(2, 2, 3),


        state_root=tmp_path / "state",
        run_root=tmp_path / "runs",
        result_root=tmp_path / "results",
    )
    # Two points per regime: one backscatter and one forward point.
    full_pairs = [(2, 2), (1, 1), (1, 1), (-1, -1), (-1, -1), (-2, -2)]
    resolved_pairs = [(1, 1), (2, 2), (-1, -1), (1, 1), (-2, -2), (-1, -1)]
    full = np.asarray([v for pair in full_pairs for v in pair], dtype="<f4").reshape(3, 2, 2)
    resolved = np.asarray([v for pair in resolved_pairs for v in pair], dtype="<f4").reshape(3, 2, 2)
    pi_values = []
    for scale in range(1, 7):
        pi_values.extend((float(scale), float(-2 * scale)))
    pi = np.asarray(pi_values, dtype="<f4").reshape(3, 2, 2)
    root = zarr.group()
    root.create_dataset("pi", data=pi, chunks=(1, 2, 2), dtype="<f4")
    root.create_dataset("work_full", data=full, chunks=(1, 2, 2), dtype="<f4")
    root.create_dataset("work_resolved", data=resolved, chunks=(1, 2, 2), dtype="<f4")

    report = compute_regime_pi_statistics(root, cfg)
    assert report["passed"]
    assert report["coverage"]["regime_point_count"] == 12
    for scale, regime in enumerate(report["regime_order"], start=1):
        item = report["regimes"][regime]
        backscatter = item["directions"]["backscatter"]
        forward = item["directions"]["forward"]
        assert item["count"] == 2
        assert backscatter["mean"] == scale
        assert backscatter["fraction"] == 0.5
        assert backscatter["intensity"] == scale / 2
        assert forward["mean"] == 2 * scale
        assert forward["fraction"] == 0.5
        assert forward["intensity"] == scale
        assert item["signed_pi_mean"] == -scale / 2
        assert item["closure"]["residual_sum"] == 0.0
