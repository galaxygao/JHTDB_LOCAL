# 操作手册：配置、GUI 与端到端命令

本项目在 Windows / macOS / Linux 下载 JHTDB `isotropic1024coarse` 的完整 `1024³` 单帧速度场，
在完整周期域上完成谱滤波、谱导数、能量传输量、QA 和多 sigma 统计，并用只读
Streamlit GUI 查看正式结果。

通用模板 `configs/pipeline.yaml` 使用比例宽度 smooth-sharp 滤波：

- `sigma = [10, 15, 30, 55, 75]`；
- `alpha = w/k_c = 0.1171875`；
- 16 个 FFT worker、8 个压缩线程；
- 模板路径位于 `C:/Xingqun_Gao/persistent`；deploy 生成配置时改为所选 data-root。

下面 Windows CLI 示例使用 deploy 创建的 `.venv-windows` 和默认 `.local/pipeline.yaml`。
使用其他数据根目录或独立本机 YAML 时替换配置路径；macOS/CRC 使用各自专用配置。

## 文档与代码位置

[根 README](../README.md) 负责平台安装与端到端导航；本手册保留完整配置与操作细节。实现细节放在功能对应目录：

| 功能 | 代码与说明 |
|---|---|
| 下载、验证、滤波、物理量、QA、结果 schema | [`src/jhtdb_pipeline/README.md`](../src/jhtdb_pipeline/README.md) |
| 多 sigma 一键脚本 | [`scripts/README.md`](../scripts/README.md) |

## 环境要求

- Python 3.9 或更新版本；
- JHTDB 个人 token；
- RAM 共享缓存本身约 84.09 GiB，另有 FFT 临时数组、QA 和工作文件驻留页；完整域峰值尚未实测；
- CRC 的 32 CPU / 160G 推荐及估算依据见 [Linux 方案](linux_crc_run.md)，192G 不是最低要求；24 GB Mac 使用下述 `memmap` 配置；
- 完整输入缓存约 12 GiB，单个 sigma 正式结果约 22 GiB，另有每帧共享原始梯度约 4.5 GiB；
- 默认要求正式盘和临时盘各保留至少 24 GiB 安全余量。

不要同时启动多个 sigma 计算进程。`process-batch` 会在一个进程中共享原始梯度和
FFT 频谱，并通过生产锁阻止相互覆盖。

## 安装

