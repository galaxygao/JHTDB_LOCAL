# JHTDB 全周期域计算与湍流统计

本项目下载 `isotropic1024coarse` 的完整 `1024³` 速度场，在 `[0,2π)³` 周期域上进行 Gaussian / smooth-sharp 谱滤波、速度梯度、能量传输和 QA，并提供只读 Streamlit GUI。压力下载及 FD4 梯度用于独立 QPower 分析。

当前正式结果格式为 **v9，全域计算、向量场步长 2 存储**。共享原始梯度、滤波速度和滤波梯度保存原网格 `[::2,::2,::2]` 的 `512³` 点；原始速度输入及所有标量场保留完整 `1024³`。本文全部命令从项目根目录执行。命令直接写出配置文件、数据目录和帧号；先激活对应虚拟环境，再使用 `python`。每条命令单独执行，确认成功后再执行下一条；任一步报错时先处理错误。

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

### 1. 按系统创建、激活并安装环境

首次安装时先用系统 Python 创建虚拟环境，再激活环境并运行部署。已有对应环境时跳过创建命令。Windows 使用 `Activate.ps1` 激活；macOS/Linux 使用 `source` 激活。

Windows / PowerShell：先进入你的项目目录。`.local` 是项目内的数据目录，也可将命令中的 `.local` 直接替换为有足够空间的绝对路径。

```powershell
py -3 -m venv .venv-windows
.\.venv-windows\Scripts\Activate.ps1
python deploy.py --stage setup --data-root .local --token-file "$HOME\.secrets\jhtdb_token"
```

macOS / zsh 或 bash：先进入你的项目目录。下面默认数据目录与 macOS 配置中的 `.local` 一致。

```bash
python3 -m venv .venv-mac
source .venv-mac/bin/activate
python deploy.py --stage setup --data-root .local --token-file ~/.secrets/jhtdb_token
```

