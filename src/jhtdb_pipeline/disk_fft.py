"""Full-domain FFTs with slab-sized working arrays and disk-backed spectra."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from scipy import fft

from .physics import axis_batches, smooth_sharp_radial_weights, release_pages


def mapped_array(path: Path, shape: tuple[int, ...], dtype: str) -> np.memmap:
    path.parent.mkdir(parents=True, exist_ok=True)
    return np.memmap(path, mode="w+", shape=shape, dtype=dtype)


def build_spectrum(
    source: Any, path: Path, slab: int, *, workers: int, full: bool,
) -> np.memmap:
    shape = tuple(source.shape)
    spectrum = mapped_array(path, (shape[0], shape[1], shape[2] // 2 + 1), "<c8")
    try:
        for key in axis_batches(shape, 2, slab):
            block = np.asarray(source[key], dtype=np.float32)
            spectrum[key] = fft.rfft(block, axis=2, workers=workers)
        release_pages(spectrum)
        if full:
            for axis in (1, 0):
                for key in axis_batches(tuple(spectrum.shape), axis, slab):
                    block = np.array(spectrum[key], dtype=np.complex64, copy=True)
                    spectrum[key] = fft.fft(block, axis=axis, workers=workers, overwrite_x=True)
                release_pages(spectrum)
        return spectrum
    except BaseException:
        spectrum._mmap.close()
        raise


def filter_spectrum(
    spectrum: Any, destination: Any, scratch_path: Path,
    sigma: float, domain_length: float, alpha: float, slab: int, *, workers: int,
) -> None:
    """Apply the radial filter, then invert each axis in full-length FFT slabs."""
    shape = tuple(destination.shape)
    expected = (shape[0], shape[1], shape[2] // 2 + 1)
    if tuple(spectrum.shape) != expected or len(set(shape)) != 1:
        raise ValueError("smooth-sharp requires a full cubic field and matching spectrum")
    if sigma <= 0 or domain_length <= 0 or alpha <= 0 or slab < 1:
        raise ValueError("invalid spectral filter parameters")
    cutoff = np.pi / (sigma * domain_length / shape[2])
    width = alpha * cutoff
    kz = 2 * np.pi * fft.fftfreq(shape[0], d=domain_length / shape[0])
    ky = 2 * np.pi * fft.fftfreq(shape[1], d=domain_length / shape[1])
    kx = 2 * np.pi * fft.rfftfreq(shape[2], d=domain_length / shape[2])
    filtered = mapped_array(scratch_path, expected, "<c8")
    try:
        for key in axis_batches(expected, 2, slab):
            radial = np.sqrt(kz[key[0], None, None] ** 2 + ky[None, :, None] ** 2 + kx[None, None, :] ** 2)
            block = np.array(spectrum[key], dtype=np.complex64, copy=True)
            block *= smooth_sharp_radial_weights(radial, cutoff, width)
            filtered[key] = block
        release_pages(filtered)
        # Same normalization as irfftn: inverse z, inverse y, real inverse x.
        for axis in (0, 1):
            for key in axis_batches(expected, axis, slab):
                block = np.array(filtered[key], dtype=np.complex64, copy=True)
                filtered[key] = fft.ifft(block, axis=axis, workers=workers, overwrite_x=True)
            release_pages(filtered)
        for key in axis_batches(shape, 2, slab):
            block = np.array(filtered[key], dtype=np.complex64, copy=True)
            destination[key] = fft.irfft(block, n=shape[2], axis=2, workers=workers)
        release_pages(destination)
    finally:
        filtered._mmap.close()
        scratch_path.unlink(missing_ok=True)
