# JHTDB 全周期域计算与湍流统计

本项目下载 `isotropic1024coarse` 的完整 `1024³` 速度场，在 `[0,2π)³` 周期域上进行 Gaussian / smooth-sharp 谱滤波、速度梯度、能量传输和 QA，并提供只读 Streamlit GUI。压力下载及 FD4 梯度用于独立 QPower 分析。

当前正式结果格式为 **v9，全域计算、向量场步长 2 存储**。共享原始梯度、滤波速度和滤波梯度保存原网格 `[::2,::2,::2]` 的 `512³` 点；原始速度输入及所有标量场保留完整 `1024³`。本文全部命令从项目根目录执行。

## 文档入口与新会话阅读顺序

| 文档 | 内容 |
|---|---|
| [项目实现与接手指南](docs/architecture.md) | 调用流程、公式、符号、锁、校验链、故障定位、维护规则 |
| [完整操作 handbook](docs/handbook.md) | 每项配置、GUI、单尺度/多尺度、自定义参数、恢复与统计 |
| [完整命令参考](docs/cli_reference.md) | 所有 Python 入口与参数，含子项目和维护工具 |
| [系统迁移](docs/system_migration.md) | Windows/macOS/Linux 环境、输入迁移、SQLite、绝对路径引用 |
| [当前数据格式](docs/data_versions.md) | v7/v8/v9 字段、采样坐标、shape、dtype、布局与读取规则 |
| [部署与压力流程](docs/deployment.md) | `deploy.py` 分阶段运行、后台日志、本地 FD4、QPower |
| [macOS 内存与磁盘方案](docs/macos_main_pipeline_run.md) | memmap、线程与资源限制 |
| [Pitt CRC Linux 资源方案](docs/linux_crc_run.md) | 两个 pipeline 的 Slurm 资源、RAM 缓存、线程、路径与原有运行命令 |
| [服务端压力梯度入口](docs/pressure_gradient_loading.md) | 独立 `fd4noint` 数据源，与本地 FD4 区分 |
| [代码逐函数索引](docs/code_reference.md) | 每个模块、函数签名、源码位置、调用与异常；子项目有独立索引 |
| [文档维护与校验](docs/maintenance.md) | 更新命令、回归范围、目录责任 |

新会话先读本文，再读 architecture、data_versions、handbook；按任务进入对应子项目 README 与函数索引。源码和生成索引共同构成代码细节参考，公式与运行约束以人工审阅的实现说明为准。

## 环境与资源

Python **3.9+**；依赖在 [pyproject.toml](pyproject.toml)。各系统重建自己的虚拟环境，不复制环境目录。Windows 生产配置使用 RAM FFT；24 GB Mac 使用 `configs/pipeline.macos.yaml` 的磁盘 FFT。完整速度输入约 12 GiB，五尺度永久数据未压缩约 126.5 GiB，另需约 84.09 GiB 共享磁盘缓存、工作区和安全余量。以 `plan`/预检为准；24 GB Mac 的完整域峰值尚未实测。

### 进入和退出虚拟环境

从项目根目录运行。环境目录不存在时，先按对应平台命令创建并安装依赖；激活不是必须的，文档中的 `.venv-*/bin/python` 或 `.venv\Scripts\python.exe` 也可以直接调用。

```bash
# macOS
source .venv-mac/bin/activate

# Linux
source .venv-linux/bin/activate

# 查看当前解释器
which python
python --version

# 退出
deactivate
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python --version
deactivate
```

如果 PowerShell 禁止当前用户执行激活脚本，只对当前窗口临时放开：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

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
& $Python -m jhtdb_pipeline status --config $Config
& $Python -m jhtdb_pipeline gui --config $Config --port 8501
```

逐条检查退出码，失败时停止后续命令。已安装环境可跳过创建和安装。主功能串行流程见 [scripts README](scripts/README.md)。

### macOS / zsh 或 bash：主流水线全流程

帧号只在 `TIME_INDEX` 一处设置；下面以第 500 帧为例。已有环境和 token 配置时可跳过创建、安装和 token 录入。

```bash
python3 -m venv .venv-mac
.venv-mac/bin/python -m pip install -e '.[dev]'
# getpass 隐藏输入；export 让后续 Python 进程读取。
export JHTDB_TOKEN="$(.venv-mac/bin/python -c 'import getpass; print(getpass.getpass("JHTDB token: "))')"
PYTHON=.venv-mac/bin/python
CONFIG=configs/pipeline.macos.yaml
TIME_INDEX=500
"$PYTHON" -m jhtdb_pipeline auth status --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline doctor --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline plan --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline smoke --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline cache --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline validate-input --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -u -m jhtdb_pipeline process-batch --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline status --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline gui --config "$CONFIG" --port 8501
```

逐条执行，失败即停。GUI 地址 `http://127.0.0.1:8501`。默认 sigma 为 `10 15 30 55 75`，smooth-sharp 的 `alpha=w/k_c=0.1171875`。`process-batch` 顺序复用共享梯度与频谱，不要另开并行 sigma 任务。
命令间的 `&&` 确保失败后停止后续步骤。上面的流程直接调用 `process-batch`，所有帧相关命令显式使用同一个 `TIME_INDEX`，换帧只需修改变量。macOS 上可在主计算命令前加 `caffeinate -i` 防止空闲睡眠。可选包装脚本 `bash scripts/run_main_macos.sh "$TIME_INDEX"` 内置此功能；不传位置参数时默认第 1 帧，不会继承前一条 Python 命令的 `--time-index`。

