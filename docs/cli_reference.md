# 全功能命令与参数参考

全部命令从项目根目录运行，`python` 替换为本机虚拟环境解释器。以下 argparse 参数直接从代码生成，保留 default/type/choices/required/help；共用 helper 参数会在其所属模块列出。表达式默认值的实际值以配置/运行时 `--help` 为准。

主入口：`python -m jhtdb_pipeline COMMAND --config CONFIG`。各命令及前后置条件见 [操作手册](handbook.md)。独立脚本用 `python 路径 --help`。PowerShell/bash 包装入口见 [scripts README](../scripts/README.md)。

| 主命令 | 行为 |
|---|---|
| auth status | token 配置来源；不验证网络 |
| doctor / plan | 环境、路径、资源 / 请求规划 |
| smoke | 小型在线请求 |
| cache / validate-input | 下载续传 / 本地完整校验 |
| status | catalog 和正式结果状态；不包含本地 FD4 manifest |
| process-full / finalize-result | 单尺度计算（或配置全部尺度）/显式提交 |
| process-batch | 多尺度共享计算与提交 |
| single-frame | 必要时 doctor、cache、validate、batch；完整结果可直接复用 |
| compute-cq / compute-weak-asymmetry / qa-sbar | 重算或复用正式 QA 报告 |
| compute-regime-pi | 独立逐 regime 输出 |
| gui | 启动只读 Streamlit |

`--sigma-grid` 与 `--sigma-grids` 互斥，后者仅 batch/single-frame/regime-pi 支持。滤波覆盖参数只作用于本次命令。主 CLI 通常成功 0，异常 1，doctor/QA 不通过 2；argparse 用法错误也为 2。

## block_statistics/compute_block_statistics.py

[实现](../block_statistics/compute_block_statistics.py)

```python
parser.add_argument("--config", default="configs/pipeline.yaml")
parser.add_argument("--time-index", type=int, required=True)
parser.add_argument("--sigma-grid", type=float, required=True)
parser.add_argument("--filter-type", choices=FILTER_TYPES)
parser.add_argument("--sharp-edge-width-fraction", type=float)
parser.add_argument("--blocks-per-axis", type=int, default=16)
parser.add_argument("--output-root", type=Path, default=Path("block_statistics/output"))
parser.add_argument("--scratch-root", type=Path, default=Path("block_statistics/.scratch"))
parser.add_argument("--overwrite", action="store_true")
```

## block_statistics/plot_vs_strain.py

[实现](../block_statistics/plot_vs_strain.py)

```python
parser.add_argument(
        "--input-csv",
        "--input",
        dest="input_csv",
        type=Path,
        required=True,
        help="block CSV path or its containing result directory",
    )
parser.add_argument("--output-dir", type=Path)
```

## block_statistics/regime_pair_asymmetry.py

[实现](../block_statistics/regime_pair_asymmetry.py)

```python
parser.add_argument("--config", default="configs/pipeline.yaml")
parser.add_argument("--time-index", type=int, required=True)
parser.add_argument("--sigma-grid", type=float, required=True)
parser.add_argument("--filter-type", choices=FILTER_TYPES)
parser.add_argument("--sharp-edge-width-fraction", type=float)
parser.add_argument("--blocks-per-axis", type=int, default=16)
parser.add_argument("--output-root", type=Path, default=Path("block_statistics/output"))
parser.add_argument("--overwrite", action="store_true")
```

## deploy.py

[实现](../deploy.py)

```python
parser.add_argument("--stage", choices=("setup", "check", "velocity", "download", "qpower", "all"), default="all")
parser.add_argument("--time-index", type=int, default=1)
parser.add_argument("--data-root", type=Path, default=PROJECT / ".local")
parser.add_argument("--token-file", type=Path)
parser.add_argument("--skip-install", action="store_true", help="Reuse the installed local environment")
parser.add_argument("--background", action="store_true", help="Continue independently of the terminal; write deploy.log")
parser.add_argument("--wait-lock", action="store_true", help="Wait for another deployment using the same data root")
```

## flux_plateau/plot_pi_epsilon_vs_k.py

[实现](../flux_plateau/plot_pi_epsilon_vs_k.py)

```python
parser.add_argument("--config", default="configs/pipeline.yaml")
parser.add_argument("--time-index", type=int, required=True)
parser.add_argument("--viscosity", type=float, default=DEFAULT_VISCOSITY)
parser.add_argument(
        "--epsilon-reference", type=float, default=DEFAULT_EPSILON_REFERENCE
    )
parser.add_argument("--eta-reference", type=float, default=DEFAULT_ETA_REFERENCE)
parser.add_argument("--output-dir", type=Path)
```

## pi_pdf/plot_pi_pdf.py

[实现](../pi_pdf/plot_pi_pdf.py)

```python
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
```

