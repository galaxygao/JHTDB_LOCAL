from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
import zarr


PRESSURE_NAMES = ("pressure", "p", "P")


class PreflightError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArrayRef:
    path: Path
    key: str | None
    shape: tuple[int, ...]


def _store_keys(path: Path) -> set[str]:
    if path.suffix.lower() == ".npy":
        return {""}
    if path.suffix.lower() == ".npz":
        with np.load(path) as data:
            return set(data.files)
    root = zarr.open_group(str(path), mode="r")
    return set(root.array_keys())


def _shape(path: Path, key: str | None) -> tuple[int, ...]:
    if path.suffix.lower() == ".npy":
        return tuple(np.load(path, mmap_mode="r").shape)
    if path.suffix.lower() == ".npz":
        with np.load(path) as data:
            if key not in data:
                raise PreflightError(f"array {key!r} is absent from {path}")
            return tuple(data[key].shape)
    root = zarr.open_group(str(path), mode="r")
    if key not in root:
        raise PreflightError(f"array {key!r} is absent from {path}")
    return tuple(root[key].shape)


def _ref(path_value: Any, key: str | None, label: str) -> ArrayRef:
    if not path_value:
        raise PreflightError(f"{label} path is not configured")
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise PreflightError(f"{label} path does not exist: {path}")
    keys = _store_keys(path)
    actual_key = key
    if path.suffix.lower() == ".npy":
        actual_key = None
    elif actual_key not in keys:
        raise PreflightError(
            f"{label} array {actual_key!r} is absent from {path}; available={sorted(keys)}"
        )
    return ArrayRef(path, actual_key, _shape(path, actual_key))


def _load(ref: ArrayRef) -> np.ndarray:
    suffix = ref.path.suffix.lower()
    if suffix == ".npy":
        result = np.load(ref.path)
    elif suffix == ".npz":
        with np.load(ref.path) as data:
            result = np.asarray(data[ref.key])
    else:
        result = np.asarray(zarr.open_group(str(ref.path), mode="r")[ref.key])
    return np.asarray(result)


def preflight_frame(frame: dict[str, Any]) -> dict[str, Any]:
    label = f"frame {frame.get('frame', '?')}"
    velocity = _ref(frame.get("velocity_path"), frame.get("velocity_key", "velocity"), f"{label} velocity")
    if len(velocity.shape) != 4 or velocity.shape[0] != 3:
        raise PreflightError(f"{label} velocity must have shape (3,z,y,x), got {velocity.shape}")
    spatial = velocity.shape[1:]

    pressure_ref: ArrayRef | None = None
    gradient_refs: list[ArrayRef] = []
    pressure_path = frame.get("pressure_path")
    gradient_path = frame.get("pressure_gradient_path")
    if pressure_path:
        pressure_ref = _ref(pressure_path, frame.get("pressure_key", "pressure"), f"{label} pressure")
        if pressure_ref.shape != spatial:
            raise PreflightError(f"{label} pressure shape {pressure_ref.shape} != velocity shape {spatial}")
    elif gradient_path:
        gradient_store = Path(gradient_path)
        if gradient_store.is_dir():
            attrs = zarr.open_group(str(gradient_store), mode="r").attrs
            if attrs.get("source") == "JHTDB getData":
                if attrs.get("status") != "validated":
                    raise PreflightError(f"{label} managed pressure-gradient cache has not passed validation")
                if attrs.get("time_index") != frame.get("frame") or attrs.get("physical_time") != frame.get("time"):
                    raise PreflightError(f"{label} pressure-gradient frame/time metadata mismatch")
        keys = frame.get("pressure_gradient_keys", ["dPdx", "dPdy", "dPdz"])
        if len(keys) == 1:
            combined = _ref(gradient_path, keys[0], f"{label} pressure gradient")
            if combined.shape != (3, *spatial):
                raise PreflightError(f"{label} pressure gradient must have shape {(3, *spatial)}, got {combined.shape}")
            gradient_refs = [combined]
        elif len(keys) == 3:
            gradient_refs = [_ref(gradient_path, key, f"{label} pressure gradient {key}") for key in keys]
            if any(ref.shape != spatial for ref in gradient_refs):
                raise PreflightError(f"{label} pressure-gradient shapes must equal {spatial}")
        else:
            raise PreflightError(f"{label} pressure_gradient_keys must contain one or three names")
    else:
        raise PreflightError(
            f"{label} has velocity but no pressure_path or pressure_gradient_path; pressure data is required"
        )
    return {"velocity": velocity, "pressure": pressure_ref, "gradients": gradient_refs, "shape": spatial}


