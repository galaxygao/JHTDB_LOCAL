from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import numpy as np
from scipy import fft
from scipy.special import erfc


ARRAY_AXIS_FOR_DERIVATIVE = (2, 1, 0)  # derivative labels x,y,z for arrays z,y,x
REGIME_LABELS = ("uncertain", "1+", "1-", "2", "3", "4+", "4-")


def spectral_derivative(values: np.ndarray, axis: int, domain_length: float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    n = values.shape[axis]
    wave_number = 2.0 * np.pi * fft.rfftfreq(n, d=domain_length / n)
    spectrum = fft.rfft(values, axis=axis, workers=1)
    shape = [1] * values.ndim
    shape[axis] = len(wave_number)
    spectrum *= (1j * wave_number).reshape(shape)
    return fft.irfft(spectrum, n=n, axis=axis, workers=1).astype(np.float32)


def spectral_gaussian(
    values: np.ndarray, sigma_grid: float, *, workers: int = 1
) -> np.ndarray:
    if sigma_grid <= 0:
        raise ValueError("sigma_grid must be positive")
    if workers < 1:
        raise ValueError("workers must be positive")
    result = np.asarray(values, dtype=np.float32)
    for axis in range(result.ndim):
        n = result.shape[axis]
        theta = 2.0 * np.pi * fft.rfftfreq(n, d=1.0)
        transfer = np.exp(-0.5 * np.square(sigma_grid * theta)).astype(np.float32)
        spectrum = fft.rfft(result, axis=axis, workers=workers)
        shape = [1] * result.ndim
        shape[axis] = len(transfer)
        spectrum *= transfer.reshape(shape)
        result = fft.irfft(spectrum, n=n, axis=axis, workers=workers).astype(np.float32)
    return result


def regime_codes(
    work_full: np.ndarray,
    work_resolved: np.ndarray,
    epsilon_abs: float,
    epsilon_rel: float,
) -> tuple[np.ndarray, float, float]:
    full_rms = float(np.sqrt(np.mean(np.square(work_full, dtype=np.float64))))
    resolved_rms = float(
        np.sqrt(np.mean(np.square(work_resolved, dtype=np.float64)))
    )
    epsilon_full = max(epsilon_abs, epsilon_rel * full_rms)
    epsilon_resolved = max(epsilon_abs, epsilon_rel * resolved_rms)
    codes = regime_codes_from_thresholds(
        work_full, work_resolved, epsilon_full, epsilon_resolved
    )
    return codes, epsilon_full, epsilon_resolved


def regime_codes_from_thresholds(
    work_full: np.ndarray,
    work_resolved: np.ndarray,
    epsilon_full: float,
    epsilon_resolved: float,
) -> np.ndarray:
    """Return v6 codes: uncertain, 1+, 1-, 2, 3, 4+, 4-."""
    work_full = np.asarray(work_full)
    work_resolved = np.asarray(work_resolved)
    if work_full.shape != work_resolved.shape:
        raise ValueError("work fields must have identical shapes")
    codes = np.zeros(work_full.shape, dtype=np.uint8)
    full_pos, full_neg = work_full > epsilon_full, work_full < -epsilon_full
    res_pos = work_resolved > epsilon_resolved
    res_neg = work_resolved < -epsilon_resolved
    delta_nonnegative = (work_full - work_resolved) >= 0.0
    q1 = full_pos & res_pos
    q4 = full_neg & res_neg
    codes[q1 & delta_nonnegative] = 1
    codes[q1 & ~delta_nonnegative] = 2
    codes[full_pos & res_neg] = 3
    codes[full_neg & res_pos] = 4
    codes[q4 & delta_nonnegative] = 5
    codes[q4 & ~delta_nonnegative] = 6
    return codes


def legacy_regime_codes(codes: np.ndarray) -> np.ndarray:
    """Aggregate v6 codes back to the legacy uncertain/Q1/Q2/Q3/Q4 layout."""
    values = np.asarray(codes, dtype=np.uint8)
    legacy = np.zeros(values.shape, dtype=np.uint8)
    legacy[(values == 1) | (values == 2)] = 1
    legacy[values == 3] = 2
    legacy[values == 4] = 3
    legacy[(values == 5) | (values == 6)] = 4
    return legacy


class ComponentView:
    def __init__(self, parent: Any, component: int):
        self.parent = parent
        self.component = component
        self.shape = tuple(parent.shape[1:])

    def __getitem__(self, key: Any) -> np.ndarray:
        if not isinstance(key, tuple):
            key = (key,)
        return self.parent[(self.component,) + key]

    def __setitem__(self, key: Any, value: np.ndarray) -> None:
        if not isinstance(key, tuple):
            key = (key,)
        self.parent[(self.component,) + key] = value


class ProductView:
    """Read-only slab view of the pointwise product of two full-domain fields."""

    def __init__(self, left: Any, right: Any):
        if tuple(left.shape) != tuple(right.shape):
            raise ValueError("product fields must have identical shapes")
        self.left = left
        self.right = right
        self.shape = tuple(left.shape)

    def __getitem__(self, key: Any) -> np.ndarray:
        return np.asarray(self.left[key], dtype=np.float32) * np.asarray(
            self.right[key], dtype=np.float32
        )


def axis_batches(
    shape: tuple[int, int, int], axis: int, slab: int
) -> Iterator[tuple[slice, slice, slice]]:
    if axis in (1, 2):
        for start in range(0, shape[0], slab):
            yield slice(start, min(start + slab, shape[0])), slice(None), slice(None)
    elif axis == 0:
        for start in range(0, shape[1], slab):
            yield slice(None), slice(start, min(start + slab, shape[1])), slice(None)
    else:
        raise ValueError(f"invalid 3-D axis {axis}")


def transform_axis(
    source: Any,
    destination: Any,
    axis: int,
    slab: int,
    *,
    workers: int = 1,
    derivative_domain_length: float | None = None,
    gaussian_sigma_grid: float | None = None,
) -> None:
    if (derivative_domain_length is None) == (gaussian_sigma_grid is None):
        raise ValueError("select exactly one spectral operation")
    n = source.shape[axis]
    if derivative_domain_length is not None:
        multiplier = 1j * 2.0 * np.pi * fft.rfftfreq(
            n, d=derivative_domain_length / n
        )
    else:
        sigma = float(gaussian_sigma_grid)
        if sigma <= 0:
            raise ValueError("gaussian_sigma_grid must be positive")
        theta = 2.0 * np.pi * fft.rfftfreq(n, d=1.0)
        multiplier = np.exp(-0.5 * np.square(sigma * theta)).astype(np.float32)
    multiplier_shape = [1, 1, 1]
    multiplier_shape[axis] = len(multiplier)
    shaped_multiplier = multiplier.reshape(multiplier_shape)
    for key in axis_batches(tuple(source.shape), axis, slab):
        block = np.asarray(source[key], dtype=np.float32)
        spectrum = fft.rfft(block, axis=axis, workers=workers)
        spectrum *= shaped_multiplier
        destination[key] = fft.irfft(
            spectrum, n=n, axis=axis, workers=workers
        ).astype(np.float32)


def axis2_spectrum(
    source: Any,
    slab: int,
    *,
    workers: int = 1,
) -> np.ndarray:
    """Cache the first (x/array-axis-2) real FFT used by separable filtering."""
    shape = tuple(int(value) for value in source.shape)
    if len(shape) != 3:
        raise ValueError("axis2_spectrum requires a three-dimensional field")
    spectrum = np.empty(
        (shape[0], shape[1], shape[2] // 2 + 1), dtype=np.complex64
    )
    for key in axis_batches(shape, 2, slab):
        block = np.asarray(source[key], dtype=np.float32)
        spectrum[key] = fft.rfft(block, axis=2, workers=workers)
    return spectrum


def full_spectrum(
    source: Any,
    slab: int,
    *,
    workers: int = 1,
) -> np.ndarray:
    """Return the complete 3-D rFFT spectrum without spatial subsampling."""
    spectrum = axis2_spectrum(source, slab, workers=workers)
    spectrum = fft.fft(spectrum, axis=1, workers=workers, overwrite_x=True)
    spectrum = fft.fft(spectrum, axis=0, workers=workers, overwrite_x=True)
    return np.asarray(spectrum, dtype=np.complex64)


def smooth_sharp_radial_weights(
    radial_wavenumber: np.ndarray,
    cutoff_wavenumber: float,
    edge_width_wavenumber: float,
) -> np.ndarray:
    """Gaussian-smoothed Heaviside edge centered on the sharp cutoff."""
    radial = np.asarray(radial_wavenumber, dtype=np.float64)
    cutoff = float(cutoff_wavenumber)
    width = float(edge_width_wavenumber)
    if np.any(radial < 0) or not np.all(np.isfinite(radial)):
        raise ValueError("radial_wavenumber must be finite and nonnegative")
    if not np.isfinite(cutoff) or cutoff <= 0:
        raise ValueError("cutoff_wavenumber must be finite and positive")
    if not np.isfinite(width) or width <= 0:
        raise ValueError("edge_width_wavenumber must be finite and positive")
    weights = 0.5 * erfc((radial - cutoff) / (np.sqrt(2.0) * width))
    weights = np.asarray(weights, dtype=np.float32)
    weights[radial == 0] = 1.0
    return weights


def filter_smooth_sharp_from_spectrum(
    spectrum: np.ndarray,
    destination: Any,
    sigma_grid: float,
    domain_length: float,
    edge_width_fraction: float,
    slab: int,
    *,
    workers: int = 1,
) -> None:
    """Apply an isotropic smooth sharp cutoff to a complete periodic spectrum."""
    shape = tuple(int(value) for value in destination.shape)
    expected = (shape[0], shape[1], shape[2] // 2 + 1)
    if tuple(spectrum.shape) != expected or np.dtype(spectrum.dtype) != np.dtype(
        np.complex64
    ):
        raise ValueError("full spectrum has an unexpected schema")
    if sigma_grid <= 0 or domain_length <= 0 or edge_width_fraction <= 0:
        raise ValueError("filter scale, domain length, and edge width must be positive")
    if len(set(shape)) != 1:
        raise ValueError("smooth sharp filtering currently requires a cubic grid")

    dx = domain_length / shape[2]
    cutoff = np.pi / (sigma_grid * dx)
    width = edge_width_fraction * cutoff
    kz = 2.0 * np.pi * fft.fftfreq(shape[0], d=domain_length / shape[0])
    ky = 2.0 * np.pi * fft.fftfreq(shape[1], d=domain_length / shape[1])
    kx = 2.0 * np.pi * fft.rfftfreq(shape[2], d=domain_length / shape[2])
    ky2 = np.square(ky, dtype=np.float64)[None, :, None]
    kx2 = np.square(kx, dtype=np.float64)[None, None, :]
    filtered = np.array(spectrum, dtype=np.complex64, copy=True)
    for start in range(0, shape[0], slab):
        stop = min(start + slab, shape[0])
        radial = np.sqrt(
            np.square(kz[start:stop], dtype=np.float64)[:, None, None]
            + ky2
            + kx2
        )
        filtered[start:stop] *= smooth_sharp_radial_weights(
            radial, cutoff, width
        )
    values = fft.irfftn(
        filtered, s=shape, workers=workers, overwrite_x=True
    ).astype(np.float32, copy=False)
    for start in range(0, shape[0], slab):
        stop = min(start + slab, shape[0])
        destination[start:stop] = values[start:stop]


def filter_smooth_sharp_field(
    source: Any,
    destination: Any,
    sigma_grid: float,
    domain_length: float,
    edge_width_fraction: float,
    slab: int,
    *,
    workers: int = 1,
) -> None:
    """Compute and filter a complete periodic 3-D field without downsampling."""
    spectrum = full_spectrum(source, slab, workers=workers)
    filter_smooth_sharp_from_spectrum(
        spectrum,
        destination,
        sigma_grid,
        domain_length,
        edge_width_fraction,
        slab,
        workers=workers,
    )


def filter_field_from_axis2_spectrum(
    spectrum: np.ndarray,
    destination: Any,
    temp_a: Any,
    temp_b: Any,
    sigma_grid: float,
    slab: int,
    *,
    workers: int = 1,
) -> None:
    """Continue the existing separable filter from a shared first-axis FFT."""
    if sigma_grid <= 0:
        raise ValueError("sigma_grid must be positive")
    shape = tuple(int(value) for value in destination.shape)
    expected = (shape[0], shape[1], shape[2] // 2 + 1)
    if tuple(spectrum.shape) != expected or np.dtype(spectrum.dtype) != np.dtype(
        np.complex64
    ):
        raise ValueError("cached first-axis spectrum has an unexpected schema")
    theta = 2.0 * np.pi * fft.rfftfreq(shape[2], d=1.0)
    transfer = np.exp(-0.5 * np.square(sigma_grid * theta)).astype(np.float32)
    shaped_transfer = transfer.reshape(1, 1, -1)
    for key in axis_batches(shape, 2, slab):
        filtered_spectrum = np.asarray(spectrum[key]) * shaped_transfer
        temp_a[key] = fft.irfft(
            filtered_spectrum, n=shape[2], axis=2, workers=workers
        ).astype(np.float32)
    transform_axis(
        temp_a, temp_b, 1, slab, workers=workers, gaussian_sigma_grid=sigma_grid
    )
    transform_axis(
        temp_b,
        destination,
        0,
        slab,
        workers=workers,
        gaussian_sigma_grid=sigma_grid,
    )


def derivative_field(
    source: Any,
    destination: Any,
    derivative_component: int,
    domain_length: float,
    slab: int,
    workers: int = 1,
) -> None:
    transform_axis(
        source,
        destination,
        ARRAY_AXIS_FOR_DERIVATIVE[derivative_component],
        slab,
        workers=workers,
        derivative_domain_length=domain_length,
    )


def filter_field(
    source: Any,
    destination: Any,
    temp_a: Any,
    temp_b: Any,
    sigma_grid: float,
    slab: int,
    workers: int = 1,
) -> None:
    transform_axis(
        source, temp_a, 2, slab, workers=workers, gaussian_sigma_grid=sigma_grid
    )
    transform_axis(
        temp_a, temp_b, 1, slab, workers=workers, gaussian_sigma_grid=sigma_grid
    )
    transform_axis(
        temp_b, destination, 0, slab, workers=workers, gaussian_sigma_grid=sigma_grid
    )


def zero_field(field: Any, slab: int) -> None:
    for start in range(0, field.shape[0], slab):
        field[start : min(start + slab, field.shape[0]), :, :] = 0.0


def accumulate_product(
    destination: Any,
    left: Any,
    right: Any,
    slab: int,
) -> None:
    for start in range(0, destination.shape[0], slab):
        key = (slice(start, min(start + slab, destination.shape[0])), slice(None), slice(None))
        values = np.asarray(destination[key], dtype=np.float32)
        values += np.asarray(left[key], dtype=np.float32) * np.asarray(
            right[key], dtype=np.float32
        )
        destination[key] = values


def subtract_product(
    destination: Any,
    left: Any,
    right: Any,
    slab: int,
) -> None:
    for start in range(0, destination.shape[0], slab):
        key = (slice(start, min(start + slab, destination.shape[0])), slice(None), slice(None))
        values = np.asarray(destination[key], dtype=np.float32)
        values -= np.asarray(left[key], dtype=np.float32) * np.asarray(
            right[key], dtype=np.float32
        )
        destination[key] = values


def memmap(path: Path, shape: tuple[int, ...], mode: str = "w+") -> np.memmap:
    path.parent.mkdir(parents=True, exist_ok=True)
    return np.memmap(path, dtype=np.float32, mode=mode, shape=shape, order="C")


def close_memmap(mapped: np.memmap) -> None:
    mapped.flush()
    memory_map = getattr(mapped, "_mmap", None)
    if memory_map is not None:
        memory_map.close()
