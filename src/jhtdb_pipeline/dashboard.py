from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Streamlit puts this script's directory first on sys.path. Prefer the project
# packages when running this file directly.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from jhtdb_pipeline.config import READABLE_RESULT_SCHEMAS, load_config
from jhtdb_pipeline.store import open_complete_result


GLOBAL_TOTAL_ORDER = ("s_bar", "pi", "work_resolved", "work_full")
GLOBAL_TOTAL_LABELS = ("ΣS̄", "ΣΠ", "ΣW_res", "ΣW_full")
SBAR_METRIC_SPECS = (
    ("identity_relative_residual_rms", "能量等式相对残差 RMS"),
    ("s_bar_vs_pi_net", "|ΣS̄| / |ΣΠ|"),
)

def complete_result_paths(result_root: Path) -> list[Path]:
    if not result_root.is_dir():
        return []
    return sorted(
        path
        for path in result_root.iterdir()
        if (
            path.is_dir()
            and not path.name.startswith(".")
            and not path.name.endswith(("_shared", "_shared_full", "_shared_stride2", "_shared_stride2_v9"))
            and (path / "COMPLETE").is_file()
        )
    )


def _extract_spatial_slice(array, axis: str, index: int, prefix=()) -> np.ndarray:
    axes = ("z", "y", "x")
    if axis not in axes:
        raise ValueError(f"unknown axis {axis}")
    key = [slice(None)] * 3
    key[axes.index(axis)] = index
    return np.asarray(array[prefix + tuple(key)])


def extract_slice(array, component: int, axis: str, index: int) -> np.ndarray:
    return _extract_spatial_slice(array, axis, index, (component,))


def extract_scalar_slice(array, axis: str, index: int) -> np.ndarray:
    return _extract_spatial_slice(array, axis, index)


def extract_gradient_slice(
    array, velocity_component: int, derivative_component: int, axis: str, index: int
) -> np.ndarray:
    return _extract_spatial_slice(array, axis, index, (velocity_component, derivative_component))


def spatial_axis_length(array, axis: str) -> int:
    return int(array.shape[{"z": -3, "y": -2, "x": -1}[axis]])


