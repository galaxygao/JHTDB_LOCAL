from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import zarr

from pi_pdf.validate_log_pi_gaussian import analyze_pi_root, write_outputs


class LogPiGaussianTests(unittest.TestCase):
    def test_weighted_moments_and_outputs(self) -> None:
        rng = np.random.default_rng(7)
        y = rng.normal(0.2, 0.35, size=5000)
        magnitude = np.power(10.0, y).astype(np.float32)
        signs = np.where(rng.random(size=y.size) > 0.25, 1.0, -1.0)
        pi_les = (magnitude * signs).astype("<f4").reshape(10, 10, 50)
        root = zarr.group()
        root.create_dataset("pi", data=-pi_les, chunks=(2, 5, 10), dtype="<f4")
        edges = np.linspace(-3.0, 3.0, 401)
        result = analyze_pi_root(
            root["pi"], rms=float(np.sqrt(np.mean(np.square(pi_les)))),
            point_count_expected=pi_les.size, y_edges=edges
        )
        self.assertEqual(result["point_count"], pi_les.size)
        self.assertEqual(result["sign_counts"]["forward"] + result["sign_counts"]["backscatter"], pi_les.size)
        self.assertGreater(result["forward"]["contribution_area"], 0.0)
        self.assertGreater(result["backscatter"]["contribution_area"], 0.0)
        self.assertTrue(np.isfinite(result["forward"]["mu_log10_abs_pi_over_rms"]))
        with tempfile.TemporaryDirectory() as temporary:
            write_outputs(Path(temporary), {2.0: result}, time_index=1, chunk_limit=None)
            self.assertTrue((Path(temporary) / "log_pi_contribution_cdf.html").is_file())
            self.assertTrue((Path(temporary) / "log_pi_gaussian_parameters.csv").is_file())


if __name__ == "__main__":
    unittest.main()
