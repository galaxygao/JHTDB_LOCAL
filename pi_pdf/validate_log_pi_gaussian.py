from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from jhtdb_pipeline.config import FILTER_TYPES, load_config
from jhtdb_pipeline.store import open_complete_result, spatial_slices
from jhtdb_pipeline.validation import atomic_json


BRANCHES = ("forward", "backscatter")


def sigma_text(sigma: float) -> str:
    return format(float(sigma), ".8g")


def _parse_sigmas(text: str) -> list[float]:
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values or len(set(values)) != len(values) or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("sigmas must be unique positive values")
    return values


def _normal_pdf(y: np.ndarray, mean: float, standard_deviation: float) -> np.ndarray:
    scale = max(float(standard_deviation), np.finfo(float).tiny)
    return np.exp(-0.5 * np.square((y - mean) / scale)) / (math.sqrt(2.0 * math.pi) * scale)


def _normal_cdf(y: np.ndarray, mean: float, standard_deviation: float) -> np.ndarray:
    scale = max(float(standard_deviation), np.finfo(float).tiny)
    return 0.5 * (1.0 + np.vectorize(math.erf)((y - mean) / (math.sqrt(2.0) * scale)))


def _r2(observed: np.ndarray, predicted: np.ndarray) -> float | None:
    denominator = float(np.sum(np.square(observed - np.mean(observed))))
    if denominator <= 0.0:
        return None
    return 1.0 - float(np.sum(np.square(observed - predicted))) / denominator


def _weighted_quantiles_from_hist(
    edges: np.ndarray, weights: np.ndarray, probabilities: Sequence[float]
) -> np.ndarray:
    cumulative = np.cumsum(np.asarray(weights, dtype=np.float64))
    total = float(cumulative[-1])
    if total <= 0.0:
        return np.full(len(probabilities), np.nan)
    targets = np.asarray(probabilities, dtype=np.float64) * total
    indices = np.searchsorted(cumulative, targets, side="left")
    indices = np.clip(indices, 0, len(weights) - 1)
    return (edges[indices] + edges[indices + 1]) * 0.5


