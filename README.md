# JHTDB 全周期域计算与湍流统计

本项目下载 `isotropic1024coarse` 的完整 `1024³` 速度场，在 `[0,2π)³` 周期域上进行 Gaussian / smooth-sharp 谱滤波、速度梯度、能量传输、六 regime 统计和 QA，并提供只读 Streamlit GUI。压力下载及 FD4 梯度用于独立 QPower 分析；block statistics、Pi PDF、切片、密度图和通量平台分别由子项目提供。

当前正式结果格式为 **v7，全域保存**。文档只维护 v6、v7 两版主结果格式；旧中心裁剪结果需从完整速度重建，不能改版本号充当全域结果。本文全部命令从项目根目录执行。

## 文档入口与新会话阅读顺序

| 文档 | 内容 |
|---|---|
| [项目实现与接手指南](docs/architecture.md) | 调用流程、公式、符号、锁、校验链、故障定位、维护规则 |
| [完整操作 handbook](docs/handbook.md) | 每项配置、GUI、单尺度/多尺度、自定义参数、恢复与统计 |
| [完整命令参考](docs/cli_reference.md) | 所有 Python 入口与参数，含子项目和维护工具 |
| [系统迁移](docs/system_migration.md) | Windows/macOS/Linux 环境、输入迁移、SQLite、绝对路径引用 |
| [数据格式与版本更新](docs/data_versions.md) | v6/v7 字段、shape、dtype、布局、重建脚本与命令 |
| [部署与压力流程](docs/deployment.md) | `deploy.py` 分阶段运行、后台日志、本地 FD4、QPower |
| [macOS 内存与磁盘方案](docs/macos_main_pipeline_run.md) | memmap、线程与资源限制 |
| [服务端压力梯度入口](docs/pressure_gradient_loading.md) | 独立 `fd4noint` 数据源，与本地 FD4 区分 |
| [代码逐函数索引](docs/code_reference.md) | 每个模块、函数签名、源码位置、调用与异常；子项目有独立索引 |
| [文档维护与校验](docs/maintenance.md) | 更新命令、回归范围、目录责任 |

新会话先读本文，再读 architecture、data_versions、handbook；按任务进入对应子项目 README 与函数索引。源码和生成索引共同构成代码细节参考，公式与运行约束以人工审阅的实现说明为准。

## 环境与资源

Python **3.9+**；依赖在 [pyproject.toml](pyproject.toml)。各系统重建自己的虚拟环境，不复制环境目录。Windows 生产配置使用 RAM FFT；24 GB Mac 使用 `configs/pipeline.macos.yaml` 的磁盘 FFT。完整速度输入约 12 GiB，五尺度永久数据未压缩约 373 GiB，另需约 84.09 GiB 共享磁盘缓存、工作区和安全余量。以 `plan`/预检为准；24 GB Mac 的完整域峰值尚未实测。

### Windows / PowerShell：主流水线全流程

先检查 [Windows 配置](configs/pipeline.yaml) 的 `platform` 路径与磁盘空间。

```powershell
py -3 -m venv .venv
$Python = ".\.venv\Scripts\python.exe"
& $Python -m pip install -e ".[dev]"
# 隐藏输入 token，仅注入当前进程；不要把真实 token 写进命令或 YAML。
$Secret = Read-Host "JHTDB token" -AsSecureString
$env:JHTDB_TOKEN = [System.Net.NetworkCredential]::new("", $Secret).Password
$Config = "configs/pipeline.yaml"
& $Python -m jhtdb_pipeline auth status --config $Config
& $Python -m jhtdb_pipeline doctor --time-index 1 --config $Config
& $Python -m jhtdb_pipeline plan --time-index 1 --config $Config
& $Python -m jhtdb_pipeline smoke --time-index 1 --config $Config
& $Python -m jhtdb_pipeline cache --time-index 1 --config $Config
& $Python -m jhtdb_pipeline validate-input --time-index 1 --config $Config
& $Python -m jhtdb_pipeline process-batch --time-index 1 --config $Config
& $Python -m jhtdb_pipeline compute-regime-pi --time-index 1 --config $Config
& $Python -m jhtdb_pipeline status --config $Config
& $Python -m jhtdb_pipeline gui --config $Config --port 8501
```

逐条检查退出码，失败时停止后续命令。已安装环境可跳过创建和安装。包含 block 统计的串行流程见 [scripts README](scripts/README.md)。