def preflight(config: dict[str, Any]) -> list[dict[str, Any]]:
    frames = config.get("frames", [])
    if not frames:
        raise PreflightError("config.frames is empty")
    if config.get("axis_order", "zyx") != "zyx":
        raise PreflightError("this implementation requires stored spatial axis order zyx")
    if config.get("event_mode", "positive") not in {"positive", "negative", "absolute"}:
        raise PreflightError("event_mode must be positive, negative, or absolute")
    periodic = tuple(config.get("periodic_xyz", [True, True, True]))
    method = config.get("gradient_method", "spectral")
    if method == "spectral" and periodic != (True, True, True):
        raise PreflightError("spectral pressure gradients require a periodic domain on all axes")
    return [preflight_frame(frame) for frame in frames]


def pressure_gradient(pressure: np.ndarray, lengths_xyz: Iterable[float], method: str) -> np.ndarray:
    lx, ly, lz = map(float, lengths_xyz)
    nz, ny, nx = pressure.shape
    if method == "finite_difference":
        dz, dy, dx = lz / nz, ly / ny, lx / nx
        dpdz, dpdy, dpdx = np.gradient(pressure, dz, dy, dx, edge_order=2)
        return np.stack((dpdx, dpdy, dpdz))
    if method != "spectral":
        raise ValueError(f"unknown gradient_method {method!r}")
    spectrum = np.fft.fftn(pressure)
    waves = (
        2 * np.pi * np.fft.fftfreq(nx, d=lx / nx),
        2 * np.pi * np.fft.fftfreq(ny, d=ly / ny),
        2 * np.pi * np.fft.fftfreq(nz, d=lz / nz),
    )
    return np.stack([
        np.fft.ifftn(1j * waves[0][None, None, :] * spectrum).real,
        np.fft.ifftn(1j * waves[1][None, :, None] * spectrum).real,
        np.fft.ifftn(1j * waves[2][:, None, None] * spectrum).real,
    ])


