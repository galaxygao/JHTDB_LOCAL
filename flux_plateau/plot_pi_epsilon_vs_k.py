from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

import plotly.graph_objects as go

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.dashboard import complete_result_paths
from jhtdb_pipeline.validation import atomic_json


ANALYSIS_VERSION = 2
DEFAULT_VISCOSITY = 0.000185
DEFAULT_EPSILON_REFERENCE = 0.0928
DEFAULT_ETA_REFERENCE = 0.00287
HALF_GAIN_KR = math.sqrt(24.0 * math.log(2.0))
PAPER_R_OVER_ETA = (
    4.0, 8.0, 13.0, 17.0, 25.0, 40.0, 80.0,
    120.0, 180.0, 250.0, 400.0, 700.0, 1300.0, 1600.0,
)
PAPER_FLUX_OVER_EPSILON = (
    0.012, 0.20, 0.55, 0.72, 0.95, 1.25, 1.35,
    1.40, 1.40, 1.38, 1.30, 1.15, 0.75, 0.45,
)


@dataclass(frozen=True)
class FluxPoint:
    group_key: tuple[str, float]
    group_label: str
    sigma_grid: float
    cutoff_wavenumber: float
    cutoff_modes: float
    stored_mean_pi: float
    forward_mean_pi: float
    pi_over_epsilon: float
    source_path: Path
    equivalent_r_over_eta: float
    note: str = "computed result"


def _smooth_group(manifest: dict) -> tuple[tuple[str, float], str]:
    value = float(manifest["sharp_edge_width_fraction"])
    return ("fraction_of_cutoff", value), f"smooth-sharp: α={value:g}"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_flux_inputs(
    result_root: Path,
    time_index: int,
) -> tuple[list[tuple[Path, dict, dict]], float]:
    records: list[tuple[Path, dict, dict]] = []
    gradient_rms_values: list[float] = []
    for path in complete_result_paths(result_root):
        manifest_path = path / "manifest.json"
        cq_path = path / "cq.json"
        qa_path = path / "qa.json"
        if not (manifest_path.is_file() and cq_path.is_file() and qa_path.is_file()):
            continue
        manifest = _read_json(manifest_path)
        if (
            int(manifest.get("time_index", -1)) != time_index
            or manifest.get("filter_type", "gaussian")
            not in ("gaussian", "smooth_sharp")
        ):
            continue
        cq = _read_json(cq_path)
        qa = _read_json(qa_path)
        gradient_rms_values.append(
            float(qa["divergence"]["unfiltered"]["gradient_rms"])
        )
        records.append((path, manifest, cq))
    if not records:
        raise RuntimeError(f"no complete smooth-sharp results for frame {time_index}")
    reference = gradient_rms_values[0]
    if any(
        not math.isclose(value, reference, rel_tol=1e-12, abs_tol=0.0)
        for value in gradient_rms_values[1:]
    ):
        raise RuntimeError("results disagree on the full-domain raw-gradient RMS")
    return records, reference


def build_flux_points(
    records: list[tuple[Path, dict, dict]],
    *,
    grid_size: int,
    domain_length: float,
    epsilon_reference: float,
    eta_reference: float,
) -> list[FluxPoint]:
    dx = domain_length / grid_size
    delta_k = 2.0 * math.pi / domain_length
    points: list[FluxPoint] = []
    for path, manifest, cq in records:
        sigma = float(manifest["sigma_grid"])
        filter_type = manifest.get("filter_type", "gaussian")
        if filter_type == "smooth_sharp":
            cutoff = math.pi / (sigma * dx)
            group_key, group_label = _smooth_group(manifest)
        else:
            cutoff = math.sqrt(2.0 * math.log(2.0)) / (sigma * dx)
            group_key, group_label = ("gaussian", 0.0), "Gaussian"
        stored_mean = float(cq["global"]["field_means"]["pi"])
        points.append(
            FluxPoint(
                group_key=group_key,
                group_label=group_label,
                sigma_grid=sigma,
                cutoff_wavenumber=cutoff,
                cutoff_modes=cutoff / delta_k,
                stored_mean_pi=stored_mean,
                forward_mean_pi=-stored_mean,
                pi_over_epsilon=-stored_mean / epsilon_reference,
                source_path=path,
                equivalent_r_over_eta=HALF_GAIN_KR / (cutoff * eta_reference),
            )
        )

    for r_over_eta, flux_over_epsilon in zip(
        PAPER_R_OVER_ETA, PAPER_FLUX_OVER_EPSILON
    ):
        cutoff_eta = HALF_GAIN_KR / r_over_eta
        cutoff = cutoff_eta / eta_reference
        points.append(
            FluxPoint(
                group_key=("paper", 0.0),
                group_label="Paper reference",
                sigma_grid=math.nan,
                cutoff_wavenumber=cutoff,
                cutoff_modes=cutoff / delta_k,
                stored_mean_pi=math.nan,
                forward_mean_pi=math.nan,
                pi_over_epsilon=flux_over_epsilon,
                source_path=Path("paper_reference"),
                equivalent_r_over_eta=r_over_eta,
                note="paper data",
            )
        )
    return points


