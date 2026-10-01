from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import zarr

from pi_pdf.plot_pi_pdf import (
    PiReferenceStatistics,
    analyze_pi_array,
    central_pdf_figure,
    common_edges,
    contribution_figure,
    write_outputs,
)


class PiPdfTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pi_les = np.array(
            [-8.0, -2.0, -1.0, 0.0, 0.25, 0.5, 1.0, 16.0], dtype=np.float32
        ).reshape(2, 2, 2)
        self.root = zarr.group()
        self.root.create_dataset("pi", data=-self.pi_les, chunks=(1, 2, 2), dtype="<f4")
        flat = self.pi_les.reshape(-1).astype(np.float64)
        self.reference = PiReferenceStatistics(
            sigma=2.0,
            point_count=flat.size,
            pi_les_mean=float(flat.mean()),
            pi_rms=float(np.sqrt(np.mean(np.square(flat)))),
            abs_pi_p99=float(np.quantile(np.abs(flat), 0.99)),
            abs_pi_max=float(np.max(np.abs(flat))),
            forward_count=int(np.count_nonzero(flat > 0)),
            backscatter_count=int(np.count_nonzero(flat < 0)),
            zero_count=int(np.count_nonzero(flat == 0)),
            source_path=Path("synthetic/weak_asymmetry.json"),
        )

    def test_all_point_and_pdf_closures(self) -> None:
        edges = common_edges(
            [self.reference], central_bins=32, tail_bins=32, tail_minimum=1e-6
        )
        result = analyze_pi_array(self.root["pi"], self.reference, edges)
        self.assertEqual(result["point_count"], self.pi_les.size)
        self.assertEqual(int(result["absolute_count"].sum()), self.pi_les.size)
        self.assertEqual(result["forward_count_total"], 4)
        self.assertEqual(result["backscatter_count_total"], 3)
        self.assertEqual(result["zero_count_total"], 1)
        self.assertAlmostEqual(result["tail_count_integral"], 1.0)
        self.assertAlmostEqual(result["signed_closure"], float(self.pi_les.mean()))
        self.assertAlmostEqual(
            result["absolute_closure"], float(np.abs(self.pi_les).mean())
        )

    def test_figures_and_machine_outputs(self) -> None:
        edges = common_edges(
            [self.reference], central_bins=32, tail_bins=32, tail_minimum=1e-6
        )
        result = analyze_pi_array(self.root["pi"], self.reference, edges)
        figure = central_pdf_figure({2.0: result}, edges["normalized"], normalized=True)
        self.assertEqual(len(figure.data), 1)
        self.assertEqual(figure.layout.yaxis.type, "log")
        with tempfile.TemporaryDirectory() as temporary:
            paths = write_outputs(
                Path(temporary),
                {2.0: self.reference},
                {2.0: result},
                edges,
                time_index=1,
                chunk_limit=None,
            )
            self.assertTrue(all(path.is_file() for path in paths))
            with np.load(Path(temporary) / "sigma_2" / "pi_pdf.npz") as stored:
                self.assertEqual(int(stored["absolute_count"].sum()), self.pi_les.size)

    def test_contribution_figure_contains_linear_threshold_gradients(self) -> None:
        edges = common_edges(
            [self.reference], central_bins=32, tail_bins=32, tail_minimum=1e-6
        )
        result = analyze_pi_array(self.root["pi"], self.reference, edges)
        figure = contribution_figure({2.0: result}, edges["absolute_normalized"])
        self.assertEqual(len(figure.data), 5)
        self.assertEqual(figure.layout.xaxis3.type, "log")
        self.assertEqual(figure.layout.yaxis3.type, "log")
        expected = -np.gradient(
            np.cumsum(result["absolute_sum"][::-1])[::-1][1:]
            / np.sum(result["absolute_sum"]),
            edges["absolute_normalized"][1:-1],
        )
        np.testing.assert_allclose(
            np.asarray(figure.data[-1].y, dtype=np.float64),
            np.where(expected > 0.0, expected, np.nan),
            equal_nan=True,
        )


if __name__ == "__main__":
    unittest.main()