三平台的完整首次安装、token 文件和环境复用步骤统一见
[根 README](../README.md#first-deployment)。Windows 仅安装环境的命令，从项目根目录运行：

```powershell
py -3 deploy.py --stage setup --data-root .local --token-file (Join-Path $HOME '.secrets\jhtdb_token')
```

安装生成 `.venv-windows` 与 `.local/pipeline.yaml`，不下载或计算，也不录入 token 内容。
后续直接使用 `.\.venv-windows\Scripts\python.exe`，无需激活或修改执行策略。
旧 `bootstrap_local.ps1` 会创建另一环境 `.venv` 并运行测试，属于旧脚本流程，
不作为这里首次部署的必需步骤。环境安装一次后持续复用。

## macOS：10 核 / 24 GB 配置

先按根 README 部署环境与 token，再从项目根目录运行，使用
[`configs/pipeline.macos.yaml`](../configs/pipeline.macos.yaml)。以下步骤包含在线下载和计算，
逐条确认成功，失败后停止：

```bash
.venv-mac/bin/python -m jhtdb_pipeline doctor --time-index 1 --config configs/pipeline.macos.yaml
.venv-mac/bin/python -m jhtdb_pipeline smoke --time-index 1 --config configs/pipeline.macos.yaml
.venv-mac/bin/python -m jhtdb_pipeline cache --time-index 1 --config configs/pipeline.macos.yaml
.venv-mac/bin/python -m jhtdb_pipeline validate-input --time-index 1 --config configs/pipeline.macos.yaml
bash scripts/run_main_macos.sh
```

Mac 参数为 `fft_cache_mode=memmap`、`fft_workers=10`、`compression_threads=6`、
`fft_slab_width=16`。脚本执行一次 `process-batch`，共享九分量原始梯度和十二个源频谱，
逐 sigma 复用；输出直接显示在 Terminal。磁盘 FFT 按完整坐标轴分 slab 变换，不减少格点。
线程数来自本机短测；完整域总进程峰值内存尚未实测，详细限制见
[`macOS 说明`](../docs/macos_main_pipeline_run.md)。不要在这台 Mac 使用 Windows 的 RAM 配置。

五尺度永久数据未压缩约 126.5 GiB（含输入），共享磁盘缓存约 84.09 GiB；
还需工作区与安全余量。预检按未压缩大小检查所有待算尺度及同盘共享空间。

```bash
STREAMLIT_SERVER_HEADLESS=true .venv-mac/bin/python -m jhtdb_pipeline gui \
  --config configs/pipeline.macos.yaml --port 8501
```

新结果格式 v9：原始速度输入和所有标量场完整保存 `1024³`；共享原始梯度、每尺度滤波速度/梯度每轴步长 2，保存覆盖全域的 `512³` 点。所有物理计算、统计和 QA 均使用完整 `1024³`。
原始速度和原始梯度每帧各存一份，通过 `shared_refs.json` 共用。读取器支持 v7/v8/v9；新计算写 v9，使用独立结果路径，见[当前数据格式](data_versions.md)。

## JHTDB token

长期使用用户主目录下 `.secrets/jhtdb_token`，隐藏录入步骤见
[根 README](../README.md#token-file)。deploy 首次安装时显式指定该文件；实际运行 YAML 的
`auth.token_file` 也必须指向同一个位置。非空环境变量 `JHTDB_TOKEN` 优先于文件。
验证配置：

```powershell
.\.venv-windows\Scripts\python.exe -m jhtdb_pipeline auth status `
  --config .local\pipeline.yaml
```

输出必须包含 `"configured": true`。token 不要写入 Git 项目或命令日志。

## 配置文件

配置项说明以 [`configs/pipeline.yaml`](../configs/pipeline.yaml) 模板为参照，文件内有注释。
新部署的 Windows 默认使用 `.local/pipeline.yaml`，macOS 使用 `configs/pipeline.macos.yaml`，
CRC 使用 `configs/pipeline.linux.crc.yaml`。deploy 每次运行都会覆盖其生成 YAML，
持久保存资源或路径调整时另存本机独立 YAML，然后用 `--config` 指定。
CLI 参数只覆盖本次命令，不修改 YAML；未传 CLI 参数时使用 YAML 值。

### 配置项说明

| 配置项 | 当前值/可选值 | 用途与约束 |
|---|---|---|
| `dataset` | `isotropic1024coarse` | 当前实现固定数据集 |
| `variable` | `velocity` | 当前只下载速度 |
| `grid_shape` | `[1024,1024,1024]` | 完整网格，顺序 `[x,y,z]` |
| `domain_length` | `2π` | 三个周期方向的长度 |
| `stored_time_step` | `0.002` | `physical_time=(time_index-1)×0.002` |
| `platform.state_root` | 路径 | catalog、输入缓存、manifest、QA、锁 |
| `platform.run_root` | 路径 | FFT/memmap 临时工作区 |
| `platform.result_root` | 路径 | 正式结果和 batch manifest |
| `auth.token_file` | 路径或空 | token 文件；可由 `JHTDB_TOKEN` 覆盖 |
| `jhtdb.request_shape` | `[256,256,128]` | 每个请求 96 MiB，必须整除全域且不超过 100 MiB |
| `jhtdb.tile_shape` | `[128,128,128]` | checksum tile，当前格式固定 |
| `jhtdb.retries` | 正整数 | 单请求总尝试次数 |
| `jhtdb.backoff_seconds` | 非负秒数 | 失败后的指数退避基数 |
| `jhtdb.request_cooldown_seconds` | 非负秒数 | 成功请求之间的等待时间 |
| `storage.compression_level` | `0..9` | Blosc 压缩等级 |
| `storage.compression_threads` | 正整数 | 压缩线程数 |
| `storage.*_safety_reserve_gib` | 非负 GiB | 开始写入前强制保留的磁盘余量 |
| `validation.divergence_*` | 正数 | 原始及滤波速度散度阈值 |
| `validation.energy_identity_relative_rms_max` | 正数 | 能量等式相对 RMS 残差阈值 |
| `validation.s_bar_vs_pi_net_max` | 正数 | 周期域净 `S_bar` 检查阈值 |
| `validation.weak_asymmetry_closure_relative_max` | 正数 | Pi 正负分拆 closure 阈值 |
| `physics.sigma_grid` | 正数或唯一正数列表 | 默认处理的滤波尺度 |
| `physics.filter_type` | `gaussian` / `smooth_sharp` | 滤波器类型 |
| `physics.sharp_edge_width_fraction` | 正数 | smooth-sharp 的唯一宽度参数 `alpha=w/k_c` |
| `physics.fft_cache_mode` | `memory` / `memmap` | 共享梯度和频谱使用 RAM 或磁盘映射；Mac 配置为 `memmap` |
| `physics.fft_workers` | 正整数 | FFT worker 数 |
| `physics.fft_slab_width` | 正整数 | 流式处理 slab 宽度 |
| `physics.cleanup_scratch_on_success` | `true/false` | 成功提交后是否清理该 sigma 工作区 |

对于 `smooth_sharp`，所有 sigma 使用相同相对边缘宽度：

```text
alpha = sharp_edge_width_fraction = w/k_c
```

## GUI：启动、选择与实际展示量

启动只读 GUI：

```powershell
.\.venv-windows\Scripts\python.exe -m jhtdb_pipeline gui `
  --config .local\pipeline.yaml --port 8501
```

浏览器访问 `http://127.0.0.1:8501`。GUI 只发现 `result_root` 中带 `COMPLETE` 的正式结果，
启动时仅读取小型 manifest。侧栏依次选择时间、filter type、sigma 和平滑参数，点击
“确认并加载”后才打开 Zarr；任一选择变化后都要重新确认。同参数同时存在新旧结果时优先显示最高格式版本。

### GUI 页面

| 页面 | 展示量 | 范围与控制 |
|---|---|---|
| 速度对比 | 原始 `velocity_i` 与滤波 `velocity_bar_i` | 全域步长 2 `512³`；选择 `ux/uy/uz`、切片法向和 index；两图共用对称色标 |
| 梯度对比 | `gradient[i,j]=∂_j u_i` 与 `gradient_bar[i,j]=∂_j velocity_bar_i` | 全域步长 2 `512³`；选择速度分量、求导方向、线性/SymLog 色标及 90–100% 色标分位 |
| Work | `W_full`、`W_resolved`、`ΔW=W_full-W_resolved` | 完整 `1024³`；选择切片法向和 index |
| Π 与 S̄ | `Π=τ_ij∂_j velocity_bar_i`、`S̄=∂_j(velocity_bar_i τ_ij)`、能量等式残差 | 完整 `1024³`；Pi 与 S-bar 共用 99% 对称色标；显示 decomposition QA |
| Weak asymmetry | `mean(pi)`、`rms(pi)`、`mean/rms`、相对 p99/max、正负贡献与体积分数 | 全域 Pi 正负分拆与 closure 报告 |
| 全域 S̄ QA | 能量等式相对 RMS 残差、`|ΣS̄|/|ΣΠ|`、`ΣS̄/ΣΠ/ΣW_res/ΣW_full` | 同时可展开 `manifest.json`、`qa.json`、`divergence.json`、`COMPLETE` |

连续场切片发送给浏览器时最多为 `512×512` 像素；若原切片为 `1024×1024`，只对显示做
stride，下游统计和磁盘结果仍使用全部格点。坐标轴保留源数组 index。

符号约定必须注意：项目保存 `pi=τ:S`，所以 `pi<0` 表示 forward cascade，
`pi>0` 表示 backscatter；常见 LES 记号 `Pi_LES=-pi`。

## 当前比例 smooth-sharp 一键全流程

脚本使用 single-frame 完成多尺度主计算、QA 和提交，然后打印状态。

```powershell
.\scripts\run_smooth_sharp_full_pipeline.ps1
```

该旧 PowerShell 包装脚本固定使用 `.venv` 和 `configs/pipeline.yaml`，
不自动复用 deploy 的 `.venv-windows`。新部署使用下面的直接 CLI 命令；
旧脚本参数与行为见 [`scripts/README.md`](../scripts/README.md)。

## 自定义参数：完整端到端 CLI

下面示例演示自定义 `time-index=7`、四个 sigma 和比例 smooth-sharp。先设置变量，减少
重复输入：

```powershell
$Python = ".\.venv-windows\Scripts\python.exe"
$Config = ".local\pipeline.yaml"
$TimeIndex = 7
$Sigmas = @(8, 16, 32, 64)
$Alpha = 0.10
```

### 1. 环境与资源前检

```powershell
& $Python -m jhtdb_pipeline auth status --config $Config
& $Python -m jhtdb_pipeline doctor --time-index $TimeIndex --config $Config
& $Python -m jhtdb_pipeline plan --time-index $TimeIndex --config $Config
```

### 2. 小型在线 smoke

```powershell
& $Python -m jhtdb_pipeline smoke `
  --time-index $TimeIndex --config $Config
```

### 3. 下载并验证完整输入

```powershell
& $Python -m jhtdb_pipeline cache `
  --time-index $TimeIndex --config $Config
& $Python -m jhtdb_pipeline validate-input `
  --time-index $TimeIndex --config $Config
```

下载严格串行。中断后重新运行同一 `cache` 命令，会校验并复用已有 tile。

### 4. 多 sigma 完整计算

```powershell
& $Python -m jhtdb_pipeline process-batch `
  --time-index $TimeIndex `
  --sigma-grids @Sigmas `
  --filter-type smooth_sharp `
  --sharp-edge-width-fraction $Alpha `
  --config $Config
```

该命令计算并正式提交 `velocity_bar`、`gradient_bar`、`work_full`、`work_resolved`、
`pi`、`s_bar`，并生成 divergence、能量等式、weak-asymmetry 和 S-bar QA。
已完成且参数匹配的 sigma 会复用。

也可以用一条命令执行 doctor、cache、validate 和 process-batch：

```powershell
& $Python -m jhtdb_pipeline single-frame `
  --time-index $TimeIndex `
  --sigma-grids @Sigmas `
  --filter-type smooth_sharp `
  --sharp-edge-width-fraction $Alpha `
  --config $Config
```

`single-frame` 不代替首次在线 `smoke`，正式运行前仍建议单独执行 smoke。

### 5. 状态与 GUI

```powershell
& $Python -m jhtdb_pipeline status --config $Config
& $Python -m jhtdb_pipeline gui --config $Config --port 8501
```

## Gaussian 滤波

Gaussian 多 sigma：

```powershell
.\.venv-windows\Scripts\python.exe -m jhtdb_pipeline process-batch `
  --time-index 1 --sigma-grids 2 5 10 20 40 100 `
  --filter-type gaussian --config .local\pipeline.yaml
```

只计算单个 sigma 时可用 `process-full`，随后必须执行同参数的 `finalize-result`：

```powershell
.\.venv-windows\Scripts\python.exe -m jhtdb_pipeline process-full `
  --time-index 1 --sigma-grid 20 --filter-type gaussian `
  --config .local\pipeline.yaml
.\.venv-windows\Scripts\python.exe -m jhtdb_pipeline finalize-result `
  --time-index 1 --sigma-grid 20 --filter-type gaussian `
  --config .local\pipeline.yaml
```

## 中断恢复

重新打开 PowerShell 后无需重新安装或重新下载：

```powershell
cd D:\Xingqun_Gao\JHTDB_LOCAL
# token 文件仍可复用，不需要重新录入。
.\.venv-windows\Scripts\python.exe -m jhtdb_pipeline auth status `
  --config .local\pipeline.yaml
.\.venv-windows\Scripts\python.exe -m jhtdb_pipeline status `
  --config .local\pipeline.yaml
```

然后重新运行被中断的命令。下载、正式结果 都带有可验证的续跑信息；已完成
部分会复用。不要手工移动 `.staging`、修改 `COMPLETE`，也不要并行启动两个生产计算。