def _branch_metrics(
    y_edges: np.ndarray,
    contribution: np.ndarray,
    *,
    weighted_moments: tuple[float, float, float, float, float],
    point_count: int,
) -> dict[str, Any]:
    w0, w1, w2, w3, w4 = weighted_moments
    if w0 <= 0.0:
        nan = np.full(len(y_edges) - 1, np.nan, dtype=np.float64)
        return {
            "available": False,
            "contribution_area": 0.0,
            "mu_log10_abs_pi_over_rms": None,
            "sigma_log10_abs_pi_over_rms": None,
            "weighted_skewness": None,
            "weighted_excess_kurtosis": None,
            "cdf_max_abs_error_core": None,
            "cdf_rmse_core": None,
            "pdf_r2_core": None,
            "log_density_quadratic_r2_core": None,
            "log_density_second_derivative": None,
            "expected_gaussian_second_derivative": None,
            "curvature_relative_error": None,
            "qq_r2": None,
            "point_count": point_count,
            "core_probability_range": [0.005, 0.995],
            "y_edges": y_edges,
            "contribution": np.zeros(len(y_edges) - 1, dtype=np.float64),
            "density": nan,
            "cumulative": nan,
            "fitted_cdf": nan,
            "fitted_density": nan,
            "qq_empirical": np.full(5, np.nan),
            "qq_normal": np.full(5, np.nan),
        }
    mean = w1 / w0
    central2 = w2 / w0 - mean**2
    central3 = w3 / w0 - 3.0 * mean * (w2 / w0) + 2.0 * mean**3
    central4 = (
        w4 / w0
        - 4.0 * mean * (w3 / w0)
        + 6.0 * mean**2 * (w2 / w0)
        - 3.0 * mean**4
    )
    standard_deviation = math.sqrt(max(central2, 0.0))
    skewness = central3 / max(standard_deviation**3, np.finfo(float).tiny)
    excess_kurtosis = central4 / max(standard_deviation**4, np.finfo(float).tiny) - 3.0
    width = np.diff(y_edges)
    density = contribution / (w0 * width)
    centers = (y_edges[:-1] + y_edges[1:]) * 0.5
    cumulative = np.cumsum(contribution, dtype=np.float64) / w0
    fitted_cdf = _normal_cdf(centers, mean, standard_deviation)
    mask = (cumulative >= 0.005) & (cumulative <= 0.995) & (density > 0.0)
    if int(np.count_nonzero(mask)) < 8:
        mask = density > 0.0
    cdf_error = cumulative[mask] - fitted_cdf[mask]
    cdf_max_error = float(np.max(np.abs(cdf_error))) if cdf_error.size else None
    cdf_rmse = float(np.sqrt(np.mean(np.square(cdf_error)))) if cdf_error.size else None
    predicted_density = _normal_pdf(centers, mean, standard_deviation)
    density_r2 = _r2(density[mask], predicted_density[mask]) if np.any(mask) else None
    # The Gaussian log-density has a linear first derivative and constant
    # second derivative. Fit log(density) to a quadratic on the contribution core.
    log_mask = mask & (density > 0.0)
    if int(np.count_nonzero(log_mask)) >= 8:
        coefficients = np.polyfit(centers[log_mask], np.log(density[log_mask]), 2)
        fitted_log = np.polyval(coefficients, centers[log_mask])
        log_quadratic_r2 = _r2(np.log(density[log_mask]), fitted_log)
        curvature = float(2.0 * coefficients[0])
        expected_curvature = -1.0 / max(standard_deviation**2, np.finfo(float).tiny)
        curvature_relative_error = abs(curvature - expected_curvature) / max(abs(expected_curvature), 1e-30)
    else:
        log_quadratic_r2 = None
        curvature = None
        expected_curvature = None
        curvature_relative_error = None
    quantiles = _weighted_quantiles_from_hist(y_edges, contribution, [0.01, 0.05, 0.5, 0.95, 0.99])
    normal_quantiles = mean + standard_deviation * np.array(
        [-2.326347874, -1.644853627, 0.0, 1.644853627, 2.326347874]
    )
    qq_r2 = _r2(quantiles, normal_quantiles)
    return {
        "contribution_area": w0 / point_count,
        "mu_log10_abs_pi_over_rms": mean,
        "sigma_log10_abs_pi_over_rms": standard_deviation,
        "weighted_skewness": skewness,
        "weighted_excess_kurtosis": excess_kurtosis,
        "cdf_max_abs_error_core": cdf_max_error,
        "cdf_rmse_core": cdf_rmse,
        "pdf_r2_core": density_r2,
        "log_density_quadratic_r2_core": log_quadratic_r2,
        "log_density_second_derivative": curvature,
        "expected_gaussian_second_derivative": expected_curvature,
        "curvature_relative_error": curvature_relative_error,
        "qq_r2": qq_r2,
        "point_count": point_count,
        "core_probability_range": [0.005, 0.995],
        "y_edges": y_edges,
        "contribution": contribution,
        "density": density,
        "cumulative": cumulative,
        "fitted_cdf": fitted_cdf,
        "fitted_density": predicted_density,
        "qq_empirical": quantiles,
        "qq_normal": normal_quantiles,
    }


def analyze_pi_root(
    root: Any,
    *,
    rms: float,
    point_count_expected: int,
    y_edges: np.ndarray,
    chunk_limit: int | None = None,
) -> dict[str, Any]:
    contributions = {branch: np.zeros(len(y_edges) - 1, dtype=np.float64) for branch in BRANCHES}
    moments = {branch: np.zeros(5, dtype=np.float64) for branch in BRANCHES}
    sign_counts = {branch: 0 for branch in BRANCHES}
    zero_count = 0
    point_count = 0
    for index, key in enumerate(spatial_slices(tuple(root.shape), tuple(root.chunks))):
        if chunk_limit is not None and index >= chunk_limit:
            break
        pi_les = -np.asarray(root[key], dtype=np.float32).reshape(-1).astype(np.float64)
        if not np.all(np.isfinite(pi_les)):
            raise ValueError(f"Pi contains NaN or Inf in chunk {index}: {key}")
        point_count += int(pi_les.size)
        zero_count += int(np.count_nonzero(pi_les == 0.0))
        for branch, mask in (
            ("forward", pi_les > 0.0),
            ("backscatter", pi_les < 0.0),
        ):
            magnitude = np.abs(pi_les[mask])
            if magnitude.size == 0:
                continue
            y = np.log10(magnitude / rms)
            weights = magnitude
            contributions[branch] += np.histogram(y, bins=y_edges, weights=weights)[0]
            moments[branch] += np.array(
                [
                    np.sum(weights),
                    np.dot(weights, y),
                    np.dot(weights, y * y),
                    np.dot(weights, y * y * y),
                    np.dot(weights, y * y * y * y),
                ],
                dtype=np.float64,
            )
            sign_counts[branch] += int(magnitude.size)
    expected = point_count_expected if chunk_limit is None else point_count
    if point_count != expected:
        raise RuntimeError(f"Pi point closure failed: {point_count} != {expected}")
    return {
        "point_count": point_count,
        "zero_count": zero_count,
        "sign_counts": sign_counts,
        "forward": _branch_metrics(y_edges, contributions["forward"], weighted_moments=tuple(moments["forward"]), point_count=point_count),
        "backscatter": _branch_metrics(y_edges, contributions["backscatter"], weighted_moments=tuple(moments["backscatter"]), point_count=point_count),
    }