Linux / Pitt CRC：环境入口位于项目的 `.venv-linux`，数据根目录使用持久存储。

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
python3 -m venv .venv-linux
source .venv-linux/bin/activate
python deploy.py --stage setup --data-root /ix/lfang/persistent --token-file ~/.secrets/jhtdb_token
```

通用 Linux 可直接替换命令中 `--data-root` 后的目录，并准备匹配本机资源的主配置。`--data-root` 不改变虚拟环境位置；CRC 已有 `.venv-linux` 若是指向持久目录的符号链接，跳过创建命令，激活并复用已有环境。不要将永久环境建在 job 的临时 scratch 中。

<a id="token-file"></a>

### 2. 首次保存 token 文件

已有有效文件时跳过。这里保存你已有的 **JHTDB token**；不涉及 SSH token。文件内容不写进命令历史或 YAML。首次安装时指定的 token 路径可以暂时不存在。

下面的命令会提示 `JHTDB token:`。在提示后粘贴 token 并按回车，输入过程不显示字符；输入完成后自动创建目录和 token 文件。macOS/Linux 文件权限设为 `600`，只有当前用户可读写。输入为空时停止，不创建或覆盖文件。此步骤需单独执行，`deploy.py` 不会自动询问 token。

Windows / PowerShell：

```powershell
.\.venv-windows\Scripts\Activate.ps1
$Secret = Read-Host 'JHTDB token' -AsSecureString
$TokenValue = [System.Net.NetworkCredential]::new('', $Secret).Password.Trim()
if ([string]::IsNullOrWhiteSpace($TokenValue)) { throw '输入为空，未修改 token 文件' }
New-Item -ItemType Directory -Force -Path "$HOME\.secrets"
[IO.File]::WriteAllText("$HOME\.secrets\jhtdb_token", $TokenValue + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
Remove-Variable TokenValue, Secret
Remove-Item Env:JHTDB_TOKEN -ErrorAction SilentlyContinue
```

文件自动保存到用户主目录的 `.secrets\jhtdb_token`，没有扩展名。

macOS：

```bash
source .venv-mac/bin/activate
python - <<'PY'
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

Linux / Pitt CRC：

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
source .venv-linux/bin/activate
python - <<'PY'
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

macOS/Linux 文件自动保存到 `~/.secrets/jhtdb_token`。token 只需录入一次，关闭终端或结束 Slurm job 后文件仍然保留；更新 token 时重新执行录入步骤。CLI 优先读取非空 `JHTDB_TOKEN`，其次读取 YAML 的 `auth.token_file`；上面的清除环境变量命令让后续使用文件。自定义 token 位置时，录入路径、`--token-file` 和实际运行 YAML 的 `auth.token_file` 必须一致。macOS/Linux 会拒绝组或其他用户具有权限的 token 文件。

### 3. 确认储存路径，再做本地检查

部署完成后，确认并修改实际运行使用的 YAML。`deploy.py` 每次运行都会从 `configs/pipeline.yaml` 重新生成配置：上述 Windows/macOS 命令生成 `.local/pipeline.yaml`，上述 CRC 命令生成 `/ix/lfang/persistent/pipeline.yaml`。它只替换路径和 token 文件位置，不会自动采用 macOS 的磁盘 FFT 参数或 CRC 的资源配置。

三个系统都不需要复制或重命名 YAML。Windows 直接修改并使用 deploy 生成的 `.local/pipeline.yaml`；macOS 直接修改并使用现有的 `configs/pipeline.macos.yaml`；CRC 直接修改并使用现有的 `configs/pipeline.linux.crc.yaml`。**再次运行 deploy 会覆盖生成文件中的手动修改，Windows 需要重新确认这些设置；现有的 macOS 和 CRC 配置文件不会被 deploy 覆盖。**

CRC 的 `platform` 路径如下；需要换目录时，直接修改 `configs/pipeline.linux.crc.yaml` 中对应的值：

```yaml
platform:
  state_root: /ix/lfang/persistent/state
  run_root: /vast/lfang/xig134/JHTDB_CRC/runs
  result_root: /ix/lfang/xig134/JHTDB_CRC/results
```

`state_root` 保存原始输入和状态，`run_root` 保存计算临时文件，`result_root` 保存正式结果。deploy 以 `/ix/lfang/persistent` 为数据目录时，生成文件里的三个路径分别是 `/ix/lfang/persistent/state`、`/ix/lfang/persistent/runs`、`/ix/lfang/persistent/results`；运行时显式指定 CRC YAML 才会使用上面的 `/vast` 工作区。`cleanup_scratch_on_success: true` 会在计算成功后清理对应尺度的临时工作区。

| 内容 | Windows/macOS 默认位置 | Pitt CRC 本文方案 |
|---|---|---|
| Python 环境 | `.venv-windows/` / `.venv-mac/` | `.venv-linux/`（可为持久目录链接） |
| token 文件 | 用户主目录下 `.secrets/jhtdb_token` | `$HOME/.secrets/jhtdb_token` |
| deploy 生成的 YAML | `.local/pipeline.yaml` | `/ix/lfang/persistent/pipeline.yaml` |
| 原始输入、catalog、manifest | `.local/state/` | `/ix/lfang/persistent/state/` |
| 主计算工作文件 | `.local/runs/` | `/vast/lfang/xig134/JHTDB_CRC/runs/` |
| 主计算正式结果 | `.local/results/` | `/ix/lfang/xig134/JHTDB_CRC/results/` |
| QPower 输出 | `qpower_analysis/output/`（使用 deploy 时） | `/ix/lfang/xig134/JHTDB_CRC/qpower/`（使用 CRC JSON 时） |

Windows/macOS 使用其他 `--data-root` 时，生成配置的 state/runs/results 随之改变；**QPower 的 deploy 输出仍在项目 `qpower_analysis/output/`**。macOS 主流程的 `configs/pipeline.macos.yaml` 默认指向 `.local`，换盘时直接修改其中的三个 `platform` 路径。CRC 必须显式使用 `configs/pipeline.linux.crc.yaml` 和 `qpower_analysis/config.linux.crc.json`，才能采用上表的 `/vast` 工作区和独立结果目录；只给 deploy 传 `/ix/lfang/persistent` 不会启用这些路径。

Windows：

```powershell
.\.venv-windows\Scripts\Activate.ps1
python -m jhtdb_pipeline auth status --config .local/pipeline.yaml
python -m jhtdb_pipeline doctor --time-index 1 --config .local/pipeline.yaml
```

macOS：

```bash
source .venv-mac/bin/activate
python -m jhtdb_pipeline auth status --config configs/pipeline.macos.yaml
python -m jhtdb_pipeline doctor --time-index 1 --config configs/pipeline.macos.yaml
```

Linux / Pitt CRC：先按下文 Linux 主流程设置线程与缓存环境变量，再做本地检查。

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
source .venv-linux/bin/activate
python -m jhtdb_pipeline auth status --config configs/pipeline.linux.crc.yaml
python -m jhtdb_pipeline doctor --time-index 1 --config configs/pipeline.linux.crc.yaml
```

这些检查不下载科学数据；`doctor` 会检查依赖、路径可写性等。`auth status` 只报告 token 来源，不能证明在线认证有效，后续 `smoke` 才会请求服务。

### 4. 下次打开终端或新 Slurm job

进入同一个项目目录，激活已有环境即可。环境和 token 文件仍在，不需要重新创建环境或录入 token。Linux CRC 的线程与缓存环境变量需要在新终端或新 job 中重新设置，见下文 Linux 主流程。

| 系统 | 激活命令 | 本文运行使用的主配置 |
|---|---|---|
| Windows | `.\.venv-windows\Scripts\Activate.ps1` | `.local/pipeline.yaml` |
| macOS | `source .venv-mac/bin/activate` | `configs/pipeline.macos.yaml` |
| Pitt CRC Linux | `source .venv-linux/bin/activate` | `configs/pipeline.linux.crc.yaml` |

激活后统一使用 `python`；退出用 `deactivate`。旧 Windows 包装脚本使用 `.venv`，与 deploy 创建的 `.venv-windows` 不同；下面使用激活后的环境执行命令。

已有环境再调用 deploy 时加 `--skip-install`，并保持相同 `--data-root`、`--token-file`；需要更新依赖时重新执行 `--stage setup`，复用原环境进行安装。[部署细节与分阶段命令](docs/deployment.md)。

## 部署完成后：主 pipeline

以下命令会下载或计算，按资源条件选择执行。完整速度输入约 12 GiB，五尺度结果加共享梯度及输入未压缩约 126.5 GiB，另需 FFT 缓存、工作区与安全余量，以 `plan`/预检为准。默认 sigma 为 `10 15 30 55 75`，smooth-sharp 的 `alpha=w/k_c=0.1171875`，`process-batch` 串行复用共享缓存。

### Windows / PowerShell

部署使用默认 `.local` 时：

```powershell
.\.venv-windows\Scripts\Activate.ps1
python -m jhtdb_pipeline doctor --time-index 1 --config .local/pipeline.yaml
python -m jhtdb_pipeline plan --time-index 1 --config .local/pipeline.yaml
python -m jhtdb_pipeline smoke --time-index 1 --config .local/pipeline.yaml
python -m jhtdb_pipeline cache --time-index 1 --config .local/pipeline.yaml
python -m jhtdb_pipeline validate-input --time-index 1 --config .local/pipeline.yaml
python -m jhtdb_pipeline process-batch --time-index 1 --config .local/pipeline.yaml
python -m jhtdb_pipeline status --config .local/pipeline.yaml
python -m jhtdb_pipeline gui --config .local/pipeline.yaml --port 8501
```

Windows 生成配置沿用 RAM FFT / 16 FFT worker / 8 压缩线程。RAM FFT 的共享缓存本身约 84.09 GiB，完整峰值更高。内存不足时先调整 `.local/pipeline.yaml`，不能只减少线程。自定义数据目录时，将每条命令中 `--config` 后的文件路径直接替换为该数据目录中 deploy 生成的 `pipeline.yaml` 路径。

### macOS / zsh 或 bash

24 GB Mac 使用已有磁盘 FFT 配置，完整域峰值尚未实测；空间规划见 [macOS 资源方案](docs/macos_main_pipeline_run.md)。

```bash
source .venv-mac/bin/activate
python -m jhtdb_pipeline doctor --time-index 500 --config configs/pipeline.macos.yaml
python -m jhtdb_pipeline plan --time-index 500 --config configs/pipeline.macos.yaml
python -m jhtdb_pipeline smoke --time-index 500 --config configs/pipeline.macos.yaml
python -m jhtdb_pipeline cache --time-index 500 --config configs/pipeline.macos.yaml
python -m jhtdb_pipeline validate-input --time-index 500 --config configs/pipeline.macos.yaml
python -u -m jhtdb_pipeline process-batch --time-index 500 --config configs/pipeline.macos.yaml
python -m jhtdb_pipeline status --config configs/pipeline.macos.yaml
python -m jhtdb_pipeline gui --config configs/pipeline.macos.yaml --port 8501
```

换帧时修改每条命令的 `--time-index 500`；使用其他数据盘时修改 `configs/pipeline.macos.yaml` 的三个 `platform` 路径。计算期间应保持机器唤醒。GUI 地址 `http://127.0.0.1:8501`。可选包装脚本见 [scripts README](scripts/README.md)，其默认帧号为 1，必须显式传入需要的帧号。

### Linux / Pitt CRC

主流程建议单节点、单任务 **32 CPU / 160G / 12 小时**；已有 float32 梯度的 QPower 建议 **16 CPU / 96G / 6 小时**。192G 是额外余量，并非最低要求；128G 尚未实测。当前 16 CPU / 64 GB / 3 小时可部署环境，但放不下约 84.09 GiB 的主共享 RAM 缓存。walltime 为申请建议，不是已测完成时间。

新 allocation 中在任何科学 Python 命令前设置：

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
source .venv-linux/bin/activate
export OMP_NUM_THREADS=1 OMP_THREAD_LIMIT=1 OMP_DYNAMIC=FALSE
export OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MKL_DYNAMIC=FALSE
export BLIS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1 NUMEXPR_MAX_THREADS=1
export TMPDIR=/vast/lfang/xig134/JHTDB_CRC/tmp
export XDG_CACHE_HOME=/ix/lfang/xig134/JHTDB_CRC/cache
export MPLCONFIGDIR=/ix/lfang/xig134/JHTDB_CRC/cache/matplotlib
mkdir -p /vast/lfang/xig134/JHTDB_CRC/tmp
mkdir -p /ix/lfang/xig134/JHTDB_CRC/cache
mkdir -p /ix/lfang/xig134/JHTDB_CRC/cache/matplotlib
```

首次运行或速度缓存尚未完成时，依次检查配置与空间、执行在线 smoke，并下载或续传完整速度缓存：

```bash
source .venv-linux/bin/activate
python -m jhtdb_pipeline doctor --time-index 1 --config configs/pipeline.linux.crc.yaml
python -m jhtdb_pipeline plan --time-index 1 --config configs/pipeline.linux.crc.yaml
python -m jhtdb_pipeline smoke --time-index 1 --config configs/pipeline.linux.crc.yaml
python -m jhtdb_pipeline cache --time-index 1 --config configs/pipeline.linux.crc.yaml
```

`cache` 会下载缺失块、校验已有块并复用有效缓存。确认命令成功后，再执行输入验证与五尺度计算：

```bash
python -m jhtdb_pipeline validate-input --time-index 1 --config configs/pipeline.linux.crc.yaml
python -u -m jhtdb_pipeline process-batch --time-index 1 --config configs/pipeline.linux.crc.yaml
python -m jhtdb_pipeline status --config configs/pipeline.linux.crc.yaml
```

压力下载、FD4、Slurm 申请和后处理的完整命令见 [Linux 资源方案](docs/linux_crc_run.md)。配置为 FFT 24 worker、压缩 4 线程、slab 16；顺序运行两个 pipeline。使用原有 CLI，没有额外 Linux Python 入口或运行脚本。

## 部署完成后：压力 / QPower pipeline

`deploy.py --stage all` 会安装或复用环境、检查、在线 smoke、下载速度与压力、保存本地周期 FD4 梯度并运行 QPower；**不运行主 pipeline 的多 sigma 滤波与能量传输计算**。QPower 全域 float32 输入加载就约 24 GiB，另需统计内存，24 GB Mac 应只下载，再迁移至足够内存的机器分析。

Windows / PowerShell，沿用首次部署的数据和 token 路径：

```powershell
.\.venv-windows\Scripts\Activate.ps1
python deploy.py --stage all --skip-install --data-root .local --token-file "$HOME\.secrets\jhtdb_token"
```

macOS，以下全流程仅适用于内存足够的机器：

```bash
source .venv-mac/bin/activate
python deploy.py --stage all --skip-install --data-root .local --token-file ~/.secrets/jhtdb_token
```

只有下载时将 `all` 改为 `download`；已有完整速度和压力时改为 `qpower`。完整选项、输出位置与后台运行见 [部署手册](docs/deployment.md)。

Pitt CRC 使用专用 YAML/JSON 保持 `/ix` 与 `/vast` 分工；先完成上面的 Linux 线程与缓存设置。已有压力时计算 FD4；已有完整梯度可跳过 FD4 命令：

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
source .venv-linux/bin/activate
python -m jhtdb_pipeline.pressure_local --stage gradient --block-size 64 --time-index 1 --config configs/pipeline.linux.crc.yaml
python -m qpower_analysis.qpower_analysis --config qpower_analysis/config.linux.crc.json --preflight-only
python -u -m qpower_analysis.qpower_analysis --config qpower_analysis/config.linux.crc.json
```

CRC JSON 默认第 1 帧，换帧须同时修改命令的 `--time-index 1` 和 `qpower_analysis/config.linux.crc.json` 里的 frame、time 及输入路径。下载命令及顺序 I/O 方案见 [Linux 资源方案](docs/linux_crc_run.md)。

## 两个 pipeline

| 目录 | 功能与独立手册 |
|---|---|
| [主功能](src/jhtdb_pipeline/README.md) | 下载、滤波、速度梯度、能量传输、QA 与 GUI |
| [qpower_analysis](qpower_analysis/README.md) | 压力功率、事件重叠、条件尾部/分位带、角度统计 |

子项目专用脚本、测试和结果存于各自目录；共享下载、谱运算、正式结果和 GUI 接口在 `src/jhtdb_pipeline`。科学数组不内嵌文档；原始结果与运行 provenance 保留在输出目录。存储的 `pi=τ:S`：负值为 forward，正值为 backscatter；LES 记号取其负值。