## pi_pdf/validate_log_pi_gaussian.py

[实现](../pi_pdf/validate_log_pi_gaussian.py)

```python
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
```

## pi_slices/plot_orthogonal_slices.py

[实现](../pi_slices/plot_orthogonal_slices.py)

```python
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
```

## qpower_analysis/angle_statistics.py

[实现](../qpower_analysis/angle_statistics.py)

```python
parser.add_argument('--run-dir',type=Path,required=True)
parser.add_argument('--alpha',type=float,default=1.)
parser.add_argument('--beta',type=float,default=1.)
```

## qpower_analysis/conditional_ranges.py

[实现](../qpower_analysis/conditional_ranges.py)

```python
parser.add_argument('--run-dir',required=True,type=Path)
parser.add_argument('--coverage',type=float,default=.5)
parser.add_argument('--from-histograms',action='store_true')
```

## qpower_analysis/conditional_tails.py

[实现](../qpower_analysis/conditional_tails.py)

```python
parser.add_argument('--run-dir',required=True,type=Path)
```

## qpower_analysis/qpower_analysis.py

[实现](../qpower_analysis/qpower_analysis.py)

```python
parser.add_argument("--config", required=True, type=Path)
parser.add_argument("--preflight-only", action="store_true")
```

## qpower_analysis/scripts/download_then_qpower.py

[实现](../qpower_analysis/scripts/download_then_qpower.py)

```python
parser.add_argument("--job-dir", required=True, type=Path)
parser.add_argument("--pipeline-config", default="configs/pipeline.yaml")
parser.add_argument("--analysis-config", default="qpower_analysis/config.example.json")
```

## qpower_analysis/scripts/quickstart_qpower_subset.py

[实现](../qpower_analysis/scripts/quickstart_qpower_subset.py)

```python
parser.add_argument('--config', type=Path, default=PROJECT / 'configs/pipeline.yaml')
parser.add_argument('--shape-xyz', type=int, nargs=3, default=(128, 128, 64),
                        metavar=('NX', 'NY', 'NZ'), help='Origin-aligned crop, multiples of 16')
```

## qpower_analysis/threshold_contributions.py

[实现](../qpower_analysis/threshold_contributions.py)

```python
parser.add_argument('--run-dir',required=True,type=Path)
```

## scatter/plot_exact_scatter.py

[实现](../scatter/plot_exact_scatter.py)

```python
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
```

## scripts/rebuild_v7.py

[实现](../scripts/rebuild_v7.py)

```python
parser.add_argument('--config', required=True, help='Current v7-compatible YAML pointing at existing velocity inputs')
parser.add_argument('--source-result', required=True, type=Path, help='Completed v6 or v7 result directory')
parser.add_argument('--result-root', required=True, type=Path, help='Separate destination root; never the source root')
parser.add_argument('--execute', action='store_true', help='Validate full input and perform computation; default prints plan only')
```

## scripts/update_docs.py

[实现](../scripts/update_docs.py)

```python
parser.add_argument('--check', action='store_true')
```

## src/jhtdb_pipeline/cli.py

[实现](../src/jhtdb_pipeline/cli.py)

```python
parser.add_argument("--config", default=DEFAULT_CONFIG)
parser.add_argument("--time-index", type=int, required=True)
parser.add_argument("--sigma-grid", type=float)
parser.add_argument(
        "--filter-type",
        choices=FILTER_TYPES,
        help="override physics.filter_type for this command",
    )
parser.add_argument(
        "--sharp-edge-width-fraction",
        type=float,
        help="set the smooth-sharp width alpha=w/k_c",
    )
commands.add_parser("auth", help="report JHTDB token status")
auth_parser.add_argument("action", choices=("status",))
commands.add_parser("doctor", help="check local environment")
doctor_parser.add_argument("--time-index", type=int)
commands.add_parser(name)
command.add_argument("--field", choices=("velocity", "pressure_gradient"), default="velocity")
command.add_argument("--with-pressure-gradient", action="store_true")
commands.add_parser(name)
command.add_argument("--with-pressure-gradient", action="store_true")
command.add_argument(
                "--sigma-grids",
                type=float,
                nargs="+",
                metavar="SIGMA",
                help=(
                    "compute these sigma values sequentially"
                    if name == "compute-regime-pi"
                    else "process these sigma values in one shared-FFT batch"
                ),
            )
commands.add_parser("gui", help="start the read-only server GUI")
gui.add_argument("--port", type=int, default=8501)
```

## src/jhtdb_pipeline/pressure_local.py

[实现](../src/jhtdb_pipeline/pressure_local.py)

```python
parser.add_argument("--config", required=True)
parser.add_argument("--time-index", required=True, type=int)
parser.add_argument("--stage", choices=("download", "gradient", "follow", "all"), default="all")
parser.add_argument("--block-size", type=int, default=64)
```