def _figure_cdf(results: dict[float, dict[str, Any]]) -> go.Figure:
    sigmas = sorted(results)
    figure = make_subplots(rows=2, cols=3, subplot_titles=[f"sigma={sigma_text(s)}" for s in sigmas])
    for index, sigma in enumerate(sigmas):
        row, col = divmod(index, 3)
        for branch, color in (("forward", "#d62728"), ("backscatter", "#1f77b4")):
            item = results[sigma][branch]
            x = (item["y_edges"][:-1] + item["y_edges"][1:]) * 0.5
            figure.add_trace(go.Scatter(x=x, y=item["cumulative"], mode="lines", name=f"{branch} empirical", line={"color": color}, legendgroup=branch, showlegend=index == 0), row=row + 1, col=col + 1)
            figure.add_trace(go.Scatter(x=x, y=item["fitted_cdf"], mode="lines", name=f"{branch} Gaussian CDF", line={"color": color, "dash": "dash"}, legendgroup=f"{branch}_fit", showlegend=index == 0), row=row + 1, col=col + 1)
        figure.update_xaxes(title_text="log10(|Pi|/RMS)", row=row + 1, col=col + 1)
        figure.update_yaxes(title_text="cumulative contribution", range=[0, 1], row=row + 1, col=col + 1)
    figure.update_layout(title="Log-Pi contribution 的经验 S 曲线与 Gaussian CDF", template="plotly_white", width=1450, height=900)
    return figure


def _figure_pdf(results: dict[float, dict[str, Any]]) -> go.Figure:
    sigmas = sorted(results)
    figure = make_subplots(rows=2, cols=3, subplot_titles=[f"sigma={sigma_text(s)}" for s in sigmas])
    for index, sigma in enumerate(sigmas):
        row, col = divmod(index, 3)
        for branch, color in (("forward", "#d62728"), ("backscatter", "#1f77b4")):
            item = results[sigma][branch]
            x = (item["y_edges"][:-1] + item["y_edges"][1:]) * 0.5
            empirical = np.where(item["density"] > 0.0, item["density"], np.nan)
            figure.add_trace(go.Scatter(x=x, y=empirical, mode="lines", name=f"{branch} histogram", line={"color": color}, legendgroup=branch, showlegend=index == 0), row=row + 1, col=col + 1)
            figure.add_trace(go.Scatter(x=x, y=item["fitted_density"], mode="lines", name=f"{branch} Gaussian derivative", line={"color": color, "dash": "dash"}, legendgroup=f"{branch}_fit", showlegend=index == 0), row=row + 1, col=col + 1)
        figure.update_xaxes(title_text="log10(|Pi|/RMS)", row=row + 1, col=col + 1)
        figure.update_yaxes(title_text="normalized contribution density", type="log", row=row + 1, col=col + 1)
    figure.update_layout(title="Log-Pi contribution density 与 Gaussian 导数", template="plotly_white", width=1450, height=900)
    return figure


def _figure_curvature(results: dict[float, dict[str, Any]]) -> go.Figure:
    figure = make_subplots(rows=1, cols=2, subplot_titles=("d log(q) / dy", "d² log(q) / dy²"))
    for sigma in sorted(results):
        item = results[sigma]
        for branch in BRANCHES:
            b = item[branch]
            x = (b["y_edges"][:-1] + b["y_edges"][1:]) * 0.5
            mask = b["density"] > 0.0
            centers = x[mask]
            log_density = np.log(b["density"][mask])
            if len(centers) < 8:
                continue
            first = np.gradient(log_density, centers)
            second = np.gradient(first, centers)
            label = f"sigma={sigma_text(sigma)} {branch}"
            figure.add_trace(go.Scatter(x=centers, y=first, mode="lines", name=label, legendgroup=label), row=1, col=1)
            figure.add_trace(go.Scatter(x=centers, y=second, mode="lines", name=label, legendgroup=label, showlegend=False), row=1, col=2)
    figure.update_xaxes(title_text="log10(|Pi|/RMS)", row=1, col=1)
    figure.update_xaxes(title_text="log10(|Pi|/RMS)", row=1, col=2)
    figure.update_yaxes(title_text="first derivative", row=1, col=1)
    figure.update_yaxes(title_text="second derivative", row=1, col=2)
    figure.update_layout(title="Gaussian 判据：log-density 导数与曲率", template="plotly_white", width=1450, height=650)
    return figure


