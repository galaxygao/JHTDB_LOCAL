#!/usr/bin/env python
"""Plot two orthogonal full-domain Pi slices in their 3-D positions."""

from __future__ import annotations

import argparse
import errno
import json
import math
import sys
import uuid
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import plotly.graph_objects as go
from matplotlib import colormaps
from matplotlib import pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.store import open_complete_result


PLANE_NORMAL = {"xy": "z", "xz": "y", "yz": "x"}
AXIS_TO_ZYX = {"x": 2, "y": 1, "z": 0}


@dataclass(frozen=True)
class PlaneSlice:
    """One sampled plane with physical coordinates for a Plotly surface."""

    plane: str
    normal_axis: str
    index: int
    coordinate: float
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    values: np.ndarray


def parse_planes(value: str) -> tuple[str, ...]:
    planes = tuple(item.strip().lower() for item in value.split(",") if item.strip())
    if len(planes) not in (2, 3):
        raise argparse.ArgumentTypeError("--planes must contain two or three planes")
    if any(plane not in PLANE_NORMAL for plane in planes):
        raise argparse.ArgumentTypeError("planes must be selected from xy, xz and yz")
    if len(set(planes)) != len(planes):
        raise argparse.ArgumentTypeError("all selected planes must be different")
    return planes


def _plane_index(
    plane: str,
    shape_zyx: tuple[int, int, int],
    indices_xyz: dict[str, int | None],
) -> int:
    normal = PLANE_NORMAL[plane]
    size = shape_zyx[AXIS_TO_ZYX[normal]]
    selected = indices_xyz[normal]
    index = size // 2 if selected is None else int(selected)
    if index < 0 or index >= size:
        raise ValueError(
            f"--{normal}-index must be in [0, {size - 1}] for the {plane} plane"
        )
    return index


def extract_plane(
    field: Any,
    plane: str,
    index: int,
    *,
    sample_step: int,
    domain_length: float,
    multiplier: float = 1.0,
    include_indices_xyz: dict[str, Sequence[int]] | None = None,
) -> PlaneSlice:
    """Read one strided plane from a ``field[z, y, x]`` array."""

    if plane not in PLANE_NORMAL:
        raise ValueError(f"unknown plane: {plane}")
    if sample_step < 1:
        raise ValueError("sample_step must be positive")
    if not math.isfinite(domain_length) or domain_length <= 0:
        raise ValueError("domain_length must be finite and positive")
    shape = tuple(int(value) for value in field.shape)
    if len(shape) != 3:
        raise ValueError("Pi must be a three-dimensional field in z,y,x order")

    nz, ny, nx = shape
    include_indices_xyz = include_indices_xyz or {}

    def sampled_indices(axis: str, size: int) -> np.ndarray:
        required = [0, size - 1]
        required.extend(int(value) for value in include_indices_xyz.get(axis, ()))
        if any(value < 0 or value >= size for value in required):
            raise ValueError(f"required {axis} sample index is outside [0, {size - 1}]")
        return np.unique(
            np.concatenate(
                (
                    np.arange(0, size, sample_step, dtype=np.int64),
                    np.asarray(required, dtype=np.int64),
                )
            )
        )

    sampled = {
        "x": sampled_indices("x", nx),
        "y": sampled_indices("y", ny),
        "z": sampled_indices("z", nz),
    }
    coordinates = {
        axis: indices.astype(np.float64) * domain_length / size
        for axis, indices, size in (
            ("x", sampled["x"], nx),
            ("y", sampled["y"], ny),
            ("z", sampled["z"], nz),
        )
    }
    normal = PLANE_NORMAL[plane]
    normal_size = shape[AXIS_TO_ZYX[normal]]
    if index < 0 or index >= normal_size:
        raise ValueError(f"{plane} plane index must be in [0, {normal_size - 1}]")
    fixed_coordinate = index * domain_length / normal_size

    def orthogonal_values(*selection: Any) -> np.ndarray:
        if hasattr(field, "oindex"):
            return np.asarray(field.oindex[selection], dtype=np.float32)
        if plane == "xy":
            values = field[index][np.ix_(sampled["y"], sampled["x"])]
        elif plane == "xz":
            values = field[:, index, :][np.ix_(sampled["z"], sampled["x"])]
        else:
            values = field[:, :, index][np.ix_(sampled["z"], sampled["y"])]
        return np.asarray(values, dtype=np.float32)

    if plane == "xy":
        values = orthogonal_values(index, sampled["y"], sampled["x"])
        x, y = np.meshgrid(coordinates["x"], coordinates["y"], indexing="xy")
        z = np.full_like(x, fixed_coordinate)
    elif plane == "xz":
        values = orthogonal_values(sampled["z"], index, sampled["x"])
        x, z = np.meshgrid(coordinates["x"], coordinates["z"], indexing="xy")
        y = np.full_like(x, fixed_coordinate)
    else:
        values = orthogonal_values(sampled["z"], sampled["y"], index)
        y, z = np.meshgrid(coordinates["y"], coordinates["z"], indexing="xy")
        x = np.full_like(y, fixed_coordinate)

    values = values * np.float32(multiplier)
    if not np.all(np.isfinite(values)):
        raise ValueError(f"non-finite Pi value found on the {plane} plane")
    return PlaneSlice(
        plane=plane,
        normal_axis=normal,
        index=index,
        coordinate=float(fixed_coordinate),
        x=x,
        y=y,
        z=z,
        values=values,
    )


