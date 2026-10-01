from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from jhtdb_pipeline.config import FILTER_TYPES, load_config
from jhtdb_pipeline.store import open_complete_result, spatial_slices
from jhtdb_pipeline.validation import atomic_json


ANALYSIS_VERSION = 1


def sigma_text(sigma: float) -> str:
    return format(float(sigma), ".8g")


def _parse_sigmas(text: str) -> list[float]:
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values or len(set(values)) != len(values) or any(value <= 0 for value in values):
        raise argparse.ArgumentTypeError("sigmas must be unique positive comma-separated values")
    return values


@dataclass(frozen=True)
class PiReferenceStatistics:
    sigma: float
    point_count: int
    pi_les_mean: float
    pi_rms: float
    abs_pi_p99: float
    abs_pi_max: float
    forward_count: int
    backscatter_count: int
    zero_count: int
    source_path: Path


def load_reference_statistics(result_path: Path, sigma: float) -> PiReferenceStatistics:
    path = result_path / "weak_asymmetry.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("scope") != "full_domain" or not payload.get("passed"):
        raise RuntimeError(f"weak-asymmetry reference is not a passed full-domain result: {path}")
    # The source report uses stored pi=tau:S. Pi_LES reverses that sign.
    return PiReferenceStatistics(
        sigma=float(sigma),
        point_count=int(payload["point_count"]),
        pi_les_mean=-float(payload["global"]["pi_mean"]),
        pi_rms=float(payload["global"]["pi_rms"]),
        abs_pi_p99=float(payload["global"]["abs_pi_p99"]),
        abs_pi_max=float(payload["global"]["abs_pi_max"]),
        forward_count=int(payload["negative_forward"]["count"]),
        backscatter_count=int(payload["positive_backscatter"]["count"]),
        zero_count=int(payload["zero"]["count"]),
        source_path=path,
    )


def common_edges(
    references: Sequence[PiReferenceStatistics],
    *,
    central_bins: int,
    tail_bins: int,
    tail_minimum: float,
) -> dict[str, np.ndarray]:
    if central_bins < 16 or tail_bins < 16:
        raise ValueError("central and tail bins must each be at least 16")
    if tail_minimum <= 0:
        raise ValueError("tail_minimum must be positive")
    raw_clip = max(item.abs_pi_p99 for item in references)
    normalized_clip = max(item.abs_pi_p99 / item.pi_rms for item in references)
    normalized_clip = math.ceil(normalized_clip * 10.0) / 10.0
    normalized_max = max(item.abs_pi_max / item.pi_rms for item in references)
    normalized_max = np.nextafter(normalized_max, np.inf)
    return {
        "raw": np.linspace(-raw_clip, raw_clip, central_bins + 1),
        "normalized": np.linspace(
            -normalized_clip, normalized_clip, central_bins + 1
        ),
        # The first bin [0, tail_minimum) guarantees that every finite point,
        # including exact zero, participates in tail-count closure.
        "absolute_normalized": np.concatenate(
            (
                np.array([0.0]),
                np.geomspace(tail_minimum, normalized_max, tail_bins + 1),
            )
        ),
    }


def _histogram(values: np.ndarray, edges: np.ndarray) -> np.ndarray:
    return np.histogram(values, bins=edges)[0].astype(np.uint64)


