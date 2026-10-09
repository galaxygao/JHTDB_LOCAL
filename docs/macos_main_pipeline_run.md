# macOS 主流水线：步长 2 向量存储与 24 GB 配置

2026-10-02，Apple M5 / 10 核（4 性能 + 6 能效）/ 24 GB RAM / arm64。
本页说明主 pipeline 的 macOS 运行方式。
按用户要求，最终版本不启动生产下载或完整域批量计算，由用户在 Terminal 执行。

## 当前代码与数据布局

当前结果格式为 v9。计算网格完整 `1024³`；共享原始梯度、滤波速度和滤波梯度仅保存原网格 `[::2,::2,::2]`，得到覆盖全域的 `512³` 点。原始速度输入和所有标量场完整保存。采样映射写入 `field_sampling`，不引入空间裁剪。

| 数据 | 保存位置 | 未压缩大小 |
|---|---|---:|
| 原始速度，3 分量 | `.local/state/inputs/t000001/velocity_cache.zarr` | 12 GiB |
| 原始速度梯度，9 分量、步长 2 | `.local/results/t000001_shared_stride2_v9/sampled_raw.zarr` | 4.5 GiB |
| 每尺度滤波速度，3 分量、步长 2 | 各结果目录 `full_result_sigma_*.zarr/velocity_bar` | 1.5 GiB |
| 每尺度滤波梯度，9 分量、步长 2 | 同上 `gradient_bar` | 4.5 GiB |
| 每尺度 Pi、S-bar、两个 Work | 同上 | 16 GiB |

每尺度共 22 GiB，五尺度加共享输入共 126.5 GiB。原始速度和梯度每帧只保存一份，
每尺度通过 `shared_refs.json` 引用。实际 Zarr 文件使用压缩，容量预检按未压缩大小计算。

新结果与共享目录使用独立 v9 路径，旧结果仅供读取，见[当前数据格式](data_versions.md)。

## 10 核 / 24 GB 配置

使用 `configs/pipeline.macos.yaml`。自定义本机配置应同步下列线程与缓存参数，并使用当前配置项。

```yaml
storage:
  compression_threads: 6
physics:
  fft_workers: 10
  fft_slab_width: 16
  fft_cache_mode: memmap
```

原 Windows 配置保留路径和 RAM 模式。Mac 不要使用 RAM 模式：共享梯度和十二个频谱
本身约 84.09 GiB，减少线程不能解决这部分内存需求。

memmap 模式把共享梯度和频谱放在磁盘，仍只构建一次、供所有 sigma 共用。FFT 逐轴、
按 slab 执行，每次变换都包含完整被变换轴，不减少格点。滤波使用独立磁盘频谱，避免修改
共享源频谱。映射写回后，在系统支持时释放文件映射页供系统回收。

共享临时缓存约 84.09 GiB；全部临时容量的保守估算约 136.11 GiB。五尺度数据、输入、
临时空间和 24 GiB 余量合计约 286.61 GiB。输入已存在时，同盘 batch 前检要求剩余空间
约 274.61 GiB；实际前检随待算尺度数调整。临时共享缓存正常退出或异常处理时清理。
完成的全场梯度和结果永久保留；强制终止进程可能遗留临时文件。

### 参数依据与限制

在本机对 `1024×1024×slab` 实数 FFT 和 `1024×slab×513` 复数 FFT 短测，
每组预热后取三次中位数。以下耗时按 slab 换算，仅用于参数比较，不是生产运行耗时：

| slab | FFT workers | 两类 FFT 换算秒数 |
|---:|---:|---:|
| 16 | 4 | 0.5145 |
| 16 | 8 | 0.3939 |
| 16 | 10 | 0.3633 |
| 32 | 10 | 0.3549 |