def extract_orthogonal_planes(
    field: Any,
    planes: Sequence[str],
    indices_xyz: dict[str, int | None],
    *,
    sample_step: int,
    domain_length: float,
    multiplier: float = 1.0,
) -> list[PlaneSlice]:
    """Extract planes while retaining every exact full-length intersection."""

    shape = tuple(int(value) for value in field.shape)
    selected = [
        (plane, _plane_index(plane, shape, indices_xyz)) for plane in planes
    ]
    fixed_indices = {PLANE_NORMAL[plane]: index for plane, index in selected}
    return [
        extract_plane(
            field,
            plane,
            index,
            sample_step=sample_step,
            domain_length=domain_length,
            multiplier=multiplier,
            include_indices_xyz={
                axis: (fixed_index,)
                for axis, fixed_index in fixed_indices.items()
                if axis != PLANE_NORMAL[plane]
            },
        )
        for plane, index in selected
    ]


def symmetric_color_limit(
    planes: Sequence[PlaneSlice], percentile: float, explicit_limit: float | None
) -> float:
    if explicit_limit is not None:
        if not math.isfinite(explicit_limit) or explicit_limit <= 0:
            raise ValueError("--color-limit must be finite and positive")
        return float(explicit_limit)
    if not 0 < percentile <= 100:
        raise ValueError("--color-percentile must be in (0, 100]")
    absolute = np.concatenate(
        [np.abs(item.values).astype(np.float64, copy=False).ravel() for item in planes]
    )
    limit = float(np.percentile(absolute, percentile))
    if not math.isfinite(limit):
        raise ValueError("could not determine a finite Pi color limit")
    if limit == 0:
        limit = float(absolute.max(initial=0.0))
    return limit if limit > 0 else 1.0


