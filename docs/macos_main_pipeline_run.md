# macOS 主流水线：步长 2 向量存储与 24 GB 配置

2026-10-02，Apple M5 / 10 核（4 性能 + 6 能效）/ 24 GB RAM / arm64。
本次范围为主项目；不执行 block statistics、QPower 等子项目。
按用户要求，最终版本不启动生产下载或完整域批量计算，由用户在 Terminal 执行。

## 当前代码与数据布局

当前结果格式为 v8。计算网格完整 `1024³`；共享原始梯度、滤波速度和滤波梯度仅保存原网格 `[::2,::2,::2]`，得到覆盖全域的 `512³` 点。原始速度输入和所有标量场完整保存。采样映射写入 `field_sampling`，不引入空间裁剪。

| 数据 | 保存位置 | 未压缩大小 |
|---|---|---:|
| 原始速度，3 分量 | `.local/state/inputs/t000001/velocity_cache.zarr` | 12 GiB |
| 原始速度梯度，9 分量、步长 2 | `.local/results/t000001_shared_stride2/sampled_raw.zarr` | 4.5 GiB |
| 每尺度滤波速度，3 分量、步长 2 | 各结果目录 `full_result_sigma_*.zarr/velocity_bar` | 1.5 GiB |
| 每尺度滤波梯度，9 分量、步长 2 | 同上 `gradient_bar` | 4.5 GiB |
| 每尺度 Pi、S-bar、两个 Work、regime | 同上 | 17 GiB |

每尺度共 23 GiB，五尺度加共享输入共 131.5 GiB。原始速度和梯度每帧只保存一份，
每尺度通过 `shared_refs.json` 引用。实际 Zarr 文件使用压缩，容量预检按未压缩大小计算。

已删除 `migration.py`、旧格式转换函数、`migrate-existing`、`upgrade-result`、
`backfill-full-fields`、`backfill-full-regime` 和对应迁移测试。单尺度命令更名为
`process-full`。旧结果不会被转换成完整场；重新计算产生新结果。
旧数据文件未主动清除；显式重算同参数结果仍沿用 staging 完成后替换正式目录的提交行为。

## 10 核 / 24 GB 配置

使用 `configs/pipeline.macos.yaml`。现有 `.local/pipeline.yaml` 和
`.local/macos_main_run/pipeline.yaml` 也已同步线程与缓存参数。

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
临时空间和 24 GiB 余量合计约 291.61 GiB。输入已存在时，同盘 batch 前检要求剩余空间
约 279.61 GiB；实际前检随待算尺度数调整。临时共享缓存正常退出或异常处理时清理。
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
FFT 和压缩主要依次执行。脚本限制额外 BLAS 线程池为 1，FFT 仍显式使用 10 worker。
完整 `1024³` 新版本的总 RSS、操作系统文件缓存和最终耗时尚未实测，不能保证任何系统负载下
绝不内存不足。用户已要求由其自行执行生产计算。

## 用户执行命令

从项目根目录运行。已有虚拟环境和输入缓存时无需重新创建环境或强制下载。

```bash
cd /Users/xingqungao/Desktop/Sync_File/26FA/JHU_DATA

# 安装依赖仅在首次或环境缺失时执行
python3 -m venv .venv-mac
.venv-mac/bin/python -m pip install -e '.[dev]'

# 检查与输入准备
export MPLCONFIGDIR="$PWD/.local/cache/matplotlib"
.venv-mac/bin/python -m jhtdb_pipeline doctor --time-index 1 --config configs/pipeline.macos.yaml
.venv-mac/bin/python -m jhtdb_pipeline plan --time-index 1 --config configs/pipeline.macos.yaml
.venv-mac/bin/python -m jhtdb_pipeline smoke --time-index 1 --config configs/pipeline.macos.yaml
.venv-mac/bin/python -m jhtdb_pipeline cache --time-index 1 --config configs/pipeline.macos.yaml
.venv-mac/bin/python -m jhtdb_pipeline validate-input --time-index 1 --config configs/pipeline.macos.yaml

# 正式计算：一次 process-batch，共享缓存，输出直接显示在 Terminal
bash scripts/run_main_macos.sh

# 计算结束后启动 GUI
STREAMLIT_SERVER_HEADLESS=true .venv-mac/bin/python -m jhtdb_pipeline gui \
  --config configs/pipeline.macos.yaml --port 8501
```

脚本第一个参数指定时间帧，默认 `1`。计算第 500 帧时使用
`bash scripts/run_main_macos.sh 500`，并将检查、输入准备和统计命令的 `--time-index` 同步设为 `500`。