slab=32 比 16 仅快约 2.3%，单块工作内存估算翻倍，故选 16。slab=16 的实数输入块
为 64 MiB，FFT 临时数组保守工作估算约 1 GiB，**不是整个进程的峰值承诺**。
64³ Zarr 结果块压缩/解压短测中，6 线程约 0.410 ms，8 线程约 0.422 ms，10 线程约
0.415 ms，故选 6。线程基准文件在 `.local/macos_main_run/*benchmark*`。
FFT 和压缩主要依次执行。FFT 显式使用配置中的 10 worker。
完整 `1024³` 新版本的总 RSS、操作系统文件缓存和最终耗时尚未实测，不能保证任何系统负载下
绝不内存不足。用户已要求由其自行执行生产计算。

## 用户执行命令

首次安装环境与保存 token 按 [根 README](../README.md#first-deployment) 执行，统一使用 `python3 deploy.py --stage setup`，环境为 `.venv-mac`。以下命令用于部署完成后的运行，已有环境和 token 无需重复安装或录入。
从你的项目根目录执行；示例路径应改为本机位置。默认配置使用 `.local`，换数据盘时须另存 YAML 并同步 state/run/result 路径，不能只改 deploy 的 `--data-root`。

```bash
cd /Users/xingqungao/Desktop/Sync_File/26FA/JHU_DATA

# 检查与输入准备
PYTHON=.venv-mac/bin/python
CONFIG=configs/pipeline.macos.yaml
TIME_INDEX=500  # 换帧只改这里
"$PYTHON" -m jhtdb_pipeline doctor --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline plan --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline smoke --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline cache --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline validate-input --time-index "$TIME_INDEX" --config "$CONFIG" &&

# 正式计算：一次 process-batch，共享缓存，输出直接显示在 Terminal
"$PYTHON" -u -m jhtdb_pipeline process-batch --time-index "$TIME_INDEX" --config "$CONFIG" &&


# 计算结束后启动 GUI
STREAMLIT_SERVER_HEADLESS=true "$PYTHON" -m jhtdb_pipeline gui \
  --config "$CONFIG" --port 8501
```

上面的流程直接运行 Python 命令，通过同一个 `TIME_INDEX` 变量传入所有步骤，计算其他帧只需修改该变量。
可在主计算命令前加 `caffeinate -i` 防止空闲睡眠；也可使用包装脚本
`JHTDB_MAIN_CONFIG="$CONFIG" bash scripts/run_main_macos.sh "$TIME_INDEX"`。
脚本第一个参数指定时间帧，不传时默认 `1`。Python 命令的 `--time-index` 不会自动传给下一条命令。
命令之间用 `&&` 连接，任何一步失败都会停止后续计算、统计和 GUI 启动。

访问 <http://127.0.0.1:8501>。逐结果检查 `qa.json`、`divergence.json` 和 `s_bar_qa.json`；
`COMPLETE` 表示存储提交完成，GUI 仍会明确展示失败的科学 QA。

## macOS 命令差异

- deploy 的 Windows 环境 `.venv-windows\Scripts\python.exe` → `.venv-mac/bin/python`；旧 Windows 包装脚本使用 `.venv`。
- PowerShell 反引号续行 → shell 的 `\`；环境变量使用 `export`。
- Mac 配置使用 `.local/`，token 由 `JHTDB_TOKEN` 或 `${HOME}/.secrets/jhtdb_token` 读取。
- `caffeinate -i` 防止空闲睡眠；脚本已内置调用。
- `STREAMLIT_SERVER_HEADLESS=true` 避免首次启动邮箱交互提示。
- 沙箱执行时在线下载和本机监听端口需要对应权限；普通 Terminal 不受该工具沙箱限制。

## 资源预检

完整域内存峰值尚未在此配置下实测。五尺度 v9 永久数据约 126.5 GiB（含输入），完整 FFT 共享缓存约 84.09 GiB，另需工作区与安全余量。运行 `plan` 与 `process-batch` 预检获取本机实际要求；不同磁盘分别预留空间。小域测试不能替代完整域资源验证。
