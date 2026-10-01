# JHTDB 本地全周期域流水线

本项目在 Windows 本地下载 JHTDB `isotropic1024coarse` 的完整 `1024³` 单帧速度场，
在完整周期域上完成谱滤波、谱导数、能量传输量、QA 和多 sigma 统计，并用只读
Streamlit GUI 查看正式结果。

当前生产配置使用比例宽度 smooth-sharp 滤波：

- `sigma = [10, 15, 30, 55, 75]`；
- `alpha = w/k_c = 0.1171875`；
- 16 个 FFT worker、8 个压缩线程；
- 正式数据位于 `C:/Xingqun_Gao/persistent`。

## 文档与代码位置

根 README 只负责安装、配置、GUI 和端到端运行。实现细节放在功能对应目录：

| 功能 | 代码与说明 |
|---|---|
| 下载、验证、滤波、物理量、QA、结果 schema | [`src/jhtdb_pipeline/README.md`](src/jhtdb_pipeline/README.md) |
| 多 sigma 一键脚本 | [`scripts/README.md`](scripts/README.md) |
| 16³ block 与 `SijSij` | [`block_statistics/README.md`](block_statistics/README.md) |
| Pi 双正交切片三维图 | [`pi_slices/README.md`](pi_slices/README.md) |
| 全域 Cartesian PDF/scatter | [`scatter/README.md`](scatter/README.md) |
| 一维 Pi PDF 与 log-Pi 检验 | [`pi_pdf/README.md`](pi_pdf/README.md) |
| 各 regime 的 Pi 正反传输 | [`regime_pi/README.md`](regime_pi/README.md) |
| mean Pi/epsilon 平台 | [`flux_plateau/README.md`](flux_plateau/README.md) |

## 环境要求

- Python 3.9 或更新版本；
- JHTDB 个人 token；
- 推荐至少 16 个物理核心和 192 GiB RAM；
- 多 sigma smooth-sharp batch 峰值约 92 GiB RAM，此外要给系统留余量；
- 完整输入缓存约 12 GiB，单个 sigma 正式结果约 23 GiB；
- 默认要求正式盘和临时盘各保留至少 24 GiB 安全余量。

不要同时启动多个 sigma 计算进程。`process-batch` 会在一个进程中共享原始梯度和
FFT 频谱，并通过生产锁阻止相互覆盖。

## 安装

所有命令均在 PowerShell 中从项目根目录运行：

```powershell
cd D:\Xingqun_Gao\JHTDB_LOCAL
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_local.ps1
```

脚本会创建 `.venv`、安装项目和测试依赖、编译源码并运行测试。手动安装的等价命令为：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
```

如果当前 PowerShell 禁止激活脚本，可只为当前进程放开：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

后续示例统一使用 `.\.venv\Scripts\python.exe`，因此并不依赖虚拟环境是否已激活。

## JHTDB token

临时设置，只对当前 PowerShell 窗口有效：

```powershell
$env:JHTDB_TOKEN = "你的个人 JHTDB token"
```

长期方式是在 `configs/pipeline.yaml` 的 `auth.token_file` 指向的文件中只写一行 token。
默认位置是：

```text
C:\Xingqun_Gao\persistent\.secrets\jhtdb_token
```

环境变量的优先级高于 token 文件。验证配置：

```powershell
.\.venv\Scripts\python.exe -m jhtdb_pipeline auth status `
  --config configs\pipeline.yaml
```

输出必须包含 `"configured": true`。token 不要写入 Git 项目或命令日志。

## 配置文件

主配置是 [`configs/pipeline.yaml`](configs/pipeline.yaml)。文件内已为每个选项添加注释。
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
| `validation.cq_partition_relative_max` | 正数 | regime 分区 closure 阈值 |
| `physics.sigma_grid` | 正数或唯一正数列表 | 默认处理的滤波尺度 |
| `physics.filter_type` | `gaussian` / `smooth_sharp` | 滤波器类型 |
| `physics.sharp_edge_width_fraction` | 正数 | smooth-sharp 的唯一宽度参数 `alpha=w/k_c` |
| `physics.crop_start/shape` | `[256,256,256]` / `[512,512,512]` | 永久保存的中心速度与梯度范围，生产配置固定 |
| `physics.epsilon_abs/rel` | 非负数 | regime uncertain 阈值 |
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
.\.venv\Scripts\python.exe -m jhtdb_pipeline gui `
  --config configs\pipeline.yaml --port 8501
```