def _intersection_coordinates(
    first: PlaneSlice,
    second: PlaneSlice,
    shape_zyx: tuple[int, int, int],
    domain_length: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fixed = {
        first.normal_axis: first.coordinate,
        second.normal_axis: second.coordinate,
    }
    free_axis = next(axis for axis in ("x", "y", "z") if axis not in fixed)
    size = shape_zyx[AXIS_TO_ZYX[free_axis]]
    end = (size - 1) * domain_length / size
    coordinates = {
        axis: np.asarray([fixed[axis], fixed[axis]], dtype=np.float64)
        if axis in fixed
        else np.asarray([0.0, end], dtype=np.float64)
        for axis in ("x", "y", "z")
    }
    return coordinates["x"], coordinates["y"], coordinates["z"]


def build_figure(
    planes: Sequence[PlaneSlice],
    *,
    shape_zyx: tuple[int, int, int],
    domain_length: float,
    color_limit: float,
    title: str,
    quantity_label: str,
) -> go.Figure:
    if len(planes) not in (2, 3) or len({item.plane for item in planes}) != len(planes):
        raise ValueError("two or three different coordinate planes are required")

    figure = go.Figure()
    for item in planes:
        figure.add_trace(
            go.Surface(
                x=item.x,
                y=item.y,
                z=item.z,
                surfacecolor=item.values,
                coloraxis="coloraxis",
                name=f"{item.plane.upper()} @ {item.normal_axis}[{item.index}]",
                customdata=item.values,
                hovertemplate=(
                    f"{item.plane.upper()} plane<br>"
                    "x=%{x:.4f}<br>y=%{y:.4f}<br>z=%{z:.4f}<br>"
                    f"{quantity_label}=%{{customdata:.5e}}<extra></extra>"
                ),
                showscale=False,
                opacity=0.98,
            )
        )

    for first, second in combinations(planes, 2):
        line_x, line_y, line_z = _intersection_coordinates(
            first, second, shape_zyx, domain_length
        )
        figure.add_trace(
            go.Scatter3d(
                x=line_x,
                y=line_y,
                z=line_z,
                mode="lines",
                line={"color": "black", "width": 5},
                name=f"{first.plane.upper()}–{second.plane.upper()} intersection",
                hoverinfo="skip",
            )
        )
    figure.update_layout(
        title={"text": title, "x": 0.5},
        coloraxis={
            "colorscale": "RdBu_r",
            "cmin": -color_limit,
            "cmax": color_limit,
            "cmid": 0.0,
            "colorbar": {"title": quantity_label, "exponentformat": "e"},
        },
        scene={
            "xaxis": {"title": "x", "range": [0.0, domain_length]},
            "yaxis": {"title": "y", "range": [0.0, domain_length]},
            "zaxis": {"title": "z", "range": [0.0, domain_length]},
            "aspectmode": "cube",
            "camera": {"eye": {"x": 1.55, "y": 1.55, "z": 1.25}},
        },
        legend={"orientation": "h", "x": 0.5, "xanchor": "center", "y": 1.0},
        margin={"l": 20, "r": 110, "t": 90, "b": 20},
        width=1100,
        height=900,
    )
    return figure


def build_static_figure(
    planes: Sequence[PlaneSlice],
    *,
    shape_zyx: tuple[int, int, int],
    domain_length: float,
    color_limit: float,
    panel_label: str,
    view_elevation: float = 22.0,
    view_azimuth: float = 55.0,
    projection: str = "orthographic",
) -> Any:
    """Build a publication-style PNG figure matching the slice.png layout."""

    if len(planes) not in (2, 3) or len({item.plane for item in planes}) != len(planes):
        raise ValueError("two or three different coordinate planes are required")
    nz, ny, nx = shape_zyx
    scale = {"x": nx / domain_length, "y": ny / domain_length, "z": nz / domain_length}
    normalization = Normalize(vmin=-color_limit, vmax=color_limit)
    color_map = colormaps["bwr"]

    figure = plt.figure(figsize=(9.0, 5.1), facecolor="white")
    axis = figure.add_subplot(111, projection="3d")
    all_vertices: list[np.ndarray] = []
    all_facecolors: list[np.ndarray] = []
    for item in planes:
        coordinates = np.stack(
            (
                item.x * scale["x"],
                item.y * scale["y"],
                item.z * scale["z"],
            ),
            axis=-1,
        ).astype(np.float32, copy=False)
        vertices = np.stack(
            (
                coordinates[:-1, :-1],
                coordinates[1:, :-1],
                coordinates[1:, 1:],
                coordinates[:-1, 1:],
            ),
            axis=2,
        ).reshape(-1, 4, 3)
        face_values = 0.25 * (
            item.values[:-1, :-1]
            + item.values[1:, :-1]
            + item.values[1:, 1:]
            + item.values[:-1, 1:]
        )
        all_vertices.append(vertices)
        all_facecolors.append(color_map(normalization(face_values.reshape(-1))))

    # A separate Poly3DCollection per plane is sorted only as a whole by
    # mplot3d, which gives the wrong occlusion for intersecting surfaces.
    # One collection lets every quad from both planes participate in the same
    # painter-depth ordering, so the locally nearest plane is rendered on top.
    surface_collection = Poly3DCollection(
        np.concatenate(all_vertices, axis=0),
        facecolors=np.concatenate(all_facecolors, axis=0),
        edgecolors="none",
        linewidths=0,
        antialiased=False,
        zsort="average",
    )
    axis.add_collection3d(surface_collection)

    # Put the shared x/y origin at the front corner, as in the reference image.
    axis.set_xlim(nx - 1, 0)
    axis.set_ylim(ny - 1, 0)
    axis.set_zlim(0, nz - 1)
    # Preserve one identical display unit per grid index on all three axes.
    axis.set_box_aspect((nx - 1, ny - 1, nz - 1))
    axis.set_proj_type("ortho" if projection == "orthographic" else "persp")
    axis.view_init(elev=view_elevation, azim=view_azimuth)
    ticks = np.arange(0, min(nx, ny, nz) + 1, 200)
    axis.set_xticks(ticks[ticks <= nx])
    axis.set_yticks(ticks[ticks <= ny])
    axis.set_zticks(ticks[ticks <= nz])
    axis.set_yticklabels(
        ["" if value == 0 else str(int(value)) for value in ticks[ticks <= ny]]
    )
    axis.set_xlabel("")
    axis.set_ylabel("")
    axis.set_zlabel("")
    axis.tick_params(axis="both", which="major", labelsize=9, pad=0)
    for pane_axis in (axis.xaxis, axis.yaxis, axis.zaxis):
        pane_axis.pane.set_facecolor((1.0, 1.0, 1.0, 0.0))
        pane_axis.pane.set_edgecolor((0.88, 0.88, 0.88, 0.7))
        pane_axis._axinfo["grid"]["color"] = (0.88, 0.88, 0.88, 0.55)
        pane_axis._axinfo["grid"]["linewidth"] = 0.5

    scalar = plt.cm.ScalarMappable(norm=normalization, cmap=color_map)
    scalar.set_array([])
    colorbar = figure.colorbar(scalar, ax=axis, fraction=0.035, pad=0.045, shrink=0.78)
    colorbar.set_ticks(np.linspace(-color_limit, color_limit, 7))
    colorbar.ax.tick_params(labelsize=9, length=0)
    colorbar.outline.set_edgecolor((0.85, 0.85, 0.85, 1.0))
    colorbar.outline.set_linewidth(0.6)
    if panel_label:
        figure.text(
            0.035,
            0.91,
            panel_label,
            fontsize=18,
            fontstyle="italic",
            fontfamily="serif",
            color="black",
        )
    figure.subplots_adjust(left=0.01, right=0.88, bottom=0.02, top=0.98)
    return figure


def _replace_or_number(temporary: Path, target: Path) -> Path:
    """Replace target, or keep a numbered sibling when Windows has it open."""

    try:
        temporary.replace(target)
        return target
    except OSError as error:
        if error.errno not in (errno.EACCES, errno.EPERM, errno.EINVAL):
            raise
    for number in range(1, 1000):
        candidate = target.with_name(f"{target.stem}_{number}{target.suffix}")
        if candidate.exists():
            continue
        temporary.replace(candidate)
        return candidate
    raise RuntimeError(f"could not find an available output filename beside {target}")


def _temporary_path(target: Path) -> Path:
    return target.with_name(f".{target.stem}.{uuid.uuid4().hex}.tmp{target.suffix}")


def _atomic_json(path: Path, payload: dict[str, Any]) -> Path:
    temporary = _temporary_path(path)
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return _replace_or_number(temporary, path)


def visualize(args: argparse.Namespace) -> dict[str, Path]:
    cfg = load_config(args.config)
    result_dir = (
        args.result_dir.resolve()
        if args.result_dir is not None
        else cfg.result_path(args.time_index, args.sigma_grid)
    )
    root = open_complete_result(result_dir)
    if "pi" not in root:
        raise RuntimeError(f"result has no Pi field: {result_dir}")
    pi = root["pi"]
    shape = tuple(int(value) for value in pi.shape)
    if len(shape) != 3:
        raise RuntimeError(f"Pi field is not three-dimensional: {shape}")

    indices = {"x": args.x_index, "y": args.y_index, "z": args.z_index}
    multiplier = -1.0 if args.sign_convention == "les" else 1.0
    slices = extract_orthogonal_planes(
        pi,
        args.planes,
        indices,
        sample_step=args.sample_step,
        domain_length=cfg.domain_length,
        multiplier=multiplier,
    )
    limit = symmetric_color_limit(slices, args.color_percentile, args.color_limit)
    quantity_label = "Pi_LES = -tau:S" if args.sign_convention == "les" else "Pi = tau:S"
    title = (
        f"Orthogonal {quantity_label} slices — {result_dir.name}"
        f"<br><sup>step={args.sample_step}; symmetric color limit={limit:.5e}</sup>"
    )
    figure = build_figure(
        slices,
        shape_zyx=shape,
        domain_length=cfg.domain_length,
        color_limit=limit,
        title=title,
        quantity_label=quantity_label,
    )

    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else (Path("pi_slices") / "output" / result_dir.name).resolve()
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    slice_tag = "_".join(
        f"{item.plane}_{item.normal_axis}{item.index:04d}" for item in slices
    )
    output_stem = f"pi_orthogonal_slices_{slice_tag}"
    html_path = output_dir / f"{output_stem}.html"
    png_path = output_dir / f"{output_stem}.png"
    metadata_path = output_dir / f"{output_stem}.json"
    temporary_html = _temporary_path(html_path)
    figure.write_html(
        str(temporary_html),
        include_plotlyjs="cdn",
        full_html=True,
        config={"displaylogo": False, "scrollZoom": True, "responsive": True},
    )
    html_path = _replace_or_number(temporary_html, html_path)
    static_figure = build_static_figure(
        slices,
        shape_zyx=shape,
        domain_length=cfg.domain_length,
        color_limit=limit,
        panel_label=args.panel_label,
        view_elevation=args.view_elevation,
        view_azimuth=args.view_azimuth,
        projection=args.projection,
    )
    temporary_png = _temporary_path(png_path)
    try:
        static_figure.savefig(
            temporary_png,
            dpi=args.png_dpi,
            facecolor="white",
            format="png",
        )
    finally:
        plt.close(static_figure)
    png_path = _replace_or_number(temporary_png, png_path)
    metadata_payload = {
        "status": "complete",
        "source_result": str(result_dir),
        "source_array": "pi",
        "axis_order": ["z", "y", "x"],
        "shape_zyx": list(shape),
        "domain_length": cfg.domain_length,
        "sign_convention": (
            "Pi_LES = -stored pi = -tau:S; positive is forward cascade"
            if args.sign_convention == "les"
            else "stored pi = tau:S; positive is backscatter"
        ),
        "planes": [
            {
                "plane": item.plane,
                "normal_axis": item.normal_axis,
                "index": item.index,
                "coordinate": item.coordinate,
                "sampled_shape": list(item.values.shape),
                "value_min": float(np.min(item.values)),
                "value_max": float(np.max(item.values)),
                "absolute_value_p99": float(np.percentile(np.abs(item.values), 99.0)),
            }
            for item in slices
        ],
        "sample_step": args.sample_step,
        "sampled_value_count": sum(item.values.size for item in slices),
        "color_scale": "RdBu_r",
        "color_limit": limit,
        "shared_color_mapping": True,
        "intersection_uses_identical_source_samples": True,
        "color_percentile": None
        if args.color_limit is not None
        else args.color_percentile,
        "static_style": "D:/Xingqun_Gao/slice.png",
        "panel_label": args.panel_label,
        "png_dpi": args.png_dpi,
        "view_elevation": args.view_elevation,
        "view_azimuth": args.view_azimuth,
        "projection": args.projection,
        "html": str(html_path),
        "png": str(png_path),
    }
    metadata_path = _atomic_json(
        metadata_path,
        metadata_payload,
    )
    return {"png": png_path, "html": html_path, "metadata": metadata_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plot two or three sampled orthogonal Pi planes in physical 3-D space."
    )
    parser.add_argument("--config", default="configs/pipeline.yaml")
    parser.add_argument("--time-index", type=int, default=1)
    parser.add_argument("--sigma-grid", type=float, default=30.0)
    parser.add_argument(
        "--result-dir",
        type=Path,
        default=None,
        help="explicit completed result directory; overrides time-index/sigma lookup",
    )
    parser.add_argument(
        "--planes",
        type=parse_planes,
        default=("yz", "xz"),
        help="two or three different planes, e.g. yz,xz or yz,xy,xz",
    )
    parser.add_argument("--x-index", type=int, default=None)
    parser.add_argument("--y-index", type=int, default=None)
    parser.add_argument("--z-index", type=int, default=None)
    parser.add_argument("--sample-step", type=int, default=4)
    parser.add_argument("--color-percentile", type=float, default=99.0)
    parser.add_argument("--color-limit", type=float, default=None)
    parser.add_argument(
        "--sign-convention",
        choices=("stored", "les"),
        default="stored",
        help="stored: Pi=tau:S; les: Pi_LES=-tau:S",
    )
    parser.add_argument("--panel-label", default="(d)")
    parser.add_argument("--png-dpi", type=int, default=200)
    parser.add_argument("--view-elevation", type=float, default=22.0)
    parser.add_argument("--view-azimuth", type=float, default=55.0)
    parser.add_argument(
        "--projection",
        choices=("orthographic", "perspective"),
        default="orthographic",
        help="orthographic preserves equal displayed scale; perspective adds foreshortening",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.sample_step < 1:
            raise ValueError("--sample-step must be positive")
        if args.png_dpi < 72:
            raise ValueError("--png-dpi must be at least 72")
        outputs = visualize(args)
    except Exception as error:
        print(f"Pi orthogonal-slice visualization failed: {error}", file=sys.stderr)
        return 1
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
