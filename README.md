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
| [部署与压力流程](docs/deployment.md) | 三个平台的持久环境、路径规则、`deploy.py` 各阶段、FD4 与 QPower |
| [macOS 内存与磁盘方案](docs/macos_main_pipeline_run.md) | memmap、线程与资源限制 |
| [Pitt CRC Linux 资源方案](docs/linux_crc_run.md) | 两个 pipeline 的 Slurm 资源、RAM 缓存、线程、路径与原有运行命令 |
| [服务端压力梯度入口](docs/pressure_gradient_loading.md) | 独立 `fd4noint` 数据源，与本地 FD4 区分 |
| [代码逐函数索引](docs/code_reference.md) | 每个模块、函数签名、源码位置、调用与异常；子项目有独立索引 |
| [文档维护与校验](docs/maintenance.md) | 更新命令、回归范围、目录责任 |

新会话先读本文，再读 architecture、data_versions、handbook；按任务进入对应子项目 README 与函数索引。源码和生成索引共同构成代码细节参考，公式与运行约束以人工审阅的实现说明为准。

<a id="first-deployment"></a>

## 首次部署：持久环境与 token 文件

系统先安装 Python **3.9+**，依赖见 [pyproject.toml](pyproject.toml)。以下步骤在项目根目录执行，两个 pipeline 共用一个本机环境。**只部署环境使用 `--stage setup`**：创建或复用虚拟环境、安装依赖并生成路径配置，不下载科学数据、不运行 pipeline，也不创建 token 内容。省略 `--stage` 默认是 `all`，会下载和计算。

环境和 token 保存在磁盘，关闭终端或结束 Slurm job 后仍可复用；不需要每次重新安装。各系统分别建立环境，不能跨系统复制。项目采用 editable 安装，应保留源码目录；移动项目或更换基础 Python 后重新部署。

### 1. 按系统一键安装环境

Windows / PowerShell：先进入你的项目目录，再执行。`.local` 是项目内的数据目录，也可将 `$DataRoot` 改为有足够空间的绝对路径。

```powershell
$DataRoot = '.local'
$TokenPath = Join-Path $HOME '.secrets\jhtdb_token'
py -3 deploy.py --stage setup --data-root $DataRoot --token-file $TokenPath
if ($LASTEXITCODE -ne 0) { throw '环境部署失败，请先修复再继续' }
$Python = '.\.venv-windows\Scripts\python.exe'
$Config = Join-Path $DataRoot 'pipeline.yaml'
```

macOS / zsh 或 bash：先进入你的项目目录。下面默认数据目录与 macOS 配置中的 `.local` 一致。

```bash
DATA_ROOT=.local
TOKEN_FILE="$HOME/.secrets/jhtdb_token"
python3 deploy.py --stage setup --data-root "$DATA_ROOT" --token-file "$TOKEN_FILE"
# 确认上一条成功后继续
PYTHON=.venv-mac/bin/python
CONFIG=configs/pipeline.macos.yaml
```