浏览器访问 `http://127.0.0.1:8501`。GUI 只发现 `result_root` 中带 `COMPLETE` 的正式结果，
启动时仅读取小型 manifest。侧栏依次选择时间、filter type、sigma 和平滑参数，点击
“确认并加载”后才打开 Zarr；任一选择变化后都要重新确认。

### GUI 页面

| 页面 | 展示量 | 范围与控制 |
|---|---|---|
| 速度对比 | 原始 `velocity_i` 与滤波 `velocity_bar_i` | 中心 `512³`；选择 `ux/uy/uz`、切片法向和 index；两图共用对称色标 |
| 梯度对比 | `gradient[i,j]=∂_j u_i` 与 `gradient_bar[i,j]=∂_j velocity_bar_i` | 中心 `512³`；选择速度分量、求导方向、线性/SymLog 色标及 90–100% 色标分位 |
| Work 与 regime | `W_full`、`W_resolved`、`ΔW=W_full-W_resolved`、六分区 regime、全域 occupancy | 完整 `1024³`；选择切片法向和 index |
| Π 与 S̄ | `Π=τ_ij∂_j velocity_bar_i`、`S̄=∂_j(velocity_bar_i τ_ij)`、能量等式残差 | 完整 `1024³`；Pi 与 S-bar 共用 99% 对称色标；显示 decomposition QA |
| Regime 五场统计 | `Π`、`S̄`、`W_full`、`W_resolved`、`ΔW` | 每个 regime 的 `Σ_q field/N`、`Σ_q field/N_q`、格点数、体积分数、全域均值及 closure |
| Weak asymmetry | `mean(pi)`、`rms(pi)`、`mean/rms`、相对 p99/max、正负贡献与体积分数 | 全域报告；若已有 `regime_pi` 输出，还显示每个 regime 内 forward/backscatter 的 mean、fraction、intensity |
| 全域 S̄ QA | 能量等式相对 RMS 残差、`|ΣS̄|/|ΣΠ|`、`ΣS̄/ΣΠ/ΣW_res/ΣW_full` | 同时可展开 `manifest.json`、`qa.json`、`divergence.json`、`COMPLETE` |

连续场切片发送给浏览器时最多为 `512×512` 像素；若原切片为 `1024×1024`，只对显示做
stride，下游统计和磁盘结果仍使用全部格点。坐标轴保留源数组 index。

符号约定必须注意：项目保存 `pi=τ:S`，所以 `pi<0` 表示 forward cascade，
`pi>0` 表示 backscatter；常见 LES 记号 `Pi_LES=-pi`。

“Weak asymmetry”页面中的逐 regime Pi 部分需要先生成独立报告：

```powershell
.\.venv\Scripts\python.exe -m jhtdb_pipeline compute-regime-pi `
  --time-index 1 --sigma-grids 10 15 30 55 75 `
  --filter-type smooth_sharp --sharp-edge-width-fraction 0.1171875 `
  --config configs\pipeline.yaml
```

## 当前比例 smooth-sharp 一键全流程

脚本断点续算五个 sigma、生成逐 regime Pi 统计，再逐 sigma 串行计算 16³ block
`SijSij/W_resolved/W_full/Pi` 和图表：

```powershell
.\scripts\run_smooth_sharp_full_pipeline.ps1
```

强制重算 block 输出：

```powershell
.\scripts\run_smooth_sharp_full_pipeline.ps1 `
  -OverwriteBlockStatistics
```

脚本参数与行为见 [`scripts/README.md`](scripts/README.md)。

## 自定义参数：完整端到端 CLI

下面示例演示自定义 `time-index=7`、四个 sigma 和比例 smooth-sharp。先设置变量，减少
重复输入：

```powershell
$Python = ".\.venv\Scripts\python.exe"
$Config = "configs\pipeline.yaml"
$TimeIndex = 7
$Sigmas = @(8, 16, 32, 64)
$Alpha = 0.10
```