def make_figure(
    points: list[FluxPoint], epsilon_reference: float
) -> go.Figure:
    figure = go.Figure()
    group_keys = sorted({point.group_key for point in points})
    for group_key in group_keys:
        group = sorted(
            (point for point in points if point.group_key == group_key),
            key=lambda point: point.equivalent_r_over_eta,
        )
        figure.add_trace(
            go.Scatter(
                x=[point.equivalent_r_over_eta for point in group],
                y=[point.pi_over_epsilon for point in group],
                mode="lines+markers",
                name=group[0].group_label,
                line={"dash": "dot" if group_key[0] == "paper" else "solid"},
                marker={
                    "size": 10,
                    "symbol": [
                        "square-open"
                        if point.note == "paper data"
                        else "circle"
                        for point in group
                    ],
                },
                customdata=[
                    [
                        "n/a" if math.isnan(point.sigma_grid) else f"{point.sigma_grid:g}",
                        point.equivalent_r_over_eta,
                        point.cutoff_modes,
                        point.cutoff_wavenumber,
                        "n/a" if math.isnan(point.forward_mean_pi) else f"{point.forward_mean_pi:.8g}",
                        point.note,
                    ]
                    for point in group
                ],
                hovertemplate=(
                    "r_eq/eta=%{x:.6g}<br>"
                    "&lt;Π_forward&gt;/ε=%{y:.6f}<br>"
                    "sigma=%{customdata[0]}<br>"
                    "k_1/2/Δk=%{customdata[2]:.6g}<br>"
                    "k_1/2=%{customdata[3]:.6g}<br>"
                    "&lt;Π_forward&gt;=%{customdata[4]}<br>"
                    "%{customdata[5]}<extra>%{fullData.name}</extra>"
                ),
            )
        )
    figure.add_hrect(
        y0=0.95,
        y1=1.05,
        fillcolor="gray",
        opacity=0.10,
        line_width=0,
        annotation_text="±5%",
        annotation_position="top left",
    )
    figure.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="black",
        annotation_text="inertial plateau = 1",
        annotation_position="top right",
    )
    figure.update_layout(
        title=f"Mean forward energy-flux vs Gaussian-equivalent scale (ε={epsilon_reference:.4g})",
        xaxis={
            "title": "Gaussian-equivalent scale r_eq / η (linear)",
            "type": "linear",
        },
        yaxis={"title": "<Π_forward> / ε", "type": "linear"},
        legend={"title": "Filter"},
        template="plotly_white",
        hovermode="closest",
    )
    return figure


def make_log_k_figure(
    points: list[FluxPoint], epsilon_reference: float
) -> go.Figure:
    """Plot the same flux data against the common half-gain wavenumber."""
    figure = go.Figure()
    group_keys = sorted({point.group_key for point in points})
    for group_key in group_keys:
        group = sorted(
            (point for point in points if point.group_key == group_key),
            key=lambda point: point.cutoff_wavenumber,
        )
        figure.add_trace(
            go.Scatter(
                x=[point.cutoff_wavenumber for point in group],
                y=[point.pi_over_epsilon for point in group],
                mode="lines+markers",
                name=group[0].group_label,
                line={"dash": "dot" if group_key[0] == "paper" else "solid"},
                marker={
                    "size": 10,
                    "symbol": [
                        "square-open"
                        if point.note == "paper data"
                        else "circle"
                        for point in group
                    ],
                },
                customdata=[
                    [
                        "n/a" if math.isnan(point.sigma_grid) else f"{point.sigma_grid:g}",
                        point.equivalent_r_over_eta,
                        point.cutoff_modes,
                        "n/a" if math.isnan(point.forward_mean_pi) else f"{point.forward_mean_pi:.8g}",
                        point.note,
                    ]
                    for point in group
                ],
                hovertemplate=(
                    "k_1/2=%{x:.6g}<br>"
                    "&lt;Π_forward&gt;/ε=%{y:.6f}<br>"
                    "sigma=%{customdata[0]}<br>"
                    "r_eq/eta=%{customdata[1]:.6g}<br>"
                    "k_1/2/Δk=%{customdata[2]:.6g}<br>"
                    "&lt;Π_forward&gt;=%{customdata[3]}<br>"
                    "%{customdata[4]}<extra>%{fullData.name}</extra>"
                ),
            )
        )
    figure.add_hrect(
        y0=0.95,
        y1=1.05,
        fillcolor="gray",
        opacity=0.10,
        line_width=0,
        annotation_text="±5%",
        annotation_position="top left",
    )
    figure.add_hline(
        y=1.0,
        line_dash="dash",
        line_color="black",
        annotation_text="inertial plateau = 1",
        annotation_position="top right",
    )
    figure.update_layout(
        title=f"Mean forward energy-flux vs half-gain wavenumber (ε={epsilon_reference:.4g})",
        xaxis={"title": "half-gain wavenumber k_1/2 (log scale)", "type": "log"},
        yaxis={"title": "<Π_forward> / ε", "type": "linear"},
        legend={"title": "Filter"},
        template="plotly_white",
        hovermode="closest",
    )
    return figure


