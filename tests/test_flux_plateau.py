from __future__ import annotations

import unittest
from pathlib import Path

from flux_plateau.plot_pi_epsilon_vs_k import (
    build_flux_points,
    make_figure,
    make_log_k_figure,
)


class FluxPlateauTests(unittest.TestCase):
    def test_forward_sign_and_log_axis(self) -> None:
        records = [
            (
                Path("relative_sigma_10"),
                {
                    "sigma_grid": 10.0,
                    "filter_type": "smooth_sharp",
                    "sharp_edge_width_fraction": 0.1171875,
                },
                {"global": {"field_means": {"pi": -0.8}}},
            ),
        ]
        points = build_flux_points(
            records,
            grid_size=1024,
            domain_length=2.0 * 3.141592653589793,
            epsilon_reference=1.0,
            eta_reference=0.00287,
        )
        relative = [
            point for point in points if point.group_key[0] == "fraction_of_cutoff"
        ]
        self.assertEqual(len(relative), 1)
        self.assertTrue(
            all(
                point.forward_mean_pi > 0
                for point in points
                if point.note != "paper data"
            )
        )

        figure = make_figure(points, epsilon_reference=1.0)
        self.assertEqual(figure.layout.xaxis.type, "linear")
        self.assertEqual(figure.layout.yaxis.type, "linear")
        self.assertEqual(
            figure.layout.xaxis.title.text,
            "Gaussian-equivalent scale r_eq / η (linear)",
        )
        self.assertEqual(figure.layout.yaxis.title.text, "<Π_forward> / ε")
        self.assertIn("Paper reference", {trace.name for trace in figure.data})

        log_k_figure = make_log_k_figure(points, epsilon_reference=1.0)
        self.assertEqual(log_k_figure.layout.xaxis.type, "log")
        self.assertEqual(log_k_figure.layout.yaxis.type, "linear")
        self.assertEqual(
            log_k_figure.layout.xaxis.title.text,
            "half-gain wavenumber k_1/2 (log scale)",
        )

    def test_gaussian_uses_its_half_gain_wavenumber(self) -> None:
        records = [
            (
                Path("gaussian_sigma_2"),
                {"sigma_grid": 2.0, "filter_type": "gaussian"},
                {"global": {"field_means": {"pi": -0.5}}},
            )
        ]
        points = build_flux_points(
            records,
            grid_size=1024,
            domain_length=2.0 * 3.141592653589793,
            epsilon_reference=1.0,
            eta_reference=0.00287,
        )
        gaussian = next(point for point in points if point.group_key[0] == "gaussian")
        expected = (2.0 * 0.6931471805599453) ** 0.5 / (
            2.0 * (2.0 * 3.141592653589793 / 1024)
        )
        self.assertAlmostEqual(gaussian.cutoff_wavenumber, expected)
        self.assertAlmostEqual(
            gaussian.equivalent_r_over_eta,
            14.8121681530451,
        )


if __name__ == "__main__":
    unittest.main()