def _figure_qq(results: dict[float, dict[str, Any]]) -> go.Figure:
    figure = make_subplots(rows=1, cols=2, subplot_titles=("forward", "backscatter"))
    for col, branch in enumerate(BRANCHES, start=1):
        for sigma in sorted(results):
            item = results[sigma][branch]
            figure.add_trace(go.Scatter(x=item["qq_normal"], y=item["qq_empirical"], mode="lines+markers", name=f"sigma={sigma_text(sigma)}", legendgroup=sigma_text(sigma), showlegend=col == 1), row=1, col=col)
        limits = [-4, 4]
        figure.add_trace(go.Scatter(x=limits, y=limits, mode="lines", name="ideal y=x", line={"color": "black", "dash": "dash"}, showlegend=col == 1), row=1, col=col)
        figure.update_xaxes(title_text="Gaussian theoretical quantile", row=1, col=col)
        figure.update_yaxes(title_text="empirical contribution quantile", row=1, col=col)
    figure.update_layout(title="Contribution-weighted log-Pi Gaussian QQ plot", template="plotly_white", width=1250, height=650)
    return figure


def _json_metrics(results: dict[float, dict[str, Any]], *, time_index: int, chunk_limit: int | None) -> dict[str, Any]:
    output: dict[str, Any] = {
        "analysis_version": 1,
        "status": "complete",
        "time_index": time_index,
        "scope": "full_domain" if chunk_limit is None else "smoke_chunks",
        "chunk_limit": chunk_limit,
        "log_base": 10,
        "normality_target": "contribution-weighted log10(|Pi_LES|/RMS(Pi_LES)) separately for forward and backscatter",
        "branches": {},
    }
    for sigma, result in sorted(results.items()):
        output["branches"][sigma_text(sigma)] = {}
        for branch in BRANCHES:
            item = result[branch]
            output["branches"][sigma_text(sigma)][branch] = {
                key: value
                for key, value in item.items()
                if key not in {"y_edges", "contribution", "density", "cumulative", "fitted_cdf", "fitted_density", "qq_empirical", "qq_normal"}
            }
        output["branches"][sigma_text(sigma)]["point_count"] = result["point_count"]
        output["branches"][sigma_text(sigma)]["zero_count"] = result["zero_count"]
        output["branches"][sigma_text(sigma)]["sign_counts"] = result["sign_counts"]
    return output