def analyze_pi_array(
    array: Any,
    reference: PiReferenceStatistics,
    edges: dict[str, np.ndarray],
    *,
    chunk_limit: int | None = None,
) -> dict[str, Any]:
    shape = tuple(int(value) for value in array.shape)
    chunks = tuple(int(value) for value in array.chunks)
    raw_count = np.zeros(len(edges["raw"]) - 1, dtype=np.uint64)
    normalized_count = np.zeros(len(edges["normalized"]) - 1, dtype=np.uint64)
    absolute_count = np.zeros(len(edges["absolute_normalized"]) - 1, dtype=np.uint64)
    forward_count = np.zeros_like(absolute_count)
    backscatter_count = np.zeros_like(absolute_count)
    signed_sum = np.zeros(absolute_count.shape, dtype=np.float64)
    absolute_sum = np.zeros(absolute_count.shape, dtype=np.float64)
    point_count = 0
    total = 0.0
    total_abs = 0.0
    sum_squares = 0.0
    positive = 0
    negative = 0
    zero = 0
    raw_outside = 0
    normalized_outside = 0

    for index, key in enumerate(spatial_slices(shape, chunks)):
        if chunk_limit is not None and index >= chunk_limit:
            break
        pi_les = -np.asarray(array[key], dtype=np.float32).reshape(-1)
        if not np.all(np.isfinite(pi_les)):
            raise ValueError(f"Pi contains NaN or Inf in chunk {index}: {key}")
        values = pi_les.astype(np.float64)
        normalized = values / reference.pi_rms
        absolute_normalized = np.abs(normalized)
        raw_count += _histogram(values, edges["raw"])
        normalized_count += _histogram(normalized, edges["normalized"])
        absolute_count += _histogram(absolute_normalized, edges["absolute_normalized"])
        forward_mask = values > 0.0
        backscatter_mask = values < 0.0
        forward_count += _histogram(
            absolute_normalized[forward_mask], edges["absolute_normalized"]
        )
        backscatter_count += _histogram(
            absolute_normalized[backscatter_mask], edges["absolute_normalized"]
        )
        signed_sum += np.histogram(
            absolute_normalized,
            bins=edges["absolute_normalized"],
            weights=values,
        )[0]
        absolute_sum += np.histogram(
            absolute_normalized,
            bins=edges["absolute_normalized"],
            weights=np.abs(values),
        )[0]
        point_count += int(values.size)
        total += float(np.sum(values, dtype=np.float64))
        total_abs += float(np.sum(np.abs(values), dtype=np.float64))
        sum_squares += float(np.dot(values, values))
        positive += int(np.count_nonzero(forward_mask))
        negative += int(np.count_nonzero(backscatter_mask))
        zero += int(values.size - np.count_nonzero(forward_mask) - np.count_nonzero(backscatter_mask))
        raw_outside += int(
            np.count_nonzero((values < edges["raw"][0]) | (values > edges["raw"][-1]))
        )
        normalized_outside += int(
            np.count_nonzero(
                (normalized < edges["normalized"][0])
                | (normalized > edges["normalized"][-1])
            )
        )

    expected = reference.point_count if chunk_limit is None else point_count
    if point_count != expected:
        raise RuntimeError(f"Pi point closure failed: {point_count} != {expected}")
    if int(absolute_count.sum()) != point_count:
        raise RuntimeError("absolute-tail histogram does not cover every Pi point")
    if positive + negative + zero != point_count:
        raise RuntimeError("Pi sign counts do not close")
    if int(raw_count.sum()) + raw_outside != point_count:
        raise RuntimeError("raw central histogram count closure failed")
    if int(normalized_count.sum()) + normalized_outside != point_count:
        raise RuntimeError("normalized central histogram count closure failed")
    if chunk_limit is None:
        if (positive, negative, zero) != (
            reference.forward_count,
            reference.backscatter_count,
            reference.zero_count,
        ):
            raise RuntimeError("Pi_LES sign counts disagree with weak-asymmetry reference")
        calculated_rms = math.sqrt(sum_squares / point_count)
        if not math.isclose(calculated_rms, reference.pi_rms, rel_tol=2e-13):
            raise RuntimeError("Pi RMS disagrees with weak-asymmetry reference")

    raw_width = np.diff(edges["raw"])
    normalized_width = np.diff(edges["normalized"])
    tail_width = np.diff(edges["absolute_normalized"])
    return {
        "raw_count": raw_count,
        "normalized_count": normalized_count,
        "absolute_count": absolute_count,
        "forward_count": forward_count,
        "backscatter_count": backscatter_count,
        "signed_sum": signed_sum,
        "absolute_sum": absolute_sum,
        "raw_pdf": raw_count / (point_count * raw_width),
        "normalized_pdf": normalized_count / (point_count * normalized_width),
        "forward_tail_pdf": forward_count / (point_count * tail_width),
        "backscatter_tail_pdf": backscatter_count / (point_count * tail_width),
        "point_count": point_count,
        "mean": total / point_count,
        "rms": math.sqrt(sum_squares / point_count),
        "mean_abs": total_abs / point_count,
        "forward_count_total": positive,
        "backscatter_count_total": negative,
        "zero_count_total": zero,
        "raw_outside_count": raw_outside,
        "normalized_outside_count": normalized_outside,
        "raw_pdf_integral": float(np.sum(raw_count / point_count)),
        "normalized_pdf_integral": float(np.sum(normalized_count / point_count)),
        "tail_count_integral": float(np.sum(absolute_count / point_count)),
        "signed_closure": float(np.sum(signed_sum) / point_count),
        "absolute_closure": float(np.sum(absolute_sum) / point_count),
    }