### Linux

Pitt CRC 直接使用原有函数和 CLI，配合 [Linux RAM 配置](configs/pipeline.linux.crc.yaml)
及 [QPower 配置](qpower_analysis/config.linux.crc.json)。主流程建议单节点、单任务
**32 CPU / 160G / 12 小时**；已有 float32 压力梯度的 QPower 建议
**16 CPU / 96G / 6 小时**。192G 是额外留余量的选择，并非最低要求；128G 尚未实测。
当前 64 GB allocation 放不下约 84.09 GiB 的主流程共享 RAM 缓存，需要申请更大资源。
walltime 为首次申请建议，不是已测完成时间。

完整 [Linux 资源方案](docs/linux_crc_run.md) 给出 Slurm 申请、所有资源设置、存储规划、
下载/FD4 分阶段命令及后处理。没有新增 Linux Python 入口或运行脚本，Python 源码保持原样。

已有环境与输入时，在新 allocation 中设置环境变量，再调用原有入口：

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
PYTHON=.venv-linux/bin/python
CONFIG=configs/pipeline.linux.crc.yaml
QCONFIG=qpower_analysis/config.linux.crc.json
TIME_INDEX=1

export OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 OMP_DYNAMIC=FALSE
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MKL_DYNAMIC=FALSE
export BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 NUMEXPR_MAX_THREADS=1
export TMPDIR=/vast/lfang/xig134/JHTDB_CRC/tmp
export XDG_CACHE_HOME=/ix/lfang/xig134/JHTDB_CRC/cache
export MPLCONFIGDIR="$XDG_CACHE_HOME/matplotlib"
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$MPLCONFIGDIR"

# 主 pipeline：本地校验与五尺度 RAM 计算，不自动下载
"$PYTHON" -m jhtdb_pipeline validate-input --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -u -m jhtdb_pipeline process-batch --time-index "$TIME_INDEX" --config "$CONFIG"

# 已有压力时求本地 FD4；已有梯度可跳过此条
"$PYTHON" -m jhtdb_pipeline.pressure_local --stage gradient --block-size 64 \
  --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m qpower_analysis.qpower_analysis --config "$QCONFIG" --preflight-only &&
"$PYTHON" -u -m qpower_analysis.qpower_analysis --config "$QCONFIG"
```

主配置使用 FFT 24 worker、压缩 4 线程、slab 16，磁盘余量各 32 GiB；
BLAS/OpenMP 等在 shell 中限制为 1 线程。QPower 保留原有整帧 RAM 读入和 numcodecs
最多 8 线程的默认值，配置为单帧；两条流程、下载和 FD4 顺序执行。
QPower JSON 默认第 1 帧；换帧时也需同步修改 JSON 的 frame、time 和输入路径。
原始缓存保留 `/ix/lfang/persistent/state`，结果集中到 `/ix/lfang/xig134/JHTDB_CRC`，
原有工作文件及 TMPDIR 配置到 `/vast/lfang/xig134/JHTDB_CRC`。
本次没有执行这些命令或创建外部数据目录。首次环境安装见[系统迁移](docs/system_migration.md)。
其他 Linux 环境按本机资源修改配置；macOS 的 `caffeinate` 包装脚本仅用于 macOS。

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

通用 Linux 使用 `python3 deploy.py --stage all --data-root .local`。该入口创建本机环境、注入本机路径、doctor、smoke、下载完整速度与压力、保存周期 FD4 梯度，最后执行 QPower；**不运行多 sigma 主计算**。仅下载用 `--stage download`；之后 `--stage qpower --skip-install` 计算梯度并分析。完整 QPower 仅输入加载就约 24 GiB，24 GB Mac 应只下载，转到足够内存机器分析。[完整部署说明](docs/deployment.md)。Pitt CRC 按上面的 Linux 章节显式指定专用配置；原有 `deploy.py` 不会自动采用这些 Linux 资源参数。

## 两个 pipeline

| 目录 | 功能与独立手册 |
|---|---|
| [主功能](src/jhtdb_pipeline/README.md) | 下载、滤波、速度梯度、能量传输、QA 与 GUI |
| [qpower_analysis](qpower_analysis/README.md) | 压力功率、事件重叠、条件尾部/分位带、角度统计 |

子项目专用脚本、测试和结果存于各自目录；共享下载、谱运算、正式结果和 GUI 接口在 `src/jhtdb_pipeline`。科学数组不内嵌文档；原始结果与运行 provenance 保留在输出目录。存储的 `pi=τ:S`：负值为 forward，正值为 backscatter；LES 记号取其负值。
