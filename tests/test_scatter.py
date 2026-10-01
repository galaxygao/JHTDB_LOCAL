from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import zarr

from scatter.plot_exact_scatter import (
    density_figure,
    exact_density_histogram,
    exact_density_histograms,
    exact_feature_bounds,
    iter_exact_feature_chunks,
    nice_axis_limits,
    pdf_display_scale,
    probability_density,
    top_pdf_mask,
    write_outputs,
)


class ExactScatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = zarr.group()
        shape = (2, 2, 2)
        chunks = (1, 2, 2)
        s_bar = np.arange(8, dtype="<f4").reshape(shape) - 4.0
        pi = np.arange(8, dtype="<f4").reshape(shape) - 4.0
        work_resolved = np.arange(8, dtype="<f4").reshape(shape)
        work_full = work_resolved + np.arange(8, dtype="<f4").reshape(shape) * 2.0
        for name, values in {
            "s_bar": s_bar,
            "pi": pi,
            "work_full": work_full,
            "work_resolved": work_resolved,
        }.items():
            self.root.create_dataset(name, data=values, chunks=chunks, dtype="<f4")

    def test_exact_chunk_iterator_keeps_sign_and_every_point(self) -> None:
        chunks = list(iter_exact_feature_chunks(self.root))
        self.assertEqual(sum(chunk.point_count for chunk in chunks), 8)
        matrix = np.concatenate([chunk.matrix() for chunk in chunks])
        np.testing.assert_array_equal(matrix[:, 0], np.arange(8) * 3.0)
        np.testing.assert_array_equal(matrix[:, 1], np.arange(8) - 4.0)
        np.testing.assert_array_equal(matrix[:, 2], -(np.arange(8) - 4.0))
        matrix_with_delta = np.concatenate(
            [chunk.matrix_with_delta_w() for chunk in chunks]
        )
        np.testing.assert_array_equal(matrix_with_delta[:, 3], np.arange(8) * 2.0)

    def test_histogram_has_exact_point_count_closure(self) -> None:
        bounds = exact_feature_bounds(self.root)
        density, edges, point_count = exact_density_histogram(
            self.root, bounds, bins=4
        )
        self.assertEqual(point_count, 8)
        self.assertEqual(int(density.sum()), 8)
        self.assertEqual(density.dtype, np.uint64)
        self.assertEqual(density.shape, (4, 4, 4))
        self.assertEqual(tuple(len(edge) for edge in edges), (5, 5, 5))
        self.assertEqual((edges[0][0], edges[0][-1]), (0.0, 21.0))
        self.assertEqual((edges[1][0], edges[1][-1]), (-4.0, 3.0))
        self.assertEqual((edges[2][0], edges[2][-1]), (-3.0, 4.0))
        pdf, integral = probability_density(density, edges)
        self.assertAlmostEqual(integral, 1.0)
        occupied = density != 0
        display, _, _ = pdf_display_scale(pdf, occupied)
        self.assertTrue(np.all(display[~occupied] == -1.0))
        self.assertTrue(
            np.all((display[occupied] >= 0.0) & (display[occupied] <= 1.0))
        )
        top, threshold = top_pdf_mask(pdf)
        self.assertTrue(np.all(pdf[top] >= threshold))
        rounded = nice_axis_limits(-0.0034, 0.0081)
        self.assertLess(rounded[0], -0.0034)
        self.assertGreater(rounded[1], 0.0081)

    def test_figure_contains_3d_cloud_2d_density_and_delta_boundary(self) -> None:
        bounds = exact_feature_bounds(self.root)
        density, edges, density_2d, edges_2d, point_count = exact_density_histograms(
            self.root, bounds, bins_3d=4, bins_2d=8
        )
        figure = density_figure(
            density,
            edges,
            density_2d=density_2d,
            edges_2d=edges_2d,
            title="test",
        )
        self.assertEqual(
            [trace.type for trace in figure.data],
            [
                "volume",
                "heatmap",
                "scatter",
                "surface",
                "surface",
                "surface",
                "scatter3d",
                "scatter3d",
                "scatter3d",
                "volume",
                "heatmap",
            ],
        )
        self.assertEqual(len(figure.data[0].x), density.size)
        rendered_3d = np.asarray(figure.data[0].value)
        self.assertTrue(np.all(rendered_3d[density.ravel() == 0] == -1.0))
        self.assertTrue(
            np.all(
                (rendered_3d[density.ravel() != 0] >= 0.0)
                & (rendered_3d[density.ravel() != 0] <= 1.0)
            )
        )
        custom_2d = np.asarray(figure.data[1].customdata)
        self.assertEqual(int(custom_2d[..., 0].sum()), point_count)
        self.assertEqual(custom_2d.shape, (8, 8, 2))
        rendered_2d = np.asarray(figure.data[1].z)
        self.assertTrue(np.all(np.isnan(rendered_2d[density_2d.T == 0])))
        _, integral_2d = probability_density(density_2d, edges_2d)
        self.assertAlmostEqual(integral_2d, 1.0)
        self.assertEqual(figure.data[2].name, "ΔW = 0")
        self.assertEqual(
            [trace.name for trace in figure.data[3:6]],
            [
                "W_full = 0",
                "ΔW = S̄ + Π_LES = 0",
                "W_res = W_full - S̄ - Π_LES = 0",
            ],
        )
        self.assertEqual(
            [trace.name for trace in figure.data[6:9]],
            ["x-axis: W_full", "y-axis: S̄", "z-axis: Π_LES"],
        )
        np.testing.assert_allclose(figure.data[3].x, 0.0)
        np.testing.assert_allclose(
            np.asarray(figure.data[4].y) + np.asarray(figure.data[4].z), 0.0
        )
        residual = (
            np.asarray(figure.data[5].x)
            - np.asarray(figure.data[5].y)
            - np.asarray(figure.data[5].z)
        )
        np.testing.assert_allclose(residual[np.isfinite(residual)], 0.0)
        self.assertTrue(
            figure.layout.scene.xaxis.title.text.startswith("x: W_full<br>data=[")
        )
        self.assertTrue(
            figure.layout.scene.yaxis.title.text.startswith("y: S̄<br>data=[")
        )
        self.assertTrue(
            figure.layout.scene.zaxis.title.text.startswith(
                "z: Π_LES = -τ:S<br>data=["
            )
        )
        self.assertTrue(figure.layout.xaxis.title.text.startswith("x: S̄; data=["))
        self.assertTrue(
            figure.layout.yaxis.title.text.startswith("y: Π_LES = -τ:S; data=[")
        )
        self.assertEqual(figure.layout.yaxis.scaleanchor, "x")
        self.assertTrue(figure.layout.scene.xaxis.zeroline)
        self.assertEqual(figure.layout.scene.xaxis.zerolinecolor, "#d62728")
        self.assertFalse(figure.data[9].visible)
        self.assertFalse(figure.data[10].visible)
        self.assertEqual(len(figure.layout.updatemenus), 2)
        self.assertEqual(figure.layout.updatemenus[0].buttons[0].label, "3-D top 5% ON")
        self.assertEqual(figure.layout.updatemenus[1].buttons[0].label, "2-D top 5% ON")
        self.assertEqual(figure.layout.updatemenus[0].xanchor, "right")
        self.assertEqual(figure.layout.updatemenus[1].xanchor, "right")
        self.assertGreater(float(figure.layout.updatemenus[0].x), 0.9)
        self.assertEqual(float(figure.data[0].colorbar.x), 0.965)
        subplot_gap = float(figure.layout.scene.domain.y[0]) - float(
            figure.layout.yaxis.domain[1]
        )
        self.assertGreaterEqual(subplot_gap, 0.12)
        scene_height = float(figure.layout.scene.domain.y[1]) - float(
            figure.layout.scene.domain.y[0]
        )
        heatmap_height = float(figure.layout.yaxis.domain[1]) - float(
            figure.layout.yaxis.domain[0]
        )
        self.assertGreaterEqual(scene_height / heatmap_height, 2.9)
        with tempfile.TemporaryDirectory() as temporary:
            paths = write_outputs(
                Path(temporary),
                density,
                edges,
                {
                    "time_index": 1,
                    "sigma_grid": 2.0,
                    "point_count": point_count,
                },
                density_2d=density_2d,
                edges_2d=edges_2d,
            )
            self.assertTrue(all(path.is_file() for path in paths))
            with np.load(paths[1]) as stored:
                self.assertEqual(stored["density_3d"].shape, (4, 4, 4))
                self.assertEqual(stored["density_2d"].shape, (8, 8))
                self.assertEqual(stored["pdf_3d"].shape, (4, 4, 4))
                self.assertEqual(stored["pdf_2d"].shape, (8, 8))


if __name__ == "__main__":
    unittest.main()