def write_outputs(
    output_dir: Path,
    points: list[FluxPoint],
    *,
    epsilon_reference: float,
    viscosity: float,
    raw_gradient_rms: float,
    eta_reference: float,
    epsilon_instantaneous: float,
    eta_instantaneous: float,
    time_index: int,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "pi_over_epsilon_vs_r_eta_linear.html"
    figure = make_figure(points, epsilon_reference)
    figure.write_html(
        str(html_path), include_plotlyjs=True, full_html=True
    )
    log_k_path = output_dir / "pi_over_epsilon_vs_log_k.html"
    make_log_k_figure(points, epsilon_reference).write_html(
        str(log_k_path),
        include_plotlyjs=True,
        full_html=True,
    )
    figure.write_html(
        str(output_dir / "pi_over_epsilon_vs_r_eta.html"),
        include_plotlyjs=True,
        full_html=True,
    )
    csv_path = output_dir / "pi_over_epsilon_vs_r_eta.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "filter",
                "sigma_grid",
                "equivalent_r_over_eta",
                "cutoff_wavenumber",
                "cutoff_modes",
                "stored_mean_pi",
                "forward_mean_pi",
                "epsilon_reference",
                "forward_mean_pi_over_epsilon",
                "note",
                "source_path",
            )
        )
        for point in sorted(points, key=lambda item: (item.group_label, item.cutoff_wavenumber)):
            writer.writerow(
                (
                    point.group_label,
                    point.sigma_grid,
                    point.equivalent_r_over_eta,
                    point.cutoff_wavenumber,
                    point.cutoff_modes,
                    point.stored_mean_pi,
                    point.forward_mean_pi,
                    epsilon_reference,
                    point.pi_over_epsilon,
                    point.note,
                    point.source_path,
                )
            )
    atomic_json(
        output_dir / "pi_over_epsilon_vs_r_eta.json",
        {
            "analysis_version": ANALYSIS_VERSION,
            "time_index": time_index,
            "definition": "-mean(stored pi) / epsilon_reference",
            "stored_pi_definition": "tau_ij * d_j(velocity_bar_i)",
            "epsilon_definition": "nu * mean(sum_ij (d_j u_i)^2)",
            "viscosity": viscosity,
            "raw_gradient_component_rms": raw_gradient_rms,
            "epsilon_reference": epsilon_reference,
            "eta_reference": eta_reference,
            "epsilon_instantaneous_diagnostic": epsilon_instantaneous,
            "eta_instantaneous_diagnostic": eta_instantaneous,
            "x_definition": "Gaussian-equivalent r_eq / eta_reference",
            "equivalent_scale_definition": "k_1/2 * r_eq = sqrt(24 ln 2)",
            "point_count": len(points),
            "html": html_path.name,
            "log_k_html": log_k_path.name,
            "csv": csv_path.name,
        },
    )
    return html_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plot mean forward Pi/epsilon against Gaussian-equivalent r/eta"
    )
    parser.add_argument("--config", default="configs/pipeline.yaml")
    parser.add_argument("--time-index", type=int, required=True)
    parser.add_argument("--viscosity", type=float, default=DEFAULT_VISCOSITY)
    parser.add_argument(
        "--epsilon-reference", type=float, default=DEFAULT_EPSILON_REFERENCE
    )
    parser.add_argument("--eta-reference", type=float, default=DEFAULT_ETA_REFERENCE)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    for name in ("viscosity", "epsilon_reference", "eta_reference"):
        value = getattr(args, name)
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
    cfg = load_config(args.config)
    records, raw_gradient_rms = discover_flux_inputs(
        cfg.result_root, args.time_index
    )
    epsilon_instantaneous = args.viscosity * 9.0 * raw_gradient_rms**2
    eta_instantaneous = (args.viscosity**3 / epsilon_instantaneous) ** 0.25
    points = build_flux_points(
        records,
        grid_size=cfg.grid_shape[0],
        domain_length=cfg.domain_length,
        epsilon_reference=args.epsilon_reference,
        eta_reference=args.eta_reference,
    )
    output_dir = args.output_dir or (
        Path(__file__).resolve().parent / "output" / f"t{args.time_index:06d}"
    )
    print(
        write_outputs(
            output_dir,
            points,
            epsilon_reference=args.epsilon_reference,
            viscosity=args.viscosity,
            raw_gradient_rms=raw_gradient_rms,
            eta_reference=args.eta_reference,
            epsilon_instantaneous=epsilon_instantaneous,
            eta_instantaneous=eta_instantaneous,
            time_index=args.time_index,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