### macOS / zsh 或 bash：主流水线全流程

```bash
python3 -m venv .venv-mac
.venv-mac/bin/python -m pip install -e '.[dev]'
# getpass 隐藏输入；export 让后续 Python 进程读取。
export JHTDB_TOKEN="$(.venv-mac/bin/python -c 'import getpass; print(getpass.getpass("JHTDB token: "))')"
PYTHON=.venv-mac/bin/python
CONFIG=configs/pipeline.macos.yaml
"$PYTHON" -m jhtdb_pipeline auth status --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline doctor --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline plan --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline smoke --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline cache --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline validate-input --time-index 1 --config "$CONFIG"
bash scripts/run_main_macos.sh
"$PYTHON" -m jhtdb_pipeline compute-regime-pi --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline status --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline gui --config "$CONFIG" --port 8501
```

逐条执行，失败即停。GUI 地址 `http://127.0.0.1:8501`。默认 sigma 为 `10 15 30 55 75`，smooth-sharp 的 `alpha=w/k_c=0.1171875`。`process-batch` 顺序复用共享梯度与频谱，不要另开并行 sigma 任务。

### Linux

```bash
python3 -m venv .venv-linux
.venv-linux/bin/python -m pip install -e '.[dev]'
cp configs/pipeline.macos.yaml configs/pipeline.linux.local.yaml
export JHTDB_TOKEN="$(.venv-linux/bin/python -c 'import getpass; print(getpass.getpass("JHTDB token: "))')"
PYTHON=.venv-linux/bin/python
CONFIG=configs/pipeline.linux.local.yaml
"$PYTHON" -m jhtdb_pipeline auth status --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline doctor --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline plan --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline smoke --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline cache --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline validate-input --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline process-batch --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline compute-regime-pi --time-index 1 --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline status --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline gui --config "$CONFIG" --port 8501
```

先编辑本机 YAML 的三条路径、worker 和余量。Linux 复用 Python 入口；macOS shell 包装脚本依赖 `caffeinate`，不要在 Linux 调用。Linux/Windows 的真实环境运行仍需在目标机验证。

## Token 持久化与压力/QPower 全流程

CLI 优先读取 `JHTDB_TOKEN`，其次读取 YAML `auth.token_file` 指定的单行文件。POSIX 文件权限必须 `600` 或更严格。`auth status` 只说明来源已配置，在线 `smoke` 才能验证实际服务访问。文件路径和安全录入步骤见 [迁移手册](docs/system_migration.md)。

macOS：

```bash
python3 deploy.py --stage all --data-root .local
```

Windows：

```powershell
py -3 deploy.py --stage all --data-root .local
```

Linux 使用 `python3 deploy.py --stage all --data-root .local`。该入口创建本机环境、注入本机路径、doctor、smoke、下载完整速度与压力、保存周期 FD4 梯度，最后执行 QPower；**不运行多 sigma 主计算**。仅下载用 `--stage download`；之后 `--stage qpower --skip-install` 计算梯度并分析。完整 QPower 仅输入加载就约 24 GiB，24 GB Mac 应只下载，转到足够内存机器分析。[完整部署说明](docs/deployment.md)。

## 子项目

| 目录 | 功能与独立手册 |
|---|---|
| [block_statistics](block_statistics/README.md) | 全域 block、原场 SijSij、regime 成对非对称性 |
| [qpower_analysis](qpower_analysis/README.md) | 压力功率、事件重叠、条件尾部/分位带、角度统计 |
| [pi_slices](pi_slices/README.md) | Pi 正交切片 PNG/HTML |
| [scatter](scatter/README.md) | 全格点 Cartesian PDF |
| [pi_pdf](pi_pdf/README.md) | Pi PDF、尾部贡献、log-Pi 检验 |
| [regime_pi](regime_pi/README.md) | 六 regime 内 forward/backscatter |
| [flux_plateau](flux_plateau/README.md) | mean Pi/epsilon 平台及 MATLAB 对比 |

子项目专用脚本、测试和结果存于各自目录；共享下载、谱运算、正式结果和 GUI 接口在 `src/jhtdb_pipeline`。科学数组不内嵌文档；原始结果与运行 provenance 保留在输出目录。存储的 `pi=τ:S`：负值为 forward，正值为 backscatter；LES 记号取其负值。