def core_fields(velocity: np.ndarray, gradient: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    if velocity.shape != gradient.shape or velocity.shape[0] != 3:
        raise ValueError("velocity and pressure gradient must share shape (3,z,y,x)")
    q = -np.einsum("izyx,izyx->zyx", velocity, gradient, optimize=True)
    u2 = np.einsum("izyx,izyx->zyx", velocity, velocity, optimize=True)
    return q, u2, float(np.sqrt(np.mean(q * q))), float(np.mean(u2))


def event_mask(q: np.ndarray, q_rms: float, alpha: float, mode: str) -> np.ndarray:
    if mode == "positive": return q > alpha * q_rms
    if mode == "negative": return q < -alpha * q_rms
    return np.abs(q) > alpha * q_rms


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows: return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def conditional_rows(q: np.ndarray, u2: np.ndarray, q_rms: float, u2_mean: float,
                     edges: np.ndarray, min_count: int) -> list[dict[str, Any]]:
    x = u2.ravel() / u2_mean
    values = q.ravel()
    index = np.searchsorted(edges, x, side="right") - 1
    index[x == edges[-1]] = len(edges) - 2
    rows = []
    total = x.size
    for i in range(len(edges) - 1):
        mask = index == i
        count = int(mask.sum())
        mean = float(values[mask].mean()) if count else math.nan
        rows.append({
            "bin_left": edges[i], "bin_right": edges[i + 1], "bin_center": (edges[i] + edges[i + 1]) / 2,
            "u2_bin_left": edges[i] * u2_mean, "u2_bin_right": edges[i + 1] * u2_mean,
            "u2_bin_center": (edges[i] + edges[i + 1]) * u2_mean / 2,
            "count": count, "probability": count / total, "valid": count >= min_count,
            "conditional_q": mean, "conditional_q_normalized": mean / q_rms if q_rms else math.nan,
        })
    return rows


def plot_slices(q: np.ndarray, destination: Path, title: str) -> None:
    nz, ny, nx = q.shape
    slices = [(q[nz // 2], "XY"), (q[:, ny // 2, :], "XZ"), (q[:, :, nx // 2], "YZ")]
    limit = float(np.percentile(np.abs(q), 99.5))
    if not np.isfinite(limit) or limit == 0: limit = 1.0
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for axis, (data, name) in zip(axes, slices):
        image = axis.imshow(data, origin="lower", cmap="coolwarm", vmin=-limit, vmax=limit, aspect="auto")
        axis.set_title(name); fig.colorbar(image, ax=axis, shrink=.75)
    fig.suptitle(title); fig.tight_layout(); fig.savefig(destination, dpi=160); plt.close(fig)


def plot_conditional(rows: list[dict[str, Any]], destination: Path, title: str) -> None:
    x = np.array([r["bin_center"] for r in rows])
    y = np.array([r["conditional_q_normalized"] if r["valid"] else np.nan for r in rows])
    fig, axis = plt.subplots(figsize=(7, 5)); axis.axhline(0, color="black", linewidth=.8)
    axis.plot(x, y); axis.set(xlabel=r"$u^2/\langle u^2\rangle$", ylabel=r"$\langle q|u^2\rangle/q_{rms}$", title=title)
    fig.tight_layout(); fig.savefig(destination, dpi=160); plt.close(fig)


def voxel_surface(mask: np.ndarray, stride: int, full_shape: tuple[int, ...]):
    """Exposed cube faces; adjacent cells of the same class share no inner face."""
    padded = np.pad(mask, 1)
    vertices, triangles = [], []
    offset = 0
    # Axis order here is z,y,x; each face has four corners and two triangles.
    for axis in range(3):
        other = [a for a in range(3) if a != axis]
        for side in (0, 1):
            neighbor = [slice(1, -1)] * 3
            neighbor[axis] = slice(0, -2) if side == 0 else slice(2, None)
            origins = np.argwhere(mask & ~padded[tuple(neighbor)])
            if not len(origins):
                continue
            corners = np.zeros((4, 3), dtype=np.int32)
            corners[:, axis] = side
            corners[:, other[0]] = [0, 1, 1, 0]
            corners[:, other[1]] = [0, 0, 1, 1]
            points = (origins[:, None, :] + corners[None, :, :]) * stride - .5
            points = np.minimum(points, np.asarray(full_shape) - .5)
            vertices.append(points.reshape(-1, 3)[:, ::-1])
            faces = np.arange(len(origins))[:, None, None] * 4 + np.array([[0, 1, 2], [0, 2, 3]])
            triangles.append(faces.reshape(-1, 3) + offset)
            offset += len(origins) * 4
    if not vertices:
        return np.empty((0, 3)), np.empty((0, 3), dtype=int)
    return np.concatenate(vertices), np.concatenate(triangles)


def region_html(mask_a: np.ndarray, mask_b: np.ndarray | None, destination: Path,
                names: tuple[str, str] = ("A", "B"), stride: int = 1) -> None:
    stride = max(1, int(stride))
    if mask_b is not None and mask_b.shape != mask_a.shape:
        raise ValueError('Overlay masks must have the same shape')
    fig = go.Figure()
    if mask_b is None:
        regions = [(mask_a, names[0], '#e76f51', .40)]
    else:
        regions = [(mask_a & ~mask_b, f'{names[0]} only', '#e76f51', .35),
                   (mask_b & ~mask_a, f'{names[1]} only', '#3399dd', .35),
                   (mask_a & mask_b, 'A intersection B', '#a83ed1', .65)]
    for mask, name, color, opacity in regions:
        z, y, x = np.nonzero(mask[::stride, ::stride, ::stride])
        fig.add_trace(go.Scatter3d(x=x * stride, y=y * stride, z=z * stride,
            mode='markers', marker=dict(size=2, color=color, opacity=opacity),
            name=name, showlegend=True,
            hovertemplate=name + '<extra></extra>'))
    nz, ny, nx = mask_a.shape
    fig.update_layout(title=f'Grid points | display stride={stride} | local grid coordinates',
        scene=dict(aspectmode='data', xaxis=dict(title='x', range=[-.5, nx-.5]),
                   yaxis=dict(title='y', range=[-.5, ny-.5]),
                   zaxis=dict(title='z', range=[-.5, nz-.5])),
        margin=dict(l=0, r=0, t=55, b=0), legend=dict(itemsizing='constant'))
    fig.write_html(destination, include_plotlyjs=True)


def _gradient_from_refs(info: dict[str, Any], config: dict[str, Any]) -> tuple[np.ndarray, str]:
    if info["pressure"] is not None:
        pressure = _load(info["pressure"])
        return pressure_gradient(pressure, config["domain_lengths_xyz"], config.get("gradient_method", "spectral")), "computed_from_pressure"
    refs = info["gradients"]
    if len(refs) == 1: return _load(refs[0]), "supplied_combined_gradient"
    return np.stack([_load(ref) for ref in refs]), "supplied_component_gradients"


def run(config: dict[str, Any], infos: list[dict[str, Any]]) -> Path:
    # Preflight has completed before this function is entered or creates output.
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(config.get("output_root", "outputs/qpower_analysis")) / run_id
    if root.exists(): raise RuntimeError(f"refusing to overwrite {root}")
    root.mkdir(parents=True); (root / "aggregate").mkdir()
    (root / "config_used.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    percentiles = []
    for info in infos:
        velocity = _load(info["velocity"]); u2 = np.einsum("izyx,izyx->zyx", velocity, velocity)
        mean = float(u2.mean()); percentiles.append(float(np.percentile(u2 / mean, config.get("conditional_percentile", 99.9))))
        del velocity, u2
    upper = max(percentiles); edges = np.linspace(0, upper, int(config.get("n_conditional_bins", 60)) + 1)
    summary_rows, threshold_rows, overlap_rows, all_conditional = [], [], [], []
    mode = config.get("event_mode", "positive"); alphas = config.get("alphas", [1,2,3,4]); betas = config.get("betas", [1,1.5,2,3])
    for frame_cfg, info in zip(config["frames"], infos):
        velocity = _load(info["velocity"]); gradient, gradient_source = _gradient_from_refs(info, config)
        if not np.isfinite(velocity).all() or not np.isfinite(gradient).all(): raise RuntimeError(f"frame {frame_cfg['frame']} contains NaN or Inf")
        q, u2, q_rms, u2_mean = core_fields(velocity, gradient)
        frame_dir = root / f"frame_{int(frame_cfg['frame']):06d}"; frame_dir.mkdir(); (frame_dir / "alpha_events").mkdir(); (frame_dir / "beta_events").mkdir(); (frame_dir / "overlays").mkdir()
        summary = {"frame": frame_cfg["frame"], "time": frame_cfg["time"], "q_min": q.min(), "q_max": q.max(), "q_mean": q.mean(), "q_rms": q_rms, "u2_min": u2.min(), "u2_max": u2.max(), "u2_mean": u2_mean, "fraction_q_positive": np.mean(q > 0)}
        summary_rows.append(summary); _write_csv(frame_dir / "frame_summary.csv", [summary])
        plot_slices(q, frame_dir / "qpower_slices.png", f"frame={frame_cfg['frame']} t={frame_cfg['time']} q_rms={q_rms:.6g}")
        cond = conditional_rows(q, u2, q_rms, u2_mean, edges, int(config.get("min_bin_count", 100)))
        for row in cond: row.update(frame=frame_cfg["frame"], time=frame_cfg["time"])
        _write_csv(frame_dir / "conditional_q_given_u2.csv", cond); plot_conditional(cond, frame_dir / "conditional_q_given_u2.png", f"frame={frame_cfg['frame']} t={frame_cfg['time']}"); all_conditional.extend(cond)
        a_masks = {float(a): event_mask(q, q_rms, float(a), mode) for a in alphas}; b_masks = {float(b): u2 > float(b) * u2_mean for b in betas}
        stride = int(config.get("visualization_stride", 1))
        for a, mask in a_masks.items():
            threshold_rows.append({"frame": frame_cfg["frame"], "time": frame_cfg["time"], "kind": "alpha", "threshold": a, "count": int(mask.sum()), "fraction": float(mask.mean()), "event_mode": mode})
            region_html(mask, None, frame_dir / "alpha_events" / f"alpha_{a}.html", (f"A alpha={a}", ""), stride)
        for b, mask in b_masks.items():
            threshold_rows.append({"frame": frame_cfg["frame"], "time": frame_cfg["time"], "kind": "beta", "threshold": b, "count": int(mask.sum()), "fraction": float(mask.mean()), "event_mode": mode})
            region_html(mask, None, frame_dir / "beta_events" / f"beta_{b}.html", (f"B beta={b}", ""), stride)
        pairs = config.get("overlay_pairs") or [[a,b] for a in alphas for b in betas]
        for a, b in pairs:
            aa, bb = float(a), float(b); am, bm = a_masks[aa], b_masks[bb]; inter = am & bm; ac, bc, ic = int(am.sum()), int(bm.sum()), int(inter.sum())
            overlap_rows.append({"frame": frame_cfg["frame"], "time": frame_cfg["time"], "alpha": aa, "beta": bb, "a_count": ac, "b_count": bc, "intersection_count": ic, "a_fraction": ac/am.size, "b_fraction": bc/bm.size, "intersection_fraction": ic/am.size, "p_a_given_b": ic/bc if bc else math.nan, "p_b_given_a": ic/ac if ac else math.nan, "event_mode": mode})
            region_html(am, bm, frame_dir / "overlays" / f"alpha_{aa}_beta_{bb}.html", (f"A {mode}, alpha={aa}", f"B beta={bb}"), stride)
        metadata = {"frame": frame_cfg["frame"], "gradient_source": gradient_source, "shape_zyx": list(q.shape), "conditional_points_above_upper": int(np.sum(u2/u2_mean > upper)), "conditional_upper": upper}
        (frame_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        del velocity, gradient, q, u2
    _write_csv(root / "run_summary.csv", summary_rows); _write_csv(root / "threshold_statistics.csv", threshold_rows); _write_csv(root / "overlap_statistics.csv", overlap_rows)
    _write_csv(root / "aggregate" / "conditional_q_given_u2_all_frames.csv", all_conditional)
    aggregate = []
    for i in range(len(edges)-1):
        values = [float(r["conditional_q_normalized"]) for r in all_conditional if r["bin_left"] == edges[i] and r["valid"] and np.isfinite(r["conditional_q_normalized"])]
        aggregate.append({"bin_left": edges[i], "bin_right": edges[i+1], "bin_center": (edges[i]+edges[i+1])/2, "valid_frames": len(values), "mean": np.mean(values) if values else math.nan, "std": np.std(values, ddof=1) if len(values)>1 else math.nan})
    _write_csv(root / "aggregate" / "conditional_q_given_u2_ensemble.csv", aggregate)
    metadata = {"created_utc": datetime.now(timezone.utc).isoformat(), "pressure_preflight": "passed", "frames": [f["frame"] for f in config["frames"]], "common_conditional_edges": edges.tolist(), "pressure_definition": config.get("pressure_definition", "unspecified"), "axis_order": "zyx"}
    (root / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="3-D pressure-power analysis")
    parser.add_argument("--config", required=True, type=Path); parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8")); infos = preflight(config)
        print(f"Pressure preflight passed for {len(infos)} frame(s).")
        if args.preflight_only: return 0
        print(f"Analysis complete: {run(config, infos)}"); return 0
    except (PreflightError, OSError, ValueError, KeyError) as exc:
        print(f"PRECHECK FAILED: {exc}", file=sys.stderr); return 2


if __name__ == "__main__":
    raise SystemExit(main())