def comparison_slices(result, field, axis, index, component, derivative=None):
    """Read raw and filtered values at the same original-grid coordinates."""
    raw_field = "velocity" if field == "velocity_bar" else "gradient"
    sampling = result.attrs.get("field_sampling", {})
    stride = sampling.get(field, {}).get("stride_xyz", [1, 1, 1])[0]
    raw_stride = sampling.get(raw_field, {}).get("stride_xyz", [1, 1, 1])[0]
    if index % stride or stride % raw_stride:
        raise ValueError("comparison plane must lie on the stored sampling lattice")
    prefix = (component,) if derivative is None else (component, derivative)
    raw_key = [slice(None, None, stride // raw_stride)] * 3
    raw_key[("z", "y", "x").index(axis)] = index // raw_stride
    raw = np.asarray(result[raw_field][prefix + tuple(raw_key)])
    filtered = _extract_spatial_slice(result[field], axis, index // stride, prefix)
    return raw, filtered


def _global_totals_figure(report: dict):
    totals = report["global_totals"]
    return go.Figure(
        go.Bar(
            x=list(GLOBAL_TOTAL_LABELS),
            y=[totals[name] for name in GLOBAL_TOTAL_ORDER],
            customdata=[totals[name] for name in GLOBAL_TOTAL_ORDER],
            hovertemplate="%{x}: %{customdata:.8e}<extra></extra>",
        )
    ).update_layout(title=f"Global net totals ({report['scope']})")


def _scientific_text(value) -> str:
    if value is None:
        return "不可定义"
    return f"{float(value):.6e}"


def sbar_metric_rows(report: dict) -> list[dict[str, str]]:
    metrics = report.get("metrics", {})
    rows = []
    for key, label in SBAR_METRIC_SPECS:
        metric = metrics.get(key, {})
        detail = metric.get("error") or ""
        if (
            key == "identity_relative_residual_rms"
            and metric.get("residual_rms") is not None
        ):
            detail = (
                f"residual_rms={_scientific_text(metric['residual_rms'])}; "
                f"joint_energy_rms={_scientific_text(metric.get('joint_energy_rms'))}"
            )
        rows.append(
            {
                "判据": label,
                "值": _scientific_text(metric.get("value")),
                "阈值（≤）": _scientific_text(metric.get("threshold")),
                "状态": "通过" if metric.get("passed") else "失败",
                "说明": detail,
            }
        )
    return rows


def energy_identity_residual(
    work_full: np.ndarray,
    work_resolved: np.ndarray,
    pi: np.ndarray,
    s_bar: np.ndarray,
) -> np.ndarray:
    return work_full - work_resolved + pi - s_bar


def result_selection_metadata(path: Path) -> dict | None:
    """Read only the small manifest needed to populate result selectors."""
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") not in READABLE_RESULT_SCHEMAS:
            return None
        time_index = int(manifest["time_index"])
        sigma_grid = float(manifest["sigma_grid"])
        filter_type = str(manifest.get("filter_type", "gaussian"))
        physical_time = manifest.get("physical_time")
        if physical_time is not None:
            physical_time = float(physical_time)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if filter_type == "smooth_sharp":
        fraction = manifest.get("sharp_edge_width_fraction")
        if fraction is None:
            return None
        smoothing_key = ("fraction_of_cutoff", float(fraction))
        smoothing_label = f"α = {float(fraction):g} (w/kc)"
    else:
        smoothing_key = ("not_applicable", None)
        smoothing_label = "不适用"

    return {
        "path": path,
        "schema_version": manifest["schema_version"],
        "time_index": time_index,
        "physical_time": physical_time,
        "filter_type": filter_type,
        "sigma_grid": sigma_grid,
        "smoothing_key": smoothing_key,
        "smoothing_label": smoothing_label,
    }


def result_selection_catalog(paths: list[Path]) -> list[dict]:
    catalog = [
        metadata
        for path in paths
        if (metadata := result_selection_metadata(path)) is not None
    ]
    def selection_key(item):
        return (item["time_index"], item["filter_type"], item["sigma_grid"], item["smoothing_key"])

    newest = {}
    for item in catalog:
        key = selection_key(item)
        newest[key] = max(newest.get(key, 0), item["schema_version"])
    return [item for item in catalog if item["schema_version"] == newest[selection_key(item)]]


def _time_selection_label(time_index: int, catalog: list[dict]) -> str:
    physical_times = {
        item["physical_time"]
        for item in catalog
        if item["time_index"] == time_index and item["physical_time"] is not None
    }
    if len(physical_times) == 1:
        return f"frame {time_index} (t={next(iter(physical_times)):g})"
    return f"frame {time_index}"


def _weak_asymmetry_figure(report: dict):
    return go.Figure(
        go.Bar(
            x=["positive/backscatter", "negative/forward", "net"],
            y=[
                report["positive_backscatter"]["sum"],
                report["negative_forward"]["sum"],
                report["global"]["pi_sum"],
            ],
        )
    ).update_layout(
        title="Full-domain positive/negative pi cancellation",
        yaxis_title="sum(pi)",
    )


def weak_asymmetry_rows(report: dict) -> list[dict[str, str]]:
    return [
        {
            "sign": "positive/backscatter",
            "sum": _scientific_text(report["positive_backscatter"]["sum"]),
            "volume_fraction": _scientific_text(
                report["positive_backscatter"]["volume_fraction"]
            ),
        },
        {
            "sign": "negative/forward",
            "sum": _scientific_text(report["negative_forward"]["sum"]),
            "volume_fraction": _scientific_text(
                report["negative_forward"]["volume_fraction"]
            ),
        },
        {
            "sign": "zero",
            "sum": _scientific_text(0.0),
            "volume_fraction": _scientific_text(
                report["zero"]["volume_fraction"]
            ),
        },
    ]


def _symmetric_color_limit(values: np.ndarray, percentile: float = 100.0) -> float:
    if not 0.0 < percentile <= 100.0:
        raise ValueError("percentile must be in (0, 100]")
    finite_magnitudes = np.abs(values[np.isfinite(values)])
    if not finite_magnitudes.size:
        return 1.0
    limit = float(np.percentile(finite_magnitudes, percentile))
    if not np.isfinite(limit) or limit <= 0.0:
        limit = float(np.max(finite_magnitudes))
    return limit if limit > 0.0 else 1.0


def _symlog_transform(values: np.ndarray, linear_threshold: float) -> np.ndarray:
    if linear_threshold <= 0.0:
        raise ValueError("linear_threshold must be positive")
    values = np.asarray(values)
    return np.sign(values) * np.log1p(np.abs(values) / linear_threshold)


def _continuous_figure(
    values: np.ndarray,
    title: str,
    *,
    signed: bool = True,
    color_percentile: float = 100.0,
    scale_mode: str = "linear",
    color_limit: float | None = None,
    storage_stride: int = 1,
    original_shape: tuple[int, int] | None = None,
):
    if scale_mode not in {"linear", "symlog"}:
        raise ValueError("scale_mode must be 'linear' or 'symlog'")
    if not signed and scale_mode != "linear":
        raise ValueError("symlog color scaling requires signed=True")
    row_stride = max(1, int(np.ceil(values.shape[0] / 512)))
    column_stride = max(1, int(np.ceil(values.shape[1] / 512)))
    shown = values[::row_stride, ::column_stride]
    # Keep the browser payload at most 512^2 while retaining source-array
    # coordinates. Plotly stretches each sampled value over its original-grid
    # footprint instead of relabelling a 1024^2 slice as 0..511.
    x_coordinates = np.arange(shown.shape[1], dtype=np.int64) * column_stride * storage_stride
    y_coordinates = np.arange(shown.shape[0], dtype=np.int64) * row_stride * storage_stride
    original_shape = original_shape or tuple(size * storage_stride for size in values.shape)
    displayed = shown
    kwargs = {}
    if signed:
        limit = (
            _symmetric_color_limit(shown, color_percentile)
            if color_limit is None
            else float(color_limit)
        )
        if not np.isfinite(limit) or limit <= 0.0:
            raise ValueError("color_limit must be finite and positive")
        displayed_limit = limit
        if scale_mode == "symlog":
            linear_threshold = limit * 0.01
            displayed = _symlog_transform(shown, linear_threshold)
            displayed_limit = float(
                _symlog_transform(np.asarray(limit), linear_threshold)
            )
        kwargs = {"zmin": -displayed_limit, "zmax": displayed_limit}
    figure = px.imshow(
        displayed,
        x=x_coordinates,
        y=y_coordinates,
        origin="lower",
        color_continuous_scale="RdBu_r" if signed else "Viridis",
        aspect="equal",
        **kwargs,
    )
    if signed and scale_mode == "symlog":
        raw_ticks = limit * np.asarray([-1.0, -0.1, -0.01, 0.0, 0.01, 0.1, 1.0])
        transformed_ticks = _symlog_transform(raw_ticks, linear_threshold)
        figure.update_traces(
            customdata=shown,
            hovertemplate="x=%{x}<br>y=%{y}<br>value=%{customdata:.6g}<extra></extra>",
        )
        figure.update_coloraxes(
            colorbar={
                "tickvals": transformed_ticks.tolist(),
                "ticktext": [f"{value:.3g}" for value in raw_ticks],
                "title": "value (SymLog)",
            }
        )
    figure.update_xaxes(
        title=f"original-grid index (stride={column_stride * storage_stride})",
        range=[0, original_shape[1] - 1],
    )
    figure.update_yaxes(
        title=f"original-grid index (stride={row_stride * storage_stride})",
        range=[0, original_shape[0] - 1],
        autorange=False,
    )
    figure.update_layout(title=title)
    return figure


def _continuous_pair(fields, titles, **options) -> None:
    """Display two fields in the original two-column order with common options."""
    for column, values, title in zip(st.columns(2), fields, titles):
        column.plotly_chart(_continuous_figure(values, title, **options), use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="JHTDB local viewer", layout="wide")
    cfg = load_config(os.environ.get("JHTDB_PIPELINE_CONFIG", "configs/pipeline.yaml"))
    st.title("JHTDB 周期域本地结果")
    paths = complete_result_paths(cfg.result_root)
    if not paths:
        st.info("persistent 中还没有带 COMPLETE 标记的正式结果。")
        return
    catalog = result_selection_catalog(paths)
    if not catalog:
        st.info("没有可读取 manifest 的完整结果。")
        return

    time_options = sorted({item["time_index"] for item in catalog})
    selected_time = st.sidebar.selectbox(
        "时间",
        time_options,
        format_func=lambda value: _time_selection_label(value, catalog),
    )
    time_catalog = [
        item for item in catalog if item["time_index"] == selected_time
    ]
    filter_options = sorted({item["filter_type"] for item in time_catalog})
    selected_filter = st.sidebar.selectbox("Filter type", filter_options)
    filter_catalog = [
        item for item in time_catalog if item["filter_type"] == selected_filter
    ]
    sigma_options = sorted({item["sigma_grid"] for item in filter_catalog})
    selected_sigma = st.sidebar.selectbox(
        "Sigma",
        sigma_options,
        format_func=lambda value: f"{value:g}",
    )
    sigma_catalog = [
        item for item in filter_catalog if item["sigma_grid"] == selected_sigma
    ]
    smoothing_options = sorted(
        {item["smoothing_key"] for item in sigma_catalog},
        key=lambda value: (value[0], -1.0 if value[1] is None else value[1]),
    )
    smoothing_labels = {
        item["smoothing_key"]: item["smoothing_label"] for item in sigma_catalog
    }
    selected_smoothing = st.sidebar.selectbox(
        "平滑参数",
        smoothing_options,
        format_func=lambda value: smoothing_labels[value],
    )
    candidates = [
        item
        for item in sigma_catalog
        if item["smoothing_key"] == selected_smoothing
    ]
    if len(candidates) != 1:
        st.error("当前选择对应多个结果，无法唯一确定加载目标。")
        return
    selected = candidates[0]["path"]
    selection_signature = (
        selected_time,
        selected_filter,
        selected_sigma,
        selected_smoothing,
    )
    if st.session_state.get("result_selection_signature") != selection_signature:
        st.session_state["result_selection_signature"] = selection_signature
        st.session_state.pop("confirmed_result_path", None)
    if st.sidebar.button("确认并加载", type="primary", use_container_width=True):
        st.session_state["confirmed_result_path"] = str(selected.resolve())

    confirmed_path = st.session_state.get("confirmed_result_path")
    if confirmed_path != str(selected.resolve()):
        st.info("请选择时间、filter type、sigma 和平滑参数，然后点击“确认并加载”。")
        return

    with st.spinner("正在加载结果……"):
        result = open_complete_result(selected)
    edge_text = ""
    if result.attrs.get("filter_type") == "smooth_sharp":
        edge_fraction = result.attrs.get("sharp_edge_width_fraction")
        edge_text = f" | edge alpha={float(edge_fraction):g}"
    st.caption(
        f"frame={result.attrs['time_index']} | "
        f"filter={result.attrs.get('filter_type', 'gaussian')} | "
        f"sigma={result.attrs['sigma_grid']}{edge_text}"
    )
    page = st.sidebar.radio(
        "页面",
        (
            "速度对比",
            "梯度对比",
            "Work",
            "Π 与 S̄",
            "Weak asymmetry",
            "全域 S̄ QA",
        ),
    )
    axis = st.sidebar.selectbox("切片法向", ("z", "y", "x"))
    index = None
    storage_stride = 1
    if page not in ("Weak asymmetry", "全域 S̄ QA"):
        field_name = "work_full" if page in ("Work", "Π 与 S̄") else "gradient_bar" if page == "梯度对比" else "velocity_bar"
        indexed_field = result[field_name]
        storage_stride = result.attrs.get("field_sampling", {}).get(field_name, {}).get("stride_xyz", [1, 1, 1])[0]
        length = spatial_axis_length(indexed_field, axis)
        scope = "全域"
        index = st.sidebar.slider(
            f"{scope}原网格切片 index", 0, (length - 1) * storage_stride,
            (length // 2) * storage_stride, step=storage_stride,
        )
        original_shape = tuple(size for name, size in zip(("z", "y", "x"), reversed(result.attrs["full_shape_xyz"])) if name != axis)
        if storage_stride > 1:
            st.caption(f"速度与梯度每轴保存间隔 {storage_stride} 个格点；切片和图轴使用原网格坐标。")

    if page == "速度对比":
        component = st.sidebar.selectbox(
            "速度分量", (0, 1, 2), format_func=lambda value: ("ux", "uy", "uz")[value]
        )
        raw, filtered = comparison_slices(result, "velocity_bar", axis, index, component)
        limit = _symmetric_color_limit(np.stack((raw, filtered)))
        _continuous_pair(
            (raw, filtered), ("velocity", "velocity_bar"), color_limit=limit,
            storage_stride=storage_stride, original_shape=original_shape,
        )
    elif page == "梯度对比":
        component = st.sidebar.selectbox(
            "速度分量 i", (0, 1, 2), format_func=lambda value: ("ux", "uy", "uz")[value]
        )
        derivative = st.sidebar.selectbox(
            "求导方向 j", (0, 1, 2), format_func=lambda value: ("x", "y", "z")[value]
        )
        label = st.sidebar.radio("梯度色标", ("线性", "SymLog"), horizontal=True)
        percentile = st.sidebar.slider("色标覆盖分位数 (%)", 90.0, 100.0, 99.0, 0.5)
        mode = "linear" if label == "线性" else "symlog"
        raw, filtered = comparison_slices(result, "gradient_bar", axis, index, component, derivative)
        limit = _symmetric_color_limit(np.stack((raw, filtered)), percentile)
        _continuous_pair(
            (raw, filtered), ("gradient", "gradient_bar"),
            color_percentile=percentile, scale_mode=mode, color_limit=limit,
            storage_stride=storage_stride, original_shape=original_shape,
        )
    elif page == "Work":
        full = extract_scalar_slice(result["work_full"], axis, index)
        resolved = extract_scalar_slice(result["work_resolved"], axis, index)
        delta = full - resolved
        _continuous_pair((full, resolved), ("work_full", "work_resolved"))

        st.plotly_chart(
            _continuous_figure(delta, "ΔW = W_full − W_resolved"),
            use_container_width=True,
        )
    elif page == "Π 与 S̄":
        pi = extract_scalar_slice(result["pi"], axis, index)
        s_bar = extract_scalar_slice(result["s_bar"], axis, index)
        limit = _symmetric_color_limit(np.stack((pi, s_bar)), 99.0)
        _continuous_pair((pi, s_bar), ("Π = τᵢⱼ ∂ⱼūᵢ", "S̄ = ∂ⱼ(ūᵢτᵢⱼ)"), color_limit=limit)
        st.caption(
            "式 (2) 符号约定：W_full = W_resolved − Π + S̄；"
            "常见 LES 定义 Π_conventional = −τ:S = −Π。"
        )
        full = extract_scalar_slice(result["work_full"], axis, index)
        resolved = extract_scalar_slice(result["work_resolved"], axis, index)
        residual = energy_identity_residual(full, resolved, pi, s_bar)
        st.plotly_chart(
            _continuous_figure(
                residual,
                "当前切片能量等式残差 W_full − W_resolved + Π − S̄",
                color_percentile=99.0,
            ),
            use_container_width=True,
        )
        st.json(dict(result.attrs.get("decomposition", {})))
    elif page == "Weak asymmetry":
        st.header("全域 Π weak asymmetry")
        report_path = selected / "weak_asymmetry.json"
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("passed"):
                st.success("Π 正负分拆 closure：通过")
            else:
                st.error("Π 正负分拆 closure：失败")
            global_values = report["global"]
            left, middle, right = st.columns(3)
            left.metric("mean(pi)", _scientific_text(global_values["pi_mean"]))
            middle.metric("rms(pi)", _scientific_text(global_values["pi_rms"]))
            right.metric(
                "mean(pi)/rms(pi)",
                _scientific_text(global_values["asymmetry_index"]),
            )
            p99_column, max_column = st.columns(2)
            p99_column.metric(
                "|mean(pi)| / p99(|pi|)",
                _scientific_text(global_values.get("ratio_p99")),
            )
            max_column.metric(
                "|mean(pi)| / max(|pi|)",
                _scientific_text(global_values.get("ratio_max")),
            )
            st.caption(
                "项目符号：pi=tau:S；pi<0 为 forward cascade，pi>0 为 backscatter。"
            )
            st.plotly_chart(
                _weak_asymmetry_figure(report), use_container_width=True
            )
            st.dataframe(
                weak_asymmetry_rows(report),
                hide_index=True,
                use_container_width=True,
            )
            with st.expander("查看 weak_asymmetry.json 原始报告"):
                st.json(report)

        else:
            st.warning(
                "当前正式结果没有 weak_asymmetry.json；运行 "
                "compute-weak-asymmetry，或重新执行 single-frame 自动补齐。"
            )
    else:
        st.header("全域 S̄ QA")
        s_bar_qa = selected / "s_bar_qa.json"
        if s_bar_qa.is_file():
            report = json.loads(s_bar_qa.read_text(encoding="utf-8"))
            if report.get("passed"):
                st.success("全域 S̄ QA：通过")
            else:
                st.error("全域 S̄ QA：失败；正式数据仍保留用于诊断")
            st.caption(
                f"{report.get('identity', 'work_full = work_resolved - pi + s_bar')} | "
                f"scope={report.get('scope')} | points={report.get('point_count', 0):,}"
            )
            columns = st.columns(len(SBAR_METRIC_SPECS))
            for column, (key, label) in zip(columns, SBAR_METRIC_SPECS):
                metric = report.get("metrics", {}).get(key, {})
                column.metric(label, _scientific_text(metric.get("value")))
                status = "通过" if metric.get("passed") else "失败"
                column.caption(
                    f"阈值 ≤ {_scientific_text(metric.get('threshold'))} · {status}"
                )
            st.dataframe(
                sbar_metric_rows(report), hide_index=True, use_container_width=True
            )
            st.plotly_chart(
                _global_totals_figure(report), use_container_width=True
            )
            with st.expander("查看 s_bar_qa.json 原始报告"):
                st.json(report)
        else:
            st.warning(
                "当前正式结果没有 s_bar_qa.json。请选择已完成的当前 schema 结果，"
                "或对完整结果运行 qa-sbar。正在计算的 staging 不会进入 GUI。"
            )
        st.subheader("完整性与其他 QA 记录")
        for filename in ("manifest.json", "qa.json", "divergence.json", "COMPLETE"):
            path = selected / filename
            st.subheader(filename)
            if path.is_file():
                try:
                    st.json(json.loads(path.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    st.code(path.read_text(encoding="utf-8"))
            else:
                st.warning("missing")

    st.caption("本 GUI 只读配置 result_root 中的全域正式结果，不修改计算数据。")


if __name__ == "__main__":
    main()