Linux / Pitt CRC：环境入口位于项目的 `.venv-linux`，数据根目录使用持久存储。

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
DATA_ROOT=/ix/lfang/persistent
TOKEN_FILE="$HOME/.secrets/jhtdb_token"
python3 deploy.py --stage setup --data-root "$DATA_ROOT" --token-file "$TOKEN_FILE"
# 确认上一条成功后继续
PYTHON=.venv-linux/bin/python
CONFIG=configs/pipeline.linux.crc.yaml
```

通用 Linux 可选择自己的 `DATA_ROOT`，并准备匹配本机资源的主配置。`--data-root` 不改变虚拟环境位置；CRC 已有 `.venv-linux` 若是指向持久目录的符号链接，部署会复用其解释器。不要将永久环境建在 job 的临时 scratch 中。

<a id="token-file"></a>

### 2. 首次保存 token 文件

已有有效文件时跳过。这里保存你已有的 **JHTDB token**；不涉及 SSH token。文件内容不写进命令历史或 YAML。首次安装时指定的 token 路径可以暂时不存在。

Windows / PowerShell：

```powershell
$TokenPath = Join-Path $HOME '.secrets\jhtdb_token'
$Secret = Read-Host 'JHTDB token' -AsSecureString
$TokenValue = [System.Net.NetworkCredential]::new('', $Secret).Password.Trim()
if ([string]::IsNullOrWhiteSpace($TokenValue)) { throw '输入为空，未修改 token 文件' }
New-Item -ItemType Directory -Force (Split-Path $TokenPath) | Out-Null
[IO.File]::WriteAllText($TokenPath, $TokenValue + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Remove-Variable TokenValue, Secret
Remove-Item Env:JHTDB_TOKEN -ErrorAction SilentlyContinue
```

macOS / Linux：使用第 1 步选定的虚拟环境解释器，隐藏输入并设置文件权限为 `600`。

```bash
"$PYTHON" - <<'PY'
import getpass, os
from pathlib import Path
token = getpass.getpass('JHTDB token: ').strip()
if not token:
    raise SystemExit('输入为空，未修改 token 文件')
path = Path.home() / '.secrets/jhtdb_token'
path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as f:
    os.fchmod(f.fileno(), 0o600)
    f.write(token + '\n')
PY
unset JHTDB_TOKEN
```

token 只需录入一次，更新 token 时重做此步。CLI 优先读取非空 `JHTDB_TOKEN`，其次读取 YAML 的 `auth.token_file`；上面的清除环境变量命令让后续使用文件。自定义 token 位置时，录入路径、`--token-file` 和实际运行 YAML 的 `auth.token_file` 必须一致。macOS/Linux 会拒绝组或其他用户具有权限的 token 文件。

### 3. 确认储存路径，再做本地检查

`deploy.py` 每次运行都会从 `configs/pipeline.yaml` 重新生成 `<data-root>/pipeline.yaml`，只替换路径和 token 文件位置。它不会自动采用 macOS 的磁盘 FFT 参数或 CRC 的资源配置。**不要长期修改这个生成文件来保存资源设置**；需要调整时复制为本机独立 YAML，再用 `--config` 指定。

| 内容 | Windows/macOS 默认位置 | Pitt CRC 本文方案 |
|---|---|---|
| Python 环境 | `.venv-windows/` / `.venv-mac/` | `.venv-linux/`（可为持久目录链接） |
| token 文件 | 用户主目录下 `.secrets/jhtdb_token` | `$HOME/.secrets/jhtdb_token` |
| deploy 生成的 YAML | `.local/pipeline.yaml` | `/ix/lfang/persistent/pipeline.yaml` |
| 原始输入、catalog、manifest | `.local/state/` | `/ix/lfang/persistent/state/` |
| 主计算工作文件 | `.local/runs/` | `/vast/lfang/xig134/JHTDB_CRC/runs/` |
| 主计算正式结果 | `.local/results/` | `/ix/lfang/xig134/JHTDB_CRC/results/` |
| QPower 输出 | `qpower_analysis/output/`（使用 deploy 时） | `/ix/lfang/xig134/JHTDB_CRC/qpower/`（使用 CRC JSON 时） |

Windows/macOS 使用其他 `--data-root` 时，生成配置的 state/runs/results 随之改变；**QPower 的 deploy 输出仍在项目 `qpower_analysis/output/`**。macOS 主流程的 `configs/pipeline.macos.yaml` 默认指向 `.local`，换盘时须另存本机 YAML 并同步三个 `platform` 路径。CRC 必须显式使用 `configs/pipeline.linux.crc.yaml` 和 `qpower_analysis/config.linux.crc.json`，才能采用上表的 `/vast` 工作区和独立结果目录；只给 deploy 传 `/ix/lfang/persistent` 不会启用这些路径。

Windows 使用第 1 步的 `$Python`、`$Config`：

```powershell
& $Python -m jhtdb_pipeline auth status --config $Config
if ($LASTEXITCODE -ne 0) { throw '认证配置检查失败' }
& $Python -m jhtdb_pipeline doctor --time-index 1 --config $Config
if ($LASTEXITCODE -ne 0) { throw '本地检查失败' }
```

macOS/Linux 使用第 1 步的 `PYTHON`、`CONFIG`；CRC 先按下文设置线程与缓存变量：

```bash
"$PYTHON" -m jhtdb_pipeline auth status --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline doctor --time-index 1 --config "$CONFIG"
```

这些检查不下载科学数据；`doctor` 会检查依赖、路径可写性等。`auth status` 只报告 token 来源，不能证明在线认证有效，后续 `smoke` 才会请求服务。

### 4. 下次打开终端或新 Slurm job

进入同一个项目目录，重新设置命令所需的 shell 变量即可。环境和 token 文件仍在；`PYTHON`/`CONFIG` 等变量只属于当前终端。

| 系统 | 直接调用的解释器 | 默认主配置 |
|---|---|---|
| Windows | `.\.venv-windows\Scripts\python.exe` | `.local/pipeline.yaml` 或你另存的本机 YAML |
| macOS | `.venv-mac/bin/python` | `configs/pipeline.macos.yaml` |
| Pitt CRC Linux | `.venv-linux/bin/python` | `configs/pipeline.linux.crc.yaml` |

激活可选：Windows 用 `.\.venv-windows\Scripts\Activate.ps1`，macOS 用 `source .venv-mac/bin/activate`，Linux 用 `source .venv-linux/bin/activate`；退出用 `deactivate`。直接调用表中解释器无需激活，也无需调整 PowerShell 执行策略。旧 Windows 包装脚本使用 `.venv`，与 deploy 创建的 `.venv-windows` 不同；下面统一直接调用 Python。

已有环境再调用 deploy 时加 `--skip-install`，并保持相同 `--data-root`、`--token-file`；需要更新依赖时重新执行 `--stage setup`，复用原环境进行安装。[部署细节与分阶段命令](docs/deployment.md)。

## 部署完成后：主 pipeline

以下命令会下载或计算，按资源条件选择执行。完整速度输入约 12 GiB，五尺度结果加共享梯度及输入未压缩约 126.5 GiB，另需 FFT 缓存、工作区与安全余量，以 `plan`/预检为准。默认 sigma 为 `10 15 30 55 75`，smooth-sharp 的 `alpha=w/k_c=0.1171875`，`process-batch` 串行复用共享缓存。

### Windows / PowerShell

部署使用默认 `.local` 时：

```powershell
$Python = '.\.venv-windows\Scripts\python.exe'
$Config = '.local/pipeline.yaml'
$TimeIndex = 1
# 保存本机资源调整时，先复制为独立 YAML，并将 $Config 改为该文件。
# 生成配置沿用 RAM FFT / 16 FFT worker / 8 压缩线程；先确认本机资源足够。
foreach ($Stage in @('doctor', 'plan', 'smoke', 'cache', 'validate-input', 'process-batch')) {
    & $Python -m jhtdb_pipeline $Stage --time-index $TimeIndex --config $Config
    if ($LASTEXITCODE -ne 0) { throw "$Stage 失败，停止后续流程" }
}
& $Python -m jhtdb_pipeline status --config $Config
if ($LASTEXITCODE -ne 0) { throw 'status 失败' }
& $Python -m jhtdb_pipeline gui --config $Config --port 8501
```

Windows RAM FFT 的共享缓存本身约 84.09 GiB，完整峰值更高。内存不足时先调整独立本机配置，不能只减少线程。自定义数据目录时 `$Config` 应指向该目录的配置。

### macOS / zsh 或 bash

24 GB Mac 使用已有磁盘 FFT 配置，完整域峰值尚未实测；空间规划见 [macOS 资源方案](docs/macos_main_pipeline_run.md)。

```bash
PYTHON=.venv-mac/bin/python
CONFIG=configs/pipeline.macos.yaml
TIME_INDEX=500
"$PYTHON" -m jhtdb_pipeline doctor --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline plan --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline smoke --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline cache --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline validate-input --time-index "$TIME_INDEX" --config "$CONFIG" &&
caffeinate -i "$PYTHON" -u -m jhtdb_pipeline process-batch --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline status --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline gui --config "$CONFIG" --port 8501
```

换帧只改 `TIME_INDEX`；使用其他数据盘时将 `CONFIG` 改为路径已调整的本机 YAML。GUI 地址 `http://127.0.0.1:8501`。可选包装脚本见 [scripts README](scripts/README.md)，其默认帧号为 1，必须显式传入需要的帧号。

### Linux / Pitt CRC

主流程建议单节点、单任务 **32 CPU / 160G / 12 小时**；已有 float32 梯度的 QPower 建议 **16 CPU / 96G / 6 小时**。192G 是额外余量，并非最低要求；128G 尚未实测。当前 16 CPU / 64 GB / 3 小时可部署环境，但放不下约 84.09 GiB 的主共享 RAM 缓存。walltime 为申请建议，不是已测完成时间。

新 allocation 中在任何科学 Python 命令前设置：

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
```

已有完整速度输入时，主流程只做本地验证与五尺度计算：

```bash
"$PYTHON" -m jhtdb_pipeline validate-input --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -u -m jhtdb_pipeline process-batch --time-index "$TIME_INDEX" --config "$CONFIG"
```

首次下载、FD4、Slurm 申请和后处理的完整命令见 [Linux 资源方案](docs/linux_crc_run.md)。配置为 FFT 24 worker、压缩 4 线程、slab 16；顺序运行两个 pipeline。使用原有 CLI，没有额外 Linux Python 入口或运行脚本。

## 部署完成后：压力 / QPower pipeline

`deploy.py --stage all` 会安装或复用环境、检查、在线 smoke、下载速度与压力、保存本地周期 FD4 梯度并运行 QPower；**不运行主 pipeline 的多 sigma 滤波与能量传输计算**。QPower 全域 float32 输入加载就约 24 GiB，另需统计内存，24 GB Mac 应只下载，再迁移至足够内存的机器分析。

Windows / PowerShell，沿用首次部署的数据和 token 路径：

```powershell
$DataRoot = '.local'
$TokenPath = Join-Path $HOME '.secrets\jhtdb_token'
py -3 deploy.py --stage all --skip-install --data-root $DataRoot --token-file $TokenPath
```

macOS，以下全流程仅适用于内存足够的机器：

```bash
python3 deploy.py --stage all --skip-install --data-root .local --token-file "$HOME/.secrets/jhtdb_token"
```

只有下载时将 `all` 改为 `download`；已有完整速度和压力时改为 `qpower`。完整选项、输出位置与后台运行见 [部署手册](docs/deployment.md)。

Pitt CRC 使用专用 YAML/JSON 保持 `/ix` 与 `/vast` 分工；沿用上面的 Linux shell 变量：

```bash
# 已有压力时计算 FD4；已有完整梯度可跳过这一条
"$PYTHON" -m jhtdb_pipeline.pressure_local --stage gradient --block-size 64 \
  --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m qpower_analysis.qpower_analysis --config "$QCONFIG" --preflight-only &&
"$PYTHON" -u -m qpower_analysis.qpower_analysis --config "$QCONFIG"
```

CRC JSON 默认第 1 帧，换帧须同步修改 frame、time 和输入路径，不能只修改 `TIME_INDEX`。下载命令及顺序 I/O 方案见 [Linux 资源方案](docs/linux_crc_run.md)。

## 两个 pipeline

| 目录 | 功能与独立手册 |
|---|---|
| [主功能](src/jhtdb_pipeline/README.md) | 下载、滤波、速度梯度、能量传输、QA 与 GUI |
| [qpower_analysis](qpower_analysis/README.md) | 压力功率、事件重叠、条件尾部/分位带、角度统计 |

子项目专用脚本、测试和结果存于各自目录；共享下载、谱运算、正式结果和 GUI 接口在 `src/jhtdb_pipeline`。科学数组不内嵌文档；原始结果与运行 provenance 保留在输出目录。存储的 `pi=τ:S`：负值为 forward，正值为 backscatter；LES 记号取其负值。