def _centers(edges: np.ndarray) -> np.ndarray:
    return (edges[:-1] + edges[1:]) * 0.5


def _positive_or_nan(values: np.ndarray) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64).copy()
    result[result <= 0.0] = np.nan
    return result


def central_pdf_figure(
    analyses: dict[float, dict[str, Any]],
    edges: np.ndarray,
    *,
    normalized: bool,
) -> go.Figure:
    figure = go.Figure()
    key = "normalized_pdf" if normalized else "raw_pdf"
    count_key = "normalized_count" if normalized else "raw_count"
    for sigma in sorted(analyses):
        item = analyses[sigma]
        figure.add_trace(
            go.Scatter(
                x=_centers(edges),
                y=_positive_or_nan(item[key]),
                customdata=item[count_key],
                mode="lines",
                name=f"sigma={sigma_text(sigma)}",
                hovertemplate="Pi coordinate=%{x:.6g}<br>PDF=%{y:.6g}<br>count=%{customdata}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(
        title=(
            "Pi_LES / RMS(Pi_LES) 的全域中心 PDF（公共 bins）"
            if normalized
            else "Pi_LES 的全域中心 PDF（公共物理单位 bins）"
        ),
        xaxis_title="Pi_LES / RMS(Pi_LES)" if normalized else "Pi_LES = -tau:S",
        yaxis_title="probability density",
        yaxis_type="log",
        template="plotly_white",
        width=1250,
        height=700,
        hovermode="x unified",
    )
    return figure


def signed_tail_figure(
    analyses: dict[float, dict[str, Any]], edges: np.ndarray
) -> go.Figure:
    sigmas = sorted(analyses)
    figure = make_subplots(
        rows=2,
        cols=3,
        subplot_titles=[f"sigma={sigma_text(sigma)}" for sigma in sigmas],
    )
    x = _centers(edges)[1:]
    for index, sigma in enumerate(sigmas):
        row, col = divmod(index, 3)
        item = analyses[sigma]
        for key, name, color in (
            ("forward_tail_pdf", "forward: Pi_LES > 0", "#d62728"),
            ("backscatter_tail_pdf", "backscatter: Pi_LES < 0", "#1f77b4"),
        ):
            figure.add_trace(
                go.Scatter(
                    x=x,
                    y=_positive_or_nan(item[key][1:]),
                    mode="lines",
                    name=name,
                    line={"color": color},
                    legendgroup=name,
                    showlegend=index == 0,
                ),
                row=row + 1,
                col=col + 1,
            )
        figure.update_xaxes(type="log", title_text="|Pi_LES| / RMS", row=row + 1, col=col + 1)
        figure.update_yaxes(type="log", title_text="unconditional density", row=row + 1, col=col + 1)
    figure.update_layout(
        title="Forward/backscatter 分侧尾部 PDF（所有格点归一化）",
        width=1400,
        height=900,
        template="plotly_white",
    )
    return figure


def ccdf_figure(analyses: dict[float, dict[str, Any]], edges: np.ndarray) -> go.Figure:
    figure = go.Figure()
    x = edges[1:-1]
    for sigma in sorted(analyses):
        counts = analyses[sigma]["absolute_count"]
        ccdf = np.cumsum(counts[::-1], dtype=np.uint64)[::-1] / analyses[sigma]["point_count"]
        figure.add_trace(
            go.Scatter(x=x, y=ccdf[1:], mode="lines", name=f"sigma={sigma_text(sigma)}")
        )
    figure.update_layout(
        title="|Pi_LES| / RMS 的全域 CCDF",
        xaxis={"title": "threshold |Pi_LES| / RMS", "type": "log"},
        yaxis={"title": "P(|Pi_LES| / RMS >= threshold)", "type": "log"},
        template="plotly_white",
        width=1200,
        height=700,
    )
    return figure


def contribution_figure(
    analyses: dict[float, dict[str, Any]], edges: np.ndarray
) -> go.Figure:
    figure = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "阈值以上事件对 mean(Pi_LES) 的累计贡献",
            "阈值以上事件占 mean(|Pi_LES|) 的比例",
            "Signed 累计贡献的下降速率（线性阈值求导）",
            "Absolute 累计贡献的下降速率（线性阈值求导）",
        ),
        vertical_spacing=0.14,
    )
    x = edges[1:-1]
    for sigma in sorted(analyses):
        item = analyses[sigma]
        signed_tail = np.cumsum(item["signed_sum"][::-1])[::-1]
        absolute_tail = np.cumsum(item["absolute_sum"][::-1])[::-1]
        signed_total = float(np.sum(item["signed_sum"]))
        absolute_total = float(np.sum(item["absolute_sum"]))
        signed_contribution = signed_tail[1:] / signed_total
        absolute_contribution = absolute_tail[1:] / absolute_total
        for col, y in ((1, signed_contribution), (2, absolute_contribution)):
            figure.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    name=f"sigma={sigma_text(sigma)}",
                    legendgroup=sigma_text(sigma),
                    showlegend=col == 1,
                ),
                row=1,
                col=col,
            )
            figure.update_xaxes(type="log", title_text="threshold |Pi_LES| / RMS", row=1, col=col)

        # Differentiate against the original, linearly valued threshold.  Axis
        # transforms below affect only display and therefore do not turn this
        # into a derivative with respect to log(threshold).
        signed_descent = -np.gradient(signed_contribution, x)
        absolute_descent = -np.gradient(absolute_contribution, x)
        figure.add_trace(
            go.Scatter(
                x=x,
                y=_positive_or_nan(signed_descent),
                mode="lines",
                name=f"sigma={sigma_text(sigma)}: decrease",
                legendgroup=sigma_text(sigma),
                showlegend=False,
            ),
            row=2,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=x,
                y=_positive_or_nan(-signed_descent),
                mode="lines",
                line={"dash": "dot"},
                name=f"sigma={sigma_text(sigma)}: local increase",
                legendgroup=sigma_text(sigma),
                showlegend=False,
                hovertemplate=(
                    "threshold=%{x}<br>local increase dC/da=%{y}<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=x,
                y=_positive_or_nan(absolute_descent),
                mode="lines",
                name=f"sigma={sigma_text(sigma)}: decrease",
                legendgroup=sigma_text(sigma),
                showlegend=False,
            ),
            row=2,
            col=2,
        )
    figure.update_yaxes(title_text="signed tail sum / total signed sum", row=1, col=1)
    figure.update_yaxes(title_text="absolute tail sum / total absolute sum", row=1, col=2)
    for col in (1, 2):
        figure.update_xaxes(
            type="log", title_text="threshold |Pi_LES| / RMS", row=2, col=col
        )
        figure.update_yaxes(type="log", title_text="descent rate -dC/da", row=2, col=col)
    figure.update_layout(
        title="Pi 强度阈值以上事件的累计通量贡献",
        width=1450,
        height=1100,
        template="plotly_white",
    )
    return figure


