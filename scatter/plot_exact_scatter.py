#!/usr/bin/env python
"""Build exact-count 3-D and 2-D density views for one frame and sigma.

Every full-domain grid point contributes to both views.  The independent 3-D
coordinates are (W_full, S_bar, Pi_LES); W_resolved and delta-W are retained as
exact derived features for later models.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.store import open_complete_result, spatial_slices


AXIS_KEYS = ("work_full", "s_bar", "pi_les")
AXIS_LABELS = ("W_full", "S̄", "Π_LES")
REQUIRED_FIELDS = ("s_bar", "pi", "work_full", "work_resolved")
DEFAULT_BINS = 64
DEFAULT_BINS_2D = 256


@dataclass(frozen=True)
class FeatureChunk:
    """One spatial chunk of exact, flattened feature values."""

    spatial_slices_zyx: tuple[slice, slice, slice]
    s_bar: np.ndarray
    pi_les: np.ndarray
    work_full: np.ndarray
    work_resolved: np.ndarray
    delta_w: np.ndarray

    @property
    def point_count(self) -> int:
        return int(self.s_bar.size)

    def matrix(self, *, dtype: Any = np.float32) -> np.ndarray:
        """Return an ``N x 3`` matrix for clustering/classification code."""

        return np.column_stack(
            (self.work_full, self.s_bar, self.pi_les)
        ).astype(
            dtype, copy=False
        )

    def matrix_with_delta_w(self, *, dtype: Any = np.float32) -> np.ndarray:
        """Return all four physical features, including derived delta-W."""

        return np.column_stack(
            (self.work_full, self.s_bar, self.pi_les, self.delta_w)
        ).astype(dtype, copy=False)


def _validate_source(root: Any) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    missing = [name for name in REQUIRED_FIELDS if name not in root]
    if missing:
        raise RuntimeError(f"result is missing fields: {', '.join(missing)}")

    arrays = [root[name] for name in REQUIRED_FIELDS]
    shape = tuple(int(value) for value in arrays[0].shape)
    if len(shape) != 3 or any(tuple(array.shape) != shape for array in arrays):
        raise RuntimeError("S_bar, pi and work fields must have one identical 3-D shape")
    if any(np.dtype(array.dtype) != np.dtype("<f4") for array in arrays):
        raise RuntimeError("S_bar, pi and work fields must be float32")
    chunks = tuple(int(value) for value in arrays[0].chunks)
    return shape, chunks


def iter_exact_feature_chunks(root: Any) -> Iterator[FeatureChunk]:
    """Yield every point exactly once with three independent features.

    The stored pipeline variable ``pi`` is ``tau:S``.  The LES-forward flux used
    on the second axis is therefore ``Pi_LES = -pi``.
    """

    shape, chunks = _validate_source(root)
    for key in spatial_slices(shape, chunks):
        s_bar = np.asarray(root["s_bar"][key], dtype=np.float32).ravel()
        stored_pi = np.asarray(root["pi"][key], dtype=np.float32).ravel()
        work_full = np.asarray(root["work_full"][key], dtype=np.float32).ravel()
        work_resolved = np.asarray(
            root["work_resolved"][key], dtype=np.float32
        ).ravel()
        if any(
            not np.all(np.isfinite(values))
            for values in (s_bar, stored_pi, work_full, work_resolved)
        ):
            raise ValueError(f"non-finite value found in spatial chunk {key}")
        yield FeatureChunk(
            spatial_slices_zyx=key,
            s_bar=s_bar,
            pi_les=-stored_pi,
            work_full=work_full,
            work_resolved=work_resolved,
            delta_w=work_full - work_resolved,
        )


def _manifest_axis_bounds(result_dir: Path) -> tuple[tuple[float, float], ...] | None:
    """Use committed exact extrema for the three independent axes."""

    manifest_path = result_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fields = manifest.get("fields", {})
    try:
        s_min = float(fields["s_bar"]["minimum"])
        s_max = float(fields["s_bar"]["maximum"])
        pi_min = float(fields["pi"]["minimum"])
        pi_max = float(fields["pi"]["maximum"])
        full_min = float(fields["work_full"]["minimum"])
        full_max = float(fields["work_full"]["maximum"])
    except (KeyError, TypeError, ValueError):
        return None
    values = (s_min, s_max, pi_min, pi_max, full_min, full_max)
    if not all(math.isfinite(value) for value in values):
        return None
    return (
        (full_min, full_max),
        (s_min, s_max),
        (-pi_max, -pi_min),
    )


def exact_feature_bounds(
    root: Any,
    *,
    committed_bounds: tuple[tuple[float, float], ...] | None = None,
) -> tuple[tuple[float, float], ...]:
    """Return exact extrema for all three axes using a chunked full scan."""

    if committed_bounds is not None:
        if len(committed_bounds) != 3:
            raise ValueError("committed_bounds must contain all three axis bounds")
        flattened = [value for item in committed_bounds for value in item]
        if not all(math.isfinite(float(value)) for value in flattened):
            raise ValueError("committed feature bounds must be finite")
        return tuple(
            (float(low), float(high)) for low, high in committed_bounds
        )

    minima = np.full(3, np.inf, dtype=np.float64)
    maxima = np.full(3, -np.inf, dtype=np.float64)
    for chunk in iter_exact_feature_chunks(root):
        fields = (
            chunk.work_full,
            chunk.s_bar,
            chunk.pi_les,
        )
        for axis, values in enumerate(fields):
            minima[axis] = min(minima[axis], float(values.min()))
            maxima[axis] = max(maxima[axis], float(values.max()))

    if not np.all(np.isfinite(minima)) or not np.all(np.isfinite(maxima)):
        raise RuntimeError("could not determine finite feature bounds")
    return tuple((float(low), float(high)) for low, high in zip(minima, maxima))


def _edges(low: float, high: float, bins: int) -> np.ndarray:
    if high < low:
        raise ValueError("feature bound maximum is smaller than minimum")
    if high == low:
        padding = max(abs(low) * 1.0e-6, 1.0e-12)
        low -= padding
        high += padding
    return np.linspace(low, high, bins + 1, dtype=np.float64)


def exact_density_histogram(
    root: Any,
    bounds: Sequence[tuple[float, float]],
    *,
    bins: int = DEFAULT_BINS,
) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray], int]:
    """Compatibility wrapper returning only the exact 3-D histogram."""

    density_3d, edges_3d, _, _, point_count = exact_density_histograms(
        root, bounds, bins_3d=bins, bins_2d=bins
    )
    return density_3d, edges_3d, point_count


def exact_density_histograms(
    root: Any,
    bounds: Sequence[tuple[float, float]],
    *,
    bins_3d: int = DEFAULT_BINS,
    bins_2d: int = DEFAULT_BINS_2D,
) -> tuple[
    np.ndarray,
    tuple[np.ndarray, np.ndarray, np.ndarray],
    np.ndarray,
    tuple[np.ndarray, np.ndarray],
    int,
]:
    """Count every point into independent exact 3-D and 2-D histograms."""

    if bins_3d < 2 or bins_3d > 256:
        raise ValueError("3-D bins must be between 2 and 256")
    if bins_2d < 2 or bins_2d > 4096:
        raise ValueError("2-D bins must be between 2 and 4096")
    if len(bounds) != 3:
        raise ValueError("three feature bounds are required")
    edges_3d = tuple(
        _edges(float(low), float(high), bins_3d) for low, high in bounds
    )
    # The 2-D view is accumulated independently at higher resolution.  It does
    # not inherit the coarser 3-D bins or the W_full dynamic range.
    edges_2d = (
        _edges(float(bounds[1][0]), float(bounds[1][1]), bins_2d),
        _edges(float(bounds[2][0]), float(bounds[2][1]), bins_2d),
    )
    density_3d = np.zeros((bins_3d, bins_3d, bins_3d), dtype=np.uint64)
    density_2d = np.zeros((bins_2d, bins_2d), dtype=np.uint64)
    point_count = 0

    for chunk in iter_exact_feature_chunks(root):
        chunk_density_3d, _ = np.histogramdd(
            (chunk.work_full, chunk.s_bar, chunk.pi_les), bins=edges_3d
        )
        chunk_density_2d, _, _ = np.histogram2d(
            chunk.s_bar, chunk.pi_les, bins=edges_2d
        )
        density_3d += chunk_density_3d.astype(np.uint64)
        density_2d += chunk_density_2d.astype(np.uint64)
        point_count += chunk.point_count

    counted_3d = int(density_3d.sum(dtype=np.uint64))
    counted_2d = int(density_2d.sum(dtype=np.uint64))
    if counted_3d != point_count or counted_2d != point_count:
        raise RuntimeError(
            "exact-density closure failed: "
            f"3-D={counted_3d}, 2-D={counted_2d}, source={point_count}"
        )
    return density_3d, edges_3d, density_2d, edges_2d, point_count


def probability_density(
    counts: np.ndarray, edges: Sequence[np.ndarray]
) -> tuple[np.ndarray, float]:
    """Normalize integer histogram counts to a Cartesian PDF."""

    if counts.ndim != len(edges):
        raise ValueError("histogram rank and number of edge arrays differ")
    if counts.shape != tuple(len(edge) - 1 for edge in edges):
        raise ValueError("histogram shape does not match its edge arrays")
    total = int(counts.sum(dtype=np.uint64))
    if total <= 0:
        raise ValueError("cannot normalize an empty histogram")

    cell_measure: np.ndarray | float = np.diff(edges[0])
    for edge in edges[1:]:
        cell_measure = np.multiply.outer(cell_measure, np.diff(edge))
    if np.any(np.asarray(cell_measure) <= 0.0):
        raise ValueError("PDF edges must be strictly increasing")
    pdf = counts.astype(np.float64) / (float(total) * cell_measure)
    integral = float(np.sum(pdf * cell_measure, dtype=np.float64))
    return pdf, integral


def top_pdf_mask(pdf: np.ndarray, percentile: float = 95.0) -> tuple[np.ndarray, float]:
    """Select occupied bins at or above the requested PDF percentile."""

    if percentile <= 0.0 or percentile >= 100.0:
        raise ValueError("PDF percentile must lie strictly between 0 and 100")
    occupied = pdf[pdf > 0.0]
    if occupied.size == 0:
        raise ValueError("PDF contains no occupied bins")
    threshold = float(np.percentile(occupied, percentile))
    return (pdf >= threshold) & (pdf > 0.0), threshold


def pdf_display_scale(
    pdf: np.ndarray,
    occupied_from_counts: np.ndarray,
    *,
    lower_percentile: float = 1.0,
    upper_percentile: float = 99.0,
) -> tuple[np.ndarray, float, float]:
    """Map occupied PDF values to [0, 1] on a robust log10 color scale."""

    if pdf.shape != occupied_from_counts.shape:
        raise ValueError("PDF and count-derived occupancy masks must match")
    if not np.any(occupied_from_counts):
        raise ValueError("cannot scale a PDF without occupied count bins")
    log_values = np.log10(pdf[occupied_from_counts])
    lower = float(np.percentile(log_values, lower_percentile))
    upper = float(np.percentile(log_values, upper_percentile))
    if upper <= lower:
        upper = lower + 1.0
    scaled = np.full(pdf.shape, -1.0, dtype=np.float64)
    scaled[occupied_from_counts] = np.clip(
        (log_values - lower) / (upper - lower), 0.0, 1.0
    )
    return scaled, lower, upper


def nice_axis_limits(
    low: float,
    high: float,
    *,
    padding_fraction: float = 0.05,
    target_intervals: int = 6,
) -> tuple[float, float]:
    """Return zero-aware, padded limits rounded outward to a 1/2/5 step."""

    if not math.isfinite(low) or not math.isfinite(high) or high < low:
        raise ValueError("axis extrema must be finite and ordered")
    low = min(float(low), 0.0)
    high = max(float(high), 0.0)
    span = high - low
    if span == 0.0:
        span = max(abs(low), 1.0)
    raw_step = span / max(int(target_intervals), 1)
    magnitude = 10.0 ** math.floor(math.log10(raw_step))
    fraction = raw_step / magnitude
    if fraction <= 1.0:
        nice_fraction = 1.0
    elif fraction <= 2.0:
        nice_fraction = 2.0
    elif fraction <= 5.0:
        nice_fraction = 5.0
    else:
        nice_fraction = 10.0
    step = nice_fraction * magnitude
    padding = span * padding_fraction
    display_low = math.floor((low - padding) / step) * step
    display_high = math.ceil((high + padding) / step) * step
    if display_low >= low:
        display_low -= step
    if display_high <= high:
        display_high += step
    return float(display_low), float(display_high)


def _pdf_colorbar(
    title: str,
    log_min: float,
    log_max: float,
    x: float,
    *,
    y: float,
    length: float,
) -> dict[str, Any]:
    ticks = np.linspace(0.0, 1.0, 5)
    return {
        "title": title,
        "x": x,
        "y": y,
        "len": length,
        "tickvals": ticks.tolist(),
        "ticktext": [
            f"{10.0 ** (log_min + tick * (log_max - log_min)):.2e}"
            for tick in ticks
        ],
    }


def density_figure(
    density: np.ndarray,
    edges: Sequence[np.ndarray],
    *,
    density_2d: np.ndarray | None = None,
    edges_2d: Sequence[np.ndarray] | None = None,
    title: str,
) -> go.Figure:
    """Create equal-scale 3-D/2-D densities with physical boundary planes."""

    centers = tuple((edge[:-1] + edge[1:]) * 0.5 for edge in edges)
    if len(centers) != 3 or density.shape != tuple(len(item) for item in centers):
        raise ValueError("3-D density shape does not match its axis edges")
    data_ranges = tuple(
        (float(edge[0]), float(edge[-1])) for edge in edges
    )
    axis_ranges = tuple(nice_axis_limits(low, high) for low, high in data_ranges)
    if density_2d is None:
        density_2d = density.sum(axis=0, dtype=np.uint64)
    if edges_2d is None:
        edges_2d = (edges[1], edges[2])
    centers_2d = tuple((edge[:-1] + edge[1:]) * 0.5 for edge in edges_2d)
    if len(centers_2d) != 2 or density_2d.shape != tuple(
        len(item) for item in centers_2d
    ):
        raise ValueError("2-D density shape does not match its axis edges")
    data_ranges_2d = tuple(
        (float(edge[0]), float(edge[-1])) for edge in edges_2d
    )
    axis_ranges_2d = tuple(
        nice_axis_limits(low, high) for low, high in data_ranges_2d
    )
    # Empty bins are identified from exact integer counts before any floating-
    # point PDF normalization is performed.
    occupied_3d = density != 0
    occupied_2d = density_2d != 0
    x_grid, y_grid, z_grid = np.meshgrid(*centers, indexing="ij")
    pdf_3d, integral_3d = probability_density(density, edges)
    pdf_2d, integral_2d = probability_density(density_2d, edges_2d)
    if not np.isclose(integral_3d, 1.0, rtol=1.0e-12, atol=1.0e-12):
        raise RuntimeError(f"3-D PDF normalization failed: integral={integral_3d}")
    if not np.isclose(integral_2d, 1.0, rtol=1.0e-12, atol=1.0e-12):
        raise RuntimeError(f"2-D PDF normalization failed: integral={integral_2d}")
    top_3d, threshold_3d = top_pdf_mask(pdf_3d)
    top_2d, threshold_2d = top_pdf_mask(pdf_2d)
    display_3d, log_min_3d, log_max_3d = pdf_display_scale(
        pdf_3d, occupied_3d
    )
    display_2d, log_min_2d, log_max_2d = pdf_display_scale(
        pdf_2d, occupied_2d
    )

    def range_text(edge: np.ndarray) -> str:
        return f"[{float(edge[0]):.3e}, {float(edge[-1]):.3e}]"

    def limit_text(limits: tuple[float, float]) -> str:
        return f"[{limits[0]:.3e}, {limits[1]:.3e}]"

    figure = make_subplots(
        rows=2,
        cols=1,
        specs=[[{"type": "scene"}], [{"type": "xy"}]],
        row_heights=[0.75, 0.25],
        vertical_spacing=0.13,
        subplot_titles=(
            "3-D PDF cloud: (W_full, S̄, Π_LES)",
            "2-D PDF: (S̄, Π_LES)",
        ),
    )
    figure.add_trace(
        go.Volume(
            x=x_grid.ravel(),
            y=y_grid.ravel(),
            z=z_grid.ravel(),
            value=display_3d.ravel(),
            customdata=np.column_stack((density.ravel(), pdf_3d.ravel())),
            isomin=0.0,
            isomax=1.0,
            opacity=0.12,
            surface_count=18,
            colorscale="Viridis",
            colorbar=_pdf_colorbar(
                "3-D PDF (log scale)",
                log_min_3d,
                log_max_3d,
                0.965,
                y=0.71,
                length=0.54,
            ),
            name="3-D exact density",
            hovertemplate=(
                "W_full=%{x:.6e}<br>S̄=%{y:.6e}<br>"
                "Π_LES=%{z:.6e}<br>points/bin=%{customdata[0]}<br>"
                "PDF=%{customdata[1]:.6e}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Heatmap(
            x=centers_2d[0],
            y=centers_2d[1],
            z=np.where(occupied_2d, display_2d, np.nan).T,
            customdata=np.stack((density_2d.T, pdf_2d.T), axis=-1),
            colorscale="Viridis",
            zmin=0.0,
            zmax=1.0,
            colorbar=_pdf_colorbar(
                "2-D PDF (log scale)",
                log_min_2d,
                log_max_2d,
                0.985,
                y=0.14,
                length=0.20,
            ),
            name="2-D exact density",
            hovertemplate=(
                "S̄=%{x:.6e}<br>Π_LES=%{y:.6e}<br>"
                "points/bin=%{customdata[0]}<br>"
                "PDF=%{customdata[1]:.6e}<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    # Delta-W = S_bar + Pi_LES, so this segment marks Delta-W = 0.
    line_low = max(axis_ranges_2d[0][0], -axis_ranges_2d[1][1])
    line_high = min(axis_ranges_2d[0][1], -axis_ranges_2d[1][0])
    if line_low <= line_high:
        figure.add_trace(
            go.Scatter(
                x=[line_low, line_high],
                y=[-line_low, -line_high],
                mode="lines",
                line={"color": "#d62728", "width": 3, "dash": "dash"},
                name="ΔW = 0",
                hovertemplate="ΔW = S̄ + Π_LES = 0<extra></extra>",
            ),
            row=2,
            col=1,
        )

    def add_plane(
        x: np.ndarray,
        y: np.ndarray,
        z: np.ndarray,
        *,
        name: str,
        color: str,
    ) -> None:
        figure.add_trace(
            go.Surface(
                x=x,
                y=y,
                z=z,
                surfacecolor=np.zeros_like(x, dtype=np.float64),
                colorscale=[[0.0, color], [1.0, color]],
                cmin=0.0,
                cmax=1.0,
                opacity=0.13,
                showscale=False,
                name=name,
                showlegend=True,
                hovertemplate=f"{name}<extra></extra>",
            ),
            row=1,
            col=1,
        )

    # The three regime boundaries all pass through (0, 0, 0).
    x_values = np.linspace(*axis_ranges[0], 17)
    y_values = np.linspace(*axis_ranges[1], 17)
    z_values = np.linspace(*axis_ranges[2], 17)
    plane_y, plane_z = np.meshgrid(y_values, z_values)
    add_plane(
        np.zeros_like(plane_y),
        plane_y,
        plane_z,
        name="W_full = 0",
        color="#7f7f7f",
    )
    delta_low = max(axis_ranges[1][0], -axis_ranges[2][1])
    delta_high = min(axis_ranges[1][1], -axis_ranges[2][0])
    if delta_low <= delta_high:
        delta_y_values = np.linspace(delta_low, delta_high, 17)
        delta_x, delta_y = np.meshgrid(x_values, delta_y_values)
        add_plane(
            delta_x,
            delta_y,
            -delta_y,
            name="ΔW = S̄ + Π_LES = 0",
            color="#ff7f0e",
        )
    full_plane = plane_y + plane_z
    full_plane = np.where(
        (full_plane >= axis_ranges[0][0]) & (full_plane <= axis_ranges[0][1]),
        full_plane,
        np.nan,
    )
    add_plane(
        full_plane,
        plane_y,
        plane_z,
        name="W_res = W_full - S̄ - Π_LES = 0",
        color="#9467bd",
    )

    axis_specs = (
        ([*axis_ranges[0]], [0.0, 0.0], [0.0, 0.0], "x-axis: W_full", "#d62728"),
        ([0.0, 0.0], [*axis_ranges[1]], [0.0, 0.0], "y-axis: S̄", "#2ca02c"),
        ([0.0, 0.0], [0.0, 0.0], [*axis_ranges[2]], "z-axis: Π_LES", "#1f77b4"),
    )
    for x_axis, y_axis, z_axis, name, color in axis_specs:
        figure.add_trace(
            go.Scatter3d(
                x=x_axis,
                y=y_axis,
                z=z_axis,
                mode="lines",
                line={"color": color, "width": 8},
                name=name,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )

    top_threshold_display_3d = float(
        np.clip(
            (np.log10(threshold_3d) - log_min_3d) / (log_max_3d - log_min_3d),
            0.0,
            1.0,
        )
    )
    top_3d_trace_index = len(figure.data)
    figure.add_trace(
        go.Volume(
            x=x_grid.ravel(),
            y=y_grid.ravel(),
            z=z_grid.ravel(),
            value=np.where(top_3d, display_3d, -1.0).ravel(),
            customdata=np.column_stack((density.ravel(), pdf_3d.ravel())),
            isomin=min(top_threshold_display_3d, 1.0 - 1.0e-12),
            isomax=1.0,
            opacity=0.35,
            surface_count=4,
            colorscale=[[0.0, "#ff0000"], [1.0, "#ff0000"]],
            showscale=False,
            name="3-D top 5% PDF bins",
            visible=False,
            hovertemplate=(
                "Top 5% PDF bin<br>W_full=%{x:.6e}<br>S̄=%{y:.6e}<br>"
                "Π_LES=%{z:.6e}<br>points/bin=%{customdata[0]}<br>"
                "PDF=%{customdata[1]:.6e}<extra></extra>"
            ),
        ),
        row=1,
        col=1,
    )
    top_2d_trace_index = len(figure.data)
    figure.add_trace(
        go.Heatmap(
            x=centers_2d[0],
            y=centers_2d[1],
            z=np.where(top_2d.T, 1.0, np.nan),
            customdata=np.stack((density_2d.T, pdf_2d.T), axis=-1),
            colorscale=[[0.0, "#ff0000"], [1.0, "#ff0000"]],
            opacity=0.62,
            showscale=False,
            name="2-D top 5% PDF bins",
            visible=False,
            hovertemplate=(
                "Top 5% PDF bin<br>S̄=%{x:.6e}<br>Π_LES=%{y:.6e}<br>"
                "points/bin=%{customdata[0]}<br>"
                "PDF=%{customdata[1]:.6e}<extra></extra>"
            ),
        ),
        row=2,
        col=1,
    )

    figure.update_layout(
        title=title,
        scene={
            "xaxis": {
                "title": (
                    f"x: W_full<br>data={range_text(edges[0])}<br>"
                    f"lim={limit_text(axis_ranges[0])}"
                ),
                "range": list(axis_ranges[0]),
                "showline": True,
                "linewidth": 4,
                "linecolor": "#202020",
                "showbackground": True,
                "backgroundcolor": "rgba(245,245,245,0.65)",
                "gridcolor": "#c8c8c8",
                "zeroline": True,
                "zerolinecolor": "#d62728",
                "zerolinewidth": 3,
            },
            "yaxis": {
                "title": (
                    f"y: S̄<br>data={range_text(edges[1])}<br>"
                    f"lim={limit_text(axis_ranges[1])}"
                ),
                "range": list(axis_ranges[1]),
                "showline": True,
                "linewidth": 4,
                "linecolor": "#202020",
                "showbackground": True,
                "backgroundcolor": "rgba(245,245,245,0.65)",
                "gridcolor": "#c8c8c8",
                "zeroline": True,
                "zerolinecolor": "#d62728",
                "zerolinewidth": 3,
            },
            "zaxis": {
                "title": (
                    f"z: Π_LES = -τ:S<br>data={range_text(edges[2])}<br>"
                    f"lim={limit_text(axis_ranges[2])}"
                ),
                "range": list(axis_ranges[2]),
                "showline": True,
                "linewidth": 4,
                "linecolor": "#202020",
                "showbackground": True,
                "backgroundcolor": "rgba(245,245,245,0.65)",
                "gridcolor": "#c8c8c8",
                "zeroline": True,
                "zerolinecolor": "#d62728",
                "zerolinewidth": 3,
            },
            "aspectmode": "data",
        },
        template="plotly_white",
        width=1200,
        height=1600,
        margin={"l": 80, "r": 110, "b": 70, "t": 115},
        legend={"orientation": "h", "y": -0.10},
        updatemenus=[
            {
                "type": "buttons",
                "direction": "right",
                "x": 0.98,
                "xanchor": "right",
                "y": 0.985,
                "yanchor": "top",
                "showactive": True,
                "buttons": [
                    {
                        "label": "3-D top 5% ON",
                        "method": "restyle",
                        "args": [{"visible": True}, [top_3d_trace_index]],
                    },
                    {
                        "label": "3-D top 5% OFF",
                        "method": "restyle",
                        "args": [{"visible": False}, [top_3d_trace_index]],
                    },
                ],
            },
            {
                "type": "buttons",
                "direction": "right",
                "x": 0.98,
                "xanchor": "right",
                "y": 0.285,
                "yanchor": "top",
                "showactive": True,
                "buttons": [
                    {
                        "label": "2-D top 5% ON",
                        "method": "restyle",
                        "args": [{"visible": True}, [top_2d_trace_index]],
                    },
                    {
                        "label": "2-D top 5% OFF",
                        "method": "restyle",
                        "args": [{"visible": False}, [top_2d_trace_index]],
                    },
                ],
            },
        ],
    )
    figure.update_xaxes(
        title_text=(
            f"x: S̄; data={range_text(np.asarray(edges_2d[0]))}; "
            f"lim={limit_text(axis_ranges_2d[0])}"
        ),
        range=list(axis_ranges_2d[0]),
        constrain="domain",
        zeroline=True,
        zerolinecolor="#202020",
        gridcolor="#d8d8d8",
        row=2,
        col=1,
    )
    figure.update_yaxes(
        title_text=(
            f"y: Π_LES = -τ:S; data={range_text(np.asarray(edges_2d[1]))}; "
            f"lim={limit_text(axis_ranges_2d[1])}"
        ),
        range=list(axis_ranges_2d[1]),
        scaleanchor="x",
        scaleratio=1.0,
        zeroline=True,
        zerolinecolor="#202020",
        gridcolor="#d8d8d8",
        row=2,
        col=1,
    )
    return figure


def write_outputs(
    output_dir: Path,
    density: np.ndarray,
    edges: Sequence[np.ndarray],
    metadata: dict[str, Any],
    *,
    density_2d: np.ndarray | None = None,
    edges_2d: Sequence[np.ndarray] | None = None,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    density_path = output_dir / "exact_density.npz"
    metadata_path = output_dir / "metadata.json"
    html_path = output_dir / "exact_density_views.html"
    if density_2d is None:
        density_2d = density.sum(axis=0, dtype=np.uint64)
    if edges_2d is None:
        edges_2d = (edges[1], edges[2])
    pdf_3d, _ = probability_density(density, edges)
    pdf_2d, _ = probability_density(density_2d, edges_2d)

    np.savez_compressed(
        density_path,
        density_3d=density,
        density_2d=density_2d,
        pdf_3d=pdf_3d,
        pdf_2d=pdf_2d,
        work_full_edges_3d=edges[0],
        s_bar_edges_3d=edges[1],
        pi_les_edges_3d=edges[2],
        s_bar_edges_2d=edges_2d[0],
        pi_les_edges_2d=edges_2d[1],
    )
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    figure = density_figure(
        density,
        edges,
        density_2d=density_2d,
        edges_2d=edges_2d,
        title=(
            f"Exact full-domain feature PDFs: frame={metadata['time_index']}, "
            f"sigma={metadata['sigma_grid']:g}, N={metadata['point_count']:,}"
        ),
    )
    figure.write_html(html_path, include_plotlyjs="cdn")
    return html_path, density_path, metadata_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Use every grid point for a 3-D (W_full, S_bar, Pi_LES) PDF "
            "cloud plus a 2-D (S_bar, Pi_LES) PDF heatmap."
        )
    )
    parser.add_argument("--config", default="configs/pipeline.yaml")
    parser.add_argument("--time-index", type=int, required=True)
    parser.add_argument("--sigma-grid", type=float, required=True)
    parser.add_argument(
        "--bins",
        type=int,
        default=DEFAULT_BINS,
        help="3-D bins per feature axis (2-256; default: 64)",
    )
    parser.add_argument(
        "--bins-2d",
        type=int,
        default=DEFAULT_BINS_2D,
        help="2-D bins per feature axis (2-4096; default: 256)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="default: scatter/output/tXXXXXX_sigma_TAG",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    result_dir = cfg.result_path(args.time_index, args.sigma_grid)
    root = open_complete_result(result_dir)
    shape, _ = _validate_source(root)
    if shape != cfg.full_shape_zyx:
        raise RuntimeError(
            f"exact scatter requires the full domain: source={shape}, "
            f"expected={cfg.full_shape_zyx}"
        )
    expected_count = int(np.prod(shape, dtype=np.int64))

    committed_bounds = _manifest_axis_bounds(result_dir)
    print("Preparing exact feature bounds...")
    bounds = exact_feature_bounds(root, committed_bounds=committed_bounds)
    print("Accumulating every grid point into independent exact 3-D/2-D bins...")
    density, edges, density_2d, edges_2d, point_count = exact_density_histograms(
        root, bounds, bins_3d=args.bins, bins_2d=args.bins_2d
    )
    if point_count != expected_count:
        raise RuntimeError(
            f"point-count closure failed: visited={point_count}, expected={expected_count}"
        )

    output_dir = args.output_dir
    if output_dir is None:
        output_dir = (
            Path(__file__).resolve().parent
            / "output"
            / cfg.result_id(args.time_index, args.sigma_grid)
        )
    pdf_3d, pdf_integral_3d = probability_density(density, edges)
    pdf_2d, pdf_integral_2d = probability_density(density_2d, edges_2d)
    top_3d, top_threshold_3d = top_pdf_mask(pdf_3d)
    top_2d, top_threshold_2d = top_pdf_mask(pdf_2d)
    _, display_log_min_3d, display_log_max_3d = pdf_display_scale(
        pdf_3d, density != 0
    )
    _, display_log_min_2d, display_log_max_2d = pdf_display_scale(
        pdf_2d, density_2d != 0
    )
    metadata = {
        "format_version": 2,
        "source_result": str(result_dir),
        "time_index": args.time_index,
        "physical_time": cfg.physical_time(args.time_index),
        "sigma_grid": float(args.sigma_grid),
        "full_shape_zyx": list(shape),
        "point_count": point_count,
        "histogram_count_3d": int(density.sum(dtype=np.uint64)),
        "histogram_count_2d": int(density_2d.sum(dtype=np.uint64)),
        "bins_per_axis_3d": args.bins,
        "bins_per_axis_2d": args.bins_2d,
        "occupied_bins_3d": int(np.count_nonzero(density)),
        "occupied_bins_2d": int(np.count_nonzero(density_2d)),
        "pdf": {
            "definition_3d": "count / (N * dW_full * dS_bar * dPi_LES)",
            "definition_2d": "count / (N * dS_bar * dPi_LES)",
            "integral_3d": pdf_integral_3d,
            "integral_2d": pdf_integral_2d,
            "top_region_definition": (
                "occupied bins with PDF at or above the 95th percentile"
            ),
            "top_threshold_3d": top_threshold_3d,
            "top_threshold_2d": top_threshold_2d,
            "top_bin_count_3d": int(np.count_nonzero(top_3d)),
            "top_bin_count_2d": int(np.count_nonzero(top_2d)),
            "display_scale": "robust log10(PDF), nonzero bins only",
            "display_log10_range_3d": [display_log_min_3d, display_log_max_3d],
            "display_log10_range_2d": [display_log_min_2d, display_log_max_2d],
            "empty_bin_rule": "integer count == 0 before PDF normalization",
        },
        "axes": {
            "x": "work_full",
            "y": "s_bar",
            "z": "pi_les = -stored pi = -tau:S",
        },
        "derived_features": {
            "delta_w": "s_bar + pi_les = work_full - work_resolved",
            "work_resolved": "work_full - s_bar - pi_les",
        },
        "bounds": {
            key: {"minimum": low, "maximum": high}
            for key, (low, high) in zip(AXIS_KEYS, bounds)
        },
        "axis_ranges_3d": {
            key: [float(edge[0]), float(edge[-1])]
            for key, edge in zip(AXIS_KEYS, edges)
        },
        "display_limits_3d": {
            key: list(nice_axis_limits(float(edge[0]), float(edge[-1])))
            for key, edge in zip(AXIS_KEYS, edges)
        },
        "bin_widths_3d": {
            key: float(edge[1] - edge[0])
            for key, edge in zip(AXIS_KEYS, edges)
        },
        "axis_ranges_2d": {
            "s_bar": [float(edges_2d[0][0]), float(edges_2d[0][-1])],
            "pi_les": [float(edges_2d[1][0]), float(edges_2d[1][-1])],
        },
        "display_limits_2d": {
            "s_bar": list(
                nice_axis_limits(float(edges_2d[0][0]), float(edges_2d[0][-1]))
            ),
            "pi_les": list(
                nice_axis_limits(float(edges_2d[1][0]), float(edges_2d[1][-1]))
            ),
        },
        "bin_widths_2d": {
            "s_bar": float(edges_2d[0][1] - edges_2d[0][0]),
            "pi_les": float(edges_2d[1][1] - edges_2d[1][0]),
        },
        "equal_numeric_unit_scale": True,
        "boundary_planes": {
            "work_full_zero": "x = 0",
            "delta_w_zero": "y + z = 0",
            "work_resolved_zero": "x - y - z = 0",
        },
        "sampling": None,
        "all_grid_points_used": True,
        "visualization_note": (
            "The displayed PDFs are normalized from exact integer bin counts; all "
            "source grid points contribute. Each axis uses its own exact range; "
            "Plotly keeps one numeric unit at the same visual scale. The 2-D density "
            "is accumulated independently at higher resolution. Raw features remain "
            "available through iter_exact_feature_chunks()."
        ),
    }
    paths = write_outputs(
        output_dir,
        density,
        edges,
        metadata,
        density_2d=density_2d,
        edges_2d=edges_2d,
    )
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