def write_outputs(output_dir: Path, results: dict[float, dict[str, Any]], *, time_index: int, chunk_limit: int | None, filter_type: str = "gaussian", sharp_edge_width_fraction: float | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "log_pi_contribution_cdf.html": _figure_cdf(results),
        "log_pi_contribution_pdf.html": _figure_pdf(results),
        "log_pi_gaussian_derivatives.html": _figure_curvature(results),
        "log_pi_gaussian_qq.html": _figure_qq(results),
    }
    for name, figure in figures.items():
        figure.write_html(str(output_dir / name), include_plotlyjs="cdn", full_html=True)
    payload = _json_metrics(results, time_index=time_index, chunk_limit=chunk_limit)
    payload["filter_type"] = filter_type
    payload["sharp_edge_width_fraction"] = sharp_edge_width_fraction
    atomic_json(output_dir / "log_pi_gaussian_validation.json", payload)
    with (output_dir / "log_pi_gaussian_parameters.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sigma", "branch", "contribution_area", "mu_log10", "sigma_log10", "weighted_skewness", "weighted_excess_kurtosis", "cdf_max_abs_error_core", "cdf_rmse_core", "pdf_r2_core", "log_density_quadratic_r2_core", "curvature_relative_error", "qq_r2"])
        for sigma, result in sorted(results.items()):
            for branch in BRANCHES:
                item = result[branch]
                writer.writerow([sigma, branch, item["contribution_area"], item["mu_log10_abs_pi_over_rms"], item["sigma_log10_abs_pi_over_rms"], item["weighted_skewness"], item["weighted_excess_kurtosis"], item["cdf_max_abs_error_core"], item["cdf_rmse_core"], item["pdf_r2_core"], item["log_density_quadratic_r2_core"], item["curvature_relative_error"], item["qq_r2"]])
    lines = [
        "# Log-Pi contribution Gaussian validation",
        "",
        f"范围：`{'full_domain' if chunk_limit is None else 'smoke_chunks'}`，时间帧 `time_index={time_index}`。",
        "",
        "正向与 backscatter 分开处理：`y=log10(|Pi_LES|/RMS(Pi_LES))`。每个格点按 `|Pi_LES|` 加权，因此拟合对象是 Pi contribution，不是普通点数 PDF。",
        "",
        "每个分支的面积是该分支对 `mean(Pi_LES)`（正向）或 `mean(|Pi_LES|)`（backscatter magnitude）的贡献。参数 `mu_log10` 和 `sigma_log10` 使用精确流式 weighted moments 求得。",
        "",
        "`log_pi_contribution_cdf.html` 用经验累计 contribution 与 Gaussian CDF 比较；`log_pi_contribution_pdf.html` 比较 histogram density 与 Gaussian CDF 的解析导数；`log_pi_gaussian_derivatives.html` 检查 log-density 的线性一阶导数和近似常数二阶导数；`log_pi_gaussian_qq.html` 做分位数检查。",
        "",
        "由于全域点数极大，不能只用显著性检验决定是否 Gaussian；应结合 weighted skewness、excess kurtosis、CDF 核心区误差、log-density quadratic R²、曲率误差和 QQ 图判断。",
    ]
    (output_dir / "LOG_PI_GAUSSIAN_REPORT_CN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    atomic_json(output_dir / "COMPLETE.json", payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Gaussian shape of contribution-weighted log Pi.")
    parser.add_argument("--config", default="configs/pipeline.yaml")
    parser.add_argument("--time-index", type=int, default=1)
    parser.add_argument("--sigmas", type=_parse_sigmas, default=None)
    parser.add_argument("--filter-type", choices=FILTER_TYPES)
    parser.add_argument("--sharp-edge-width-fraction", type=float)
    parser.add_argument("--bins", type=int, default=2048)
    parser.add_argument("--y-min", type=float, default=-45.0)
    parser.add_argument("--y-max", type=float, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--smoke-chunks", type=int, default=None)
    return parser


def run(args: argparse.Namespace) -> Path:
    cfg = load_config(args.config)
    if args.filter_type is not None:
        cfg = cfg.with_filter(args.filter_type)
    if args.sharp_edge_width_fraction is not None:
        cfg = cfg.with_sharp_edge_width_fraction(args.sharp_edge_width_fraction)
    sigmas = args.sigmas if args.sigmas is not None else list(cfg.sigma_grids)
    output_dir = args.output_dir or Path("pi_pdf") / "output" / cfg.result_id(args.time_index, 0).rsplit("_sigma_", 1)[0] / "log_gaussian"
    output_dir = output_dir.resolve()
    references = {}
    max_y = -np.inf
    for sigma in sigmas:
        result_dir = cfg.result_path(args.time_index, sigma)
        weak = json.loads((result_dir / "weak_asymmetry.json").read_text(encoding="utf-8"))
        rms = float(weak["global"]["pi_rms"])
        maximum = float(weak["global"]["abs_pi_max"])
        references[sigma] = (rms, int(weak["point_count"]))
        max_y = max(max_y, math.log10(maximum / rms))
    y_max = float(args.y_max if args.y_max is not None else np.nextafter(max_y, np.inf))
    if y_max <= args.y_min:
        raise ValueError("y-max must exceed y-min")
    y_edges = np.linspace(args.y_min, y_max, args.bins + 1)
    results = {}
    for sigma in sigmas:
        print(f"[run] sigma={sigma_text(sigma)} log-Pi contribution Gaussian", flush=True)
        root = open_complete_result(cfg.result_path(args.time_index, sigma))
        results[sigma] = analyze_pi_root(
            root["pi"],
            rms=references[sigma][0],
            point_count_expected=references[sigma][1],
            y_edges=y_edges,
            chunk_limit=args.smoke_chunks,
        )
    write_outputs(
        output_dir, results, time_index=args.time_index,
        chunk_limit=args.smoke_chunks, filter_type=cfg.filter_type,
        sharp_edge_width_fraction=(cfg.sharp_edge_width_fraction if cfg.filter_type == "smooth_sharp" else None),
    )
    return output_dir


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        output = run(args)
    except Exception as error:
        print(f"log-Pi Gaussian validation failed: {error}", file=sys.stderr)
        return 1
    print(f"log-Pi Gaussian validation complete: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