访问 <http://127.0.0.1:8501>。逐结果检查 `qa.json`、`divergence.json` 和 `s_bar_qa.json`；
`COMPLETE` 表示存储提交完成，GUI 仍会明确展示失败的科学 QA。

## macOS 命令差异

- `.venv\Scripts\python.exe` → `.venv-mac/bin/python`。
- PowerShell 反引号续行 → shell 的 `\`；环境变量使用 `export`。
- Mac 配置使用 `.local/`，token 由 `JHTDB_TOKEN` 或 `${HOME}/.secrets/jhtdb_token` 读取。
- `caffeinate -i` 防止空闲睡眠；脚本已内置调用。
- `MPLCONFIGDIR` 使用可写目录，避免默认缓存权限警告。
- `STREAMLIT_SERVER_HEADLESS=true` 避免首次启动邮箱交互提示。
- 沙箱执行时在线下载和本机监听端口需要对应权限；普通 Terminal 不受该工具沙箱限制。

## 已完成的验证与历史运行

此前原版本环境检查通过，Python 3.13.15，pip check 无冲突；在线 smoke 返回真实
3×8×8×8 float32 数据，完整第 1 帧速度缓存校验通过。输入 manifest SHA256：
`0c74324856981c33c1e1b67f583fda28ed1265db754bfe52b37c188691e625a2`。

此前单尺度试跑于约 03:09 EDT 后停止，没有正式结果与 QA。新版本没有继续该生产任务。
旧 GUI 当时健康检查成功，之后也已停止；当前没有由本次改动启动的常驻 GUI。

新版本只执行小网格测试及短时线程基准：包含完整周期域物理恒等式、磁盘/内存算法比较、
跨 sigma 频谱复用、奇数网格和非整除 slab、故障清理、结果维度及 GUI 全页验证。
验证命令为 `.venv-mac/bin/python -m pytest tests -q`；日志位于
`.local/macos_main_run/full_fields_tests.log`。

## 第 500 帧空间预检

第 500 帧输入已校验，512/512 个速度 tile 完整。v8 五尺度同盘计算的预检要求
约 279.61 GiB 可用空间，包括所有待算结果、共享梯度、完整 FFT 缓存、工作区和 24 GiB 余量。
运行 `plan` 查看配置预算；再执行 `bash scripts/run_main_macos.sh 500`。

此前 v7 全点存储启动因 349.50 GiB 可用、521.11 GiB 所需而退出；这个历史要求不适用于 v8。
如果结果盘和临时盘不同，分别预检两个磁盘；已有结果的路径迁移见
[系统迁移](system_migration.md)。

## 压缩与历史 v7 容量实测

`storage.compression_level=3`，使用 Blosc Zstd + BITSHUFFLE 无损压缩，
压缩线程为 6。完整 `1024³` 的一个 float32 标量场未压缩恰为 4 GiB。
以下是转换前 v7 的 sigma=10、第 1 帧结果，实际磁盘占用通过 `du -sk` 测量如下；
这些全点存储数字仅作历史对照，不是当前 v8 的容量预算。

| 每尺度字段 | 未压缩 GiB | 实际磁盘占用 GiB |
|---|---:|---:|
| 滤波速度，3 分量 | 12 | 8.975 |
| 滤波梯度，9 分量 | 36 | 30.099 |
| Pi、S-bar、W-full、W-resolved，4 标量 | 16 | 13.550 |
| regime，uint8 | 1 | 0.158 |
| 合计 | 65 | 52.782 |

原始速度和原始梯度每帧仅保存一次，通过 `shared_refs.json` 引用，
不包含在每尺度 65 GiB 内。完整 float32 字段保留所有位，压缩结果以实际数据为准。

对上述结果的全部字段/分量，分别抽取起点为 `(0,0,0)`、`(448,448,448)`、
`(960,960,960)` 的 `64³` 块，共 48.75 MiB，使用相同 chunk 与 bitshuffle
比较压缩级别，并逐块验证解码字节与原值一致：

| Zstd 级别 | 样本压缩后 MiB | 相比级别 3 节省 |
|---|---:|---:|
| 3 | 39.641 | — |
| 6 | 38.033 | 4.06% |
| 9 | 37.114 | 6.38% |

这是数据块样本测量，不是全部结果重压缩。提高级别会增加编码耗时，
也不会自动改写已有数组的 compressor；当前配置仍为 3。
结果记录位于 `.local/macos_main_run/compression_sample.json`。
空间预检仍按未压缩容量，不能用这个样本比例代替全域容量检查。