### 1. 只读前检

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
`pi`、`s_bar`、`regime`，并生成 divergence、能量等式、Cq、weak-asymmetry 和 S-bar QA。
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

### 5. GUI 所需的逐 regime Pi 统计

```powershell
& $Python -m jhtdb_pipeline compute-regime-pi `
  --time-index $TimeIndex `
  --sigma-grids @Sigmas `
  --filter-type smooth_sharp `
  --sharp-edge-width-fraction $Alpha `
  --config $Config
```

### 6. 自定义 block 数计算 `SijSij`

例如每轴分 8 块，即 `8³` 个 `128³` block：

```powershell
foreach ($Sigma in $Sigmas) {
  & $Python block_statistics\compute_block_statistics.py `
    --time-index $TimeIndex `
    --sigma-grid $Sigma `
    --filter-type smooth_sharp `
    --sharp-edge-width-fraction $Alpha `
    --blocks-per-axis 8 `
    --output-root block_statistics\output `
    --scratch-root block_statistics\.scratch `
    --config $Config
}
```

`blocks-per-axis` 必须整除 1024。默认 16 表示 `16³` 个 `64³` block。绘图命令和输出
格式见 [`block_statistics/README.md`](block_statistics/README.md)。

### 7. 状态与 GUI

```powershell
& $Python -m jhtdb_pipeline status --config $Config
& $Python -m jhtdb_pipeline gui --config $Config --port 8501
```

## Gaussian 滤波

Gaussian 多 sigma：

```powershell
.\.venv\Scripts\python.exe -m jhtdb_pipeline process-batch `
  --time-index 1 --sigma-grids 2 5 10 20 40 100 `
  --filter-type gaussian --config configs\pipeline.yaml
```

只计算单个 sigma 时可用 `process-center`，随后必须执行同参数的 `finalize-result`：

```powershell
.\.venv\Scripts\python.exe -m jhtdb_pipeline process-center `
  --time-index 1 --sigma-grid 20 --filter-type gaussian `
  --config configs\pipeline.yaml
.\.venv\Scripts\python.exe -m jhtdb_pipeline finalize-result `
  --time-index 1 --sigma-grid 20 --filter-type gaussian `
  --config configs\pipeline.yaml
```

## 中断恢复

重新打开 PowerShell 后无需重新安装或重新下载：

```powershell
cd D:\Xingqun_Gao\JHTDB_LOCAL
$env:JHTDB_TOKEN = "你的个人 JHTDB token"  # 使用 token 文件时省略
.\.venv\Scripts\python.exe -m jhtdb_pipeline auth status `
  --config configs\pipeline.yaml
.\.venv\Scripts\python.exe -m jhtdb_pipeline status `
  --config configs\pipeline.yaml
```

然后重新运行被中断的命令。下载、正式结果和 block CSV 都带有可验证的续跑信息；已完成
部分会复用。不要手工移动 `.staging`、修改 `COMPLETE`，也不要并行启动两个生产计算。

## 逐 regime 的 Pi forward/backscatter 统计

`compute-regime-pi` 使用全域 `Pi、W_full、W_resolved`，按与 Cq 相同的六个 regime
判据统计两个传输方向。`Pi > 0` 为 backscatter；`Pi < 0` 为 forward，界面用正幅值
`-Pi` 显示 forward。

- `mean = Σ|Pi_direction| / N_q,direction`
- `fraction = N_q,direction / N_q`
- `intensity = Σ|Pi_direction| / N_q = mean × fraction`

单组示例：

```powershell
.\.venv\Scripts\python.exe -m jhtdb_pipeline compute-regime-pi --time-index 1 --sigma-grid 15 --filter-type smooth_sharp --sharp-edge-width-fraction 0.1171875
```

Gaussian 批量示例：

```powershell
.\.venv\Scripts\python.exe -m jhtdb_pipeline compute-regime-pi --time-index 1 --filter-type gaussian --sigma-grids 2 5 10 20 40 100
```

报告按 `result_id` 写入 `regime_pi/output/<result_id>/regime_pi_transfer.json`，不修改正式
Zarr 或 manifest。在 GUI 的 `Weak asymmetry` 页面选择结果后，可查看三组柱状图、12 行
数值表和原始 JSON。