def _atomic_npz(path: Path, **arrays: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    temporary.replace(path)


def write_outputs(
    output_dir: Path,
    references: dict[float, PiReferenceStatistics],
    analyses: dict[float, dict[str, Any]],
    edges: dict[str, np.ndarray],
    *,
    time_index: int,
    chunk_limit: int | None,
    filter_type: str = "gaussian",
    sharp_edge_width_fraction: float | None = None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    figures = {
        "pi_pdf_raw.html": central_pdf_figure(analyses, edges["raw"], normalized=False),
        "pi_pdf_normalized.html": central_pdf_figure(analyses, edges["normalized"], normalized=True),
        "pi_signed_tail_pdf.html": signed_tail_figure(analyses, edges["absolute_normalized"]),
        "pi_abs_ccdf.html": ccdf_figure(analyses, edges["absolute_normalized"]),
        "pi_tail_contribution.html": contribution_figure(analyses, edges["absolute_normalized"]),
    }
    paths: list[Path] = []
    for name, figure in figures.items():
        path = output_dir / name
        figure.write_html(str(path), include_plotlyjs="cdn", full_html=True)
        paths.append(path)

    for sigma in sorted(analyses):
        directory = output_dir / f"sigma_{sigma_text(sigma).replace('.', 'p')}"
        directory.mkdir(parents=True, exist_ok=True)
        item = analyses[sigma]
        npz_path = directory / "pi_pdf.npz"
        _atomic_npz(
            npz_path,
            raw_edges=edges["raw"],
            normalized_edges=edges["normalized"],
            absolute_normalized_edges=edges["absolute_normalized"],
            **{key: item[key] for key in (
                "raw_count", "normalized_count", "absolute_count", "forward_count",
                "backscatter_count", "signed_sum", "absolute_sum", "raw_pdf",
                "normalized_pdf", "forward_tail_pdf", "backscatter_tail_pdf"
            )},
        )
        metadata = {
            "analysis_version": ANALYSIS_VERSION,
            "status": "complete",
            "time_index": time_index,
            "sigma_grid": sigma,
            "filter_type": filter_type,
            "sharp_edge_width_fraction": sharp_edge_width_fraction,
            "scope": "full_domain" if chunk_limit is None else "smoke_chunks",
            "chunk_limit": chunk_limit,
            "sign_convention": "Pi_LES = -stored pi = -tau:S; positive is forward cascade",
            "reference_statistics_path": str(references[sigma].source_path),
            **{key: item[key] for key in (
                "point_count", "mean", "rms", "mean_abs", "forward_count_total",
                "backscatter_count_total", "zero_count_total", "raw_outside_count",
                "normalized_outside_count", "raw_pdf_integral",
                "normalized_pdf_integral", "tail_count_integral", "signed_closure",
                "absolute_closure"
            )},
        }
        atomic_json(directory / "pi_pdf.json", metadata)
        paths.extend((npz_path, directory / "pi_pdf.json"))

    csv_path = output_dir / "pi_pdf_summary.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "sigma", "N", "mean_Pi_LES", "rms_Pi_LES", "mean_abs_Pi_LES",
            "abs_Pi_p99", "abs_Pi_max", "forward_fraction", "backscatter_fraction",
            "zero_fraction", "central_raw_mass", "central_normalized_mass"
        ])
        for sigma in sorted(analyses):
            item = analyses[sigma]
            reference = references[sigma]
            writer.writerow([
                sigma, item["point_count"], item["mean"], item["rms"], item["mean_abs"],
                reference.abs_pi_p99, reference.abs_pi_max,
                item["forward_count_total"] / item["point_count"],
                item["backscatter_count_total"] / item["point_count"],
                item["zero_count_total"] / item["point_count"],
                item["raw_pdf_integral"], item["normalized_pdf_integral"],
            ])
    paths.append(csv_path)

    summary = {
        "analysis_version": ANALYSIS_VERSION,
        "status": "complete",
        "time_index": time_index,
        "sigmas": sorted(analyses),
        "filter_type": filter_type,
        "sharp_edge_width_fraction": sharp_edge_width_fraction,
        "scope": "full_domain" if chunk_limit is None else "smoke_chunks",
        "chunk_limit": chunk_limit,
        "sign_convention": "Pi_LES = -stored pi = -tau:S; positive is forward cascade",
        "all_tail_histograms_cover_every_point": all(
            math.isclose(item["tail_count_integral"], 1.0, abs_tol=1e-15)
            for item in analyses.values()
        ),
        "raw_central_range": edges["raw"][[0, -1]].tolist(),
        "normalized_central_range": edges["normalized"][[0, -1]].tolist(),
        "absolute_normalized_tail_range": edges["absolute_normalized"][[0, -1]].tolist(),
    }
    summary_path = output_dir / "PI_PDF_SUMMARY.json"
    atomic_json(summary_path, summary)
    paths.append(summary_path)

    report_lines = [
        "# Pi_LES 一维 PDF 与尾部基线",
        "",
        f"时间帧：`time_index={time_index}`；范围：`{summary['scope']}`。",
        "",
        "符号：`Pi_LES = -stored pi = -tau:S`，正值为 forward cascade，负值为 backscatter。",
        "",
        "所有 tail histogram 覆盖每个格点。中心 PDF 为保证跨尺度可读性，只显示由六尺度全域 p99 确定的公共中心范围，范围外概率通过 metadata 明确记录，并在 CCDF/tail 图中完整保留。",
        "",
        "## 输出",
        "",
        "- `pi_pdf_raw.html`：原始物理单位中心 PDF；",
        "- `pi_pdf_normalized.html`：Pi/RMS 标准化中心 PDF；",
        "- `pi_signed_tail_pdf.html`：forward/backscatter 分侧尾部；",
        "- `pi_abs_ccdf.html`：绝对强度 CCDF；",
        "- `pi_tail_contribution.html`：阈值以上事件的 signed/absolute 累计贡献；",
        "- `pi_pdf_summary.csv`：六尺度统计和闭合表；",
        "- 各 `sigma_*` 子目录：精确 counts、PDF、weighted sums 和 metadata。",
        "",
        "本阶段只建立 Pi 的一维分布基线；没有执行条件 PDF、tau--strain 分解、DBSCAN、GMM 或 decision tree。",
    ]
    report_path = output_dir / "README_CN.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    paths.append(report_path)
    atomic_json(output_dir / "COMPLETE.json", summary)
    paths.append(output_dir / "COMPLETE.json")
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exact full-domain one-dimensional Pi PDF analysis.")
    parser.add_argument("--config", default="configs/pipeline.yaml")
    parser.add_argument("--time-index", type=int, default=1)
    parser.add_argument("--sigmas", type=_parse_sigmas, default=None)
    parser.add_argument("--filter-type", choices=FILTER_TYPES)
    parser.add_argument("--sharp-edge-width-fraction", type=float)
    parser.add_argument("--central-bins", type=int, default=512)
    parser.add_argument("--tail-bins", type=int, default=512)
    parser.add_argument("--tail-minimum", type=float, default=1e-6)
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
    if args.smoke_chunks is not None and args.smoke_chunks < 1:
        raise ValueError("--smoke-chunks must be positive")
    output_dir = args.output_dir or Path("pi_pdf") / "output" / cfg.result_id(args.time_index, 0).rsplit("_sigma_", 1)[0]
    output_dir = output_dir.resolve()
    references = {
        sigma: load_reference_statistics(cfg.result_path(args.time_index, sigma), sigma)
        for sigma in sigmas
    }
    edges = common_edges(
        list(references.values()),
        central_bins=args.central_bins,
        tail_bins=args.tail_bins,
        tail_minimum=args.tail_minimum,
    )
    analyses = {}
    for sigma in sigmas:
        print(f"[run] sigma={sigma_text(sigma)} full Pi PDF", flush=True)
        root = open_complete_result(cfg.result_path(args.time_index, sigma))
        analyses[sigma] = analyze_pi_array(
            root["pi"], references[sigma], edges, chunk_limit=args.smoke_chunks
        )
    write_outputs(
        output_dir,
        references,
        analyses,
        edges,
        time_index=args.time_index,
        chunk_limit=args.smoke_chunks,
        filter_type=cfg.filter_type,
        sharp_edge_width_fraction=(cfg.sharp_edge_width_fraction if cfg.filter_type == "smooth_sharp" else None),
    )
    return output_dir


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started = time.monotonic()
    try:
        output = run(args)
    except Exception as error:
        print(f"Pi PDF failed: {error}", file=sys.stderr)
        return 1
    print(f"Pi PDF complete: {output} ({time.monotonic() - started:.1f} s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
