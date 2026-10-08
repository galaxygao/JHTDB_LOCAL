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
| compute-weak-asymmetry / qa-sbar | 重算或复用正式 QA 报告 |
| gui | 启动只读 Streamlit |

`--sigma-grid` 与 `--sigma-grids` 互斥，后者仅 batch/single-frame 支持。滤波覆盖参数只作用于本次命令。主 CLI 通常成功 0，异常 1，doctor/QA 不通过 2；argparse 用法错误也为 2。

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

## qpower_analysis/gradient_given_q.py

[实现](../qpower_analysis/gradient_given_q.py)

```python
parser.add_argument('--run-dir', required=True, type=Path)
```

## qpower_analysis/lowest_q_bin_angles.py

[实现](../qpower_analysis/lowest_q_bin_angles.py)

```python
parser.add_argument('--run-dir', type=Path, required=True)
```

## qpower_analysis/near_zero_diagnostic.py

[实现](../qpower_analysis/near_zero_diagnostic.py)

```python
parser.add_argument('--run-dir', type=Path, required=True)
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

## qpower_analysis/scripts/render_h0_cavities.py

[实现](../qpower_analysis/scripts/render_h0_cavities.py)

```python
ap.add_argument('directory', type=Path)
ap.add_argument('--n', type=int, default=1024)
```

## qpower_analysis/strong_event_h0.py

[实现](../qpower_analysis/strong_event_h0.py)

```python
parser.add_argument('--run-dir', type=Path, required=True)
parser.add_argument('--out-dir', type=Path)
parser.add_argument('--alpha', type=float, default=1.)
parser.add_argument('--beta', type=float, default=1.)
parser.add_argument('--initial-radius', type=int, default=32,
                        help='Initial offset enumeration radius in grid spacings; expands until connected')
parser.add_argument('--prepare-only', action='store_true')
parser.add_argument('--from-results', action='store_true', help='Regenerate reports/plots from completed engine output')
```

## qpower_analysis/threshold_contributions.py

[实现](../qpower_analysis/threshold_contributions.py)

```python
parser.add_argument('--run-dir',required=True,type=Path)
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
                help="process these sigma values in one shared-FFT batch",
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

