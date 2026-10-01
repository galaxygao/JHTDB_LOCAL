from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from jhtdb_pipeline.physics import (
    ARRAY_AXIS_FOR_DERIVATIVE,
    axis2_spectrum,
    close_memmap,
    derivative_field,
    filter_field,
    filter_field_from_axis2_spectrum,
    filter_smooth_sharp_field,
    full_spectrum,
    memmap,
    legacy_regime_codes,
    regime_codes,
    spectral_derivative,
    spectral_gaussian,
    smooth_sharp_radial_weights,
)


class PhysicsTests(unittest.TestCase):
    def test_periodic_spectral_derivative(self) -> None:
        n = 64
        x = np.arange(n, dtype=np.float32) * (2.0 * np.pi / n)
        derivative = spectral_derivative(np.sin(3.0 * x), 0, 2.0 * np.pi)
        np.testing.assert_allclose(
            derivative, 3.0 * np.cos(3.0 * x), rtol=2e-5, atol=2e-5
        )

    def test_periodic_gaussian_preserves_constant(self) -> None:
        field = np.ones((16, 16, 16), dtype=np.float32)
        np.testing.assert_allclose(
            spectral_gaussian(field, 1.0), field, rtol=0, atol=1e-6
        )

    def test_regime_codes(self) -> None:
        full = np.asarray([3.0, 2.0, 2.0, -2.0, -2.0, -3.0, 0.0])
        resolved = np.asarray([2.0, 3.0, -2.0, 2.0, -3.0, -2.0, 1.0])
        codes, _, _ = regime_codes(full, resolved, 0.1, 0.0)
        np.testing.assert_array_equal(codes, [1, 2, 3, 4, 5, 6, 0])
        np.testing.assert_array_equal(
            legacy_regime_codes(codes), [1, 1, 2, 3, 4, 4, 0]
        )

    def test_full_spectrum_matches_direct_three_dimensional_fft(self) -> None:
        rng = np.random.default_rng(14)
        field = rng.standard_normal((8, 8, 8)).astype(np.float32)
        actual = full_spectrum(field, 2, workers=2)
        expected = np.fft.rfftn(field).astype(np.complex64)
        np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=2e-5)

    def test_smooth_sharp_edge_and_full_periodic_filter(self) -> None:
        weights = smooth_sharp_radial_weights(
            np.asarray([0.0, 3.0, 4.0, 5.0, 20.0]), 4.0, 0.25
        )
        self.assertEqual(float(weights[0]), 1.0)
        self.assertAlmostEqual(float(weights[2]), 0.5)
        self.assertTrue(np.all(np.diff(weights) <= 0))

        n = 32
        coordinates = np.arange(n, dtype=np.float32) * (2.0 * np.pi / n)
        z, y, x = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
        low = np.sin(2 * x + 3 * y)
        high = np.sin(12 * x)
        output = np.empty_like(low, dtype=np.float32)
        filter_smooth_sharp_field(
            low + high,
            output,
            sigma_grid=2.0,
            domain_length=2.0 * np.pi,
            edge_width_fraction=0.03125,
            slab=4,
            workers=2,
        )
        np.testing.assert_allclose(output, low, rtol=3e-5, atol=3e-5)

    def test_smooth_sharp_has_half_gain_at_cutoff_and_is_isotropic(self) -> None:
        n = 32
        coordinates = np.arange(n, dtype=np.float32) * (2.0 * np.pi / n)
        z, y, x = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
        # sigma=2 gives k_c=N/(2*sigma)=8 for a 2*pi domain.
        cutoff_modes = np.cos(8 * x) + np.cos(8 * y) + np.cos(8 * z)
        output = np.empty_like(cutoff_modes, dtype=np.float32)
        filter_smooth_sharp_field(
            cutoff_modes,
            output,
            sigma_grid=2.0,
            domain_length=2.0 * np.pi,
            edge_width_fraction=0.0625,
            slab=4,
            workers=2,
        )
        np.testing.assert_allclose(
            output,
            0.5 * cutoff_modes,
            rtol=3e-5,
            atol=3e-5,
        )

    def test_zero_delta_is_assigned_to_plus_partition(self) -> None:
        full = np.asarray([2.0, -2.0])
        resolved = np.asarray([2.0, -2.0])
        codes, _, _ = regime_codes(full, resolved, 0.1, 0.0)
        np.testing.assert_array_equal(codes, [1, 5])

    def test_all_gradient_axes(self) -> None:
        self.assertEqual(ARRAY_AXIS_FOR_DERIVATIVE, (2, 1, 0))
        n = 24
        coordinates = np.arange(n, dtype=np.float32) * (2.0 * np.pi / n)
        z, y, x = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
        field = np.sin(x) + 0.5 * np.cos(2 * y) + 0.25 * np.sin(3 * z)
        expected = (np.cos(x), -np.sin(2 * y), 0.75 * np.cos(3 * z))
        with tempfile.TemporaryDirectory() as temporary:
            output = memmap(Path(temporary) / "derivative.f32", field.shape)
            try:
                for component in range(3):
                    derivative_field(field, output, component, 2.0 * np.pi, slab=3)
                    np.testing.assert_allclose(
                        output, expected[component], rtol=3e-5, atol=3e-5
                    )
            finally:
                close_memmap(output)

    def test_streaming_filter_matches_in_memory_filter(self) -> None:
        n = 16
        rng = np.random.default_rng(7)
        field = rng.normal(size=(n, n, n)).astype(np.float32)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = memmap(root / "output.f32", field.shape)
            temp_a = memmap(root / "a.f32", field.shape)
            temp_b = memmap(root / "b.f32", field.shape)
            try:
                filter_field(field, output, temp_a, temp_b, 1.0, slab=2, workers=2)
                np.testing.assert_allclose(
                    output, spectral_gaussian(field, 1.0), rtol=2e-5, atol=2e-6
                )
            finally:
                close_memmap(output)
                close_memmap(temp_a)
                close_memmap(temp_b)

    def test_cached_first_axis_spectrum_matches_streaming_filter(self) -> None:
        n = 16
        rng = np.random.default_rng(11)
        field = rng.normal(size=(n, n, n)).astype(np.float32)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = memmap(root / "expected.f32", field.shape)
            actual = memmap(root / "actual.f32", field.shape)
            temp_a = memmap(root / "a.f32", field.shape)
            temp_b = memmap(root / "b.f32", field.shape)
            try:
                filter_field(field, expected, temp_a, temp_b, 2.0, slab=2, workers=2)
                spectrum = axis2_spectrum(field, slab=2, workers=2)
                filter_field_from_axis2_spectrum(
                    spectrum, actual, temp_a, temp_b, 2.0, slab=2, workers=2
                )
                np.testing.assert_array_equal(actual, expected)
            finally:
                close_memmap(expected)
                close_memmap(actual)
                close_memmap(temp_a)
                close_memmap(temp_b)


if __name__ == "__main__":
    unittest.main()
