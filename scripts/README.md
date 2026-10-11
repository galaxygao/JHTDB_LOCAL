# PowerShell 运行脚本

首次持久部署与 token 文件统一见 [根 README](../README.md#first-deployment)。
`deploy.py --stage setup` 创建的是 `.venv-windows`；本页旧 PowerShell 脚本固定使用 `.venv`，
不会自动采用 `.venv-windows`。已按新教程部署时，直接使用根 README 的 Python CLI 命令。
下列脚本保留原有环境约定，不作为新部署教程的必需步骤。

## `bootstrap_local.ps1`

创建 `.venv`，安装项目及测试依赖，编译源码并运行测试：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_local.ps1
```

## `run_stage.ps1`

使用项目虚拟环境执行单帧生产入口：

```powershell
.\scripts\run_stage.ps1 -Stage single-frame -TimeIndex 1
```

可用 `-SigmaGrid 30` 只处理一个 sigma，`-Config` 指定其他 YAML。

## `run_smooth_sharp_full_pipeline.ps1`

当前比例 smooth-sharp 的一键全流程：

1. `single-frame` 完成多 sigma 输入、计算、QA 和正式提交；
2. 打印最终 pipeline status。

生产默认值：

```powershell
.\scripts\run_smooth_sharp_full_pipeline.ps1
```

自定义新时间帧：

```powershell
.\scripts\run_smooth_sharp_full_pipeline.ps1 `
  -TimeIndex 7 `
  -SigmaGrids 8,16,32,64 `
  -SharpEdgeWidthFraction 0.10
```

参数：

| 参数 | 默认 | 含义 |
|---|---:|---|
| `TimeIndex` | `1` | JHTDB stored time index，必须 >=1 |
| `SigmaGrids` | `10,15,30,55,75` | 唯一正 sigma 列表 |
| `SharpEdgeWidthFraction` | `0.1171875` | 比例宽度 `alpha=w/k_c` |
| `Config` | `configs/pipeline.yaml` | YAML 路径 |

完整 CLI 分阶段方式见根 README。


## macOS 主计算（10 核 / 24 GB）

`bash scripts/run_main_macos.sh` 使用 `configs/pipeline.macos.yaml`，一次调用 `process-batch`，
按配置执行五个 sigma，向量场每轴步长 2 保存，标量场完整保存，使用磁盘共享梯度和 FFT 缓存。输出直接显示在终端。
该脚本仅运行主计算。输入应先完成 cache 和 validate-input。
通过 `JHTDB_MAIN_CONFIG=/绝对路径/config.yaml` 可选择另一配置。
第一个参数指定时间帧，例如 `bash scripts/run_main_macos.sh 500` 计算第 500 帧；
不传参数时默认第 1 帧。前面的 cache、validate-input  必须使用同一帧号。
全流程见[根 README](../README.md)，直接调用 Python `process-batch`，使用 `TIME_INDEX` 变量统一帧号；本脚本是可选包装。
主脚本必须显式接收这个变量；Python 命令的 `--time-index` 不会自动传给脚本：

```bash
TIME_INDEX=500
CONFIG=configs/pipeline.macos.yaml
JHTDB_MAIN_CONFIG="$CONFIG" bash scripts/run_main_macos.sh "$TIME_INDEX"
```

## 文档维护与 QPower 入口

- `python scripts/update_docs.py` / `--check`：生成函数/参数参考并校验文档链接。
- QPower 下载辅助脚本位于 [qpower_analysis/scripts](../qpower_analysis/scripts)，说明见 [QPower README](../qpower_analysis/README.md)。
- `run_stage.ps1` 的 `-WithPressureGradient`、`run_smooth_sharp_full_pipeline.ps1` 的同名开关调用服务端梯度入口。

返回 [根 README](../README.md)，完整 [命令参考](../docs/cli_reference.md)。
