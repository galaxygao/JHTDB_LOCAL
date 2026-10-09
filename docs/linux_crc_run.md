# Pitt CRC Linux：使用原有入口运行两个 pipeline

本方案只增加 Linux 配置与运行说明，不新增 Python 函数或运行脚本。
从 `/ix/lfang/xig134/JHTDB_LOCAL` 执行原有 CLI，使用已有 `.venv-linux/bin/python`。
没有执行 pipeline、下载、全域计算或性能基准。

## 推荐 Slurm 资源

| 阶段 | 单节点、单任务 CPU | 内存申请 | 首次 walltime 建议 |
|---|---:|---:|---:|
| 主 pipeline，一帧五尺度 RAM batch | 32 | 160G | 12 小时 |
| QPower，已有 float32 压力梯度 | 16 | 96G | 6 小时 |
| 下载或本地 FD4 梯度 | 8 | 32G | 6 小时 |
| QPower 后处理统计 | 8 | 96G | 12 小时 |

两个 pipeline 在同一 allocation 内顺序运行，可统一申请 **32 CPU / 160G / 12 小时**。
walltime 是首次申请建议，不是完成时间预测；具体队列时限、硬件和文件系统速度需按实际
allocation 确认。单帧计算尚未实测，不保证两条完整流程都能在 12 小时内结束。

**192G 不是必需的最低值。** 主流程的九个 float32 原始梯度占 36 GiB，十二个
complex64 半谱约 48.09 GiB，共享 RAM 缓存合计约 **84.09 GiB**。
另有全域 FFT 临时数组、QA、Python 和压缩缓冲，以及约 40 GiB 工作文件的驻留页。
将工作文件全额计入并留额外空间，保守规划约 145 GiB，因此建议 160G。
128G 可能依靠 Linux 回收工作文件页运行，但未实测；160G 是稳妥起点，192G 可留更多余量。
当前 16 CPU / 64 GB / 3 小时无法容纳这份 RAM 共享缓存。

QPower 原有实现完整加载速度和压力梯度，float32 输入合计约 24 GiB，q/u² 为 8 GiB。
还需事件掩码、精确 percentile 的副本、条件统计索引和绘图空间，所以建议 96G。
从压力直接计算 spectral 梯度会使用 complex128 频谱与逆变换，建议改用 160G allocation。
这些都是源码推导，原有函数没有新增的内存预算参数，也没有新增的内存拒绝门槛；
申请内存由 Slurm 的 `--mem` 控制。

在登录节点申请新 allocation，例如按账户需要补充 partition/account：

```bash
salloc --nodes=1 --ntasks=1 --cpus-per-task=32 --mem=160G --time=12:00:00
srun --pty bash -l
```

不要在现有 64 GB allocation 中嵌套申请来代替重新分配资源。
若队列限制 walltime，可在不同 job 中逐 sigma 完成全部尺度；每个 job 会重新生成所需
缓存，无法跨 job 保留 RAM 缓存复用，且单个 sigma 的耗时也未实测。

## 配置参数与并发

使用 [主 Linux 配置](../configs/pipeline.linux.crc.yaml) 和
[QPower Linux 配置](../qpower_analysis/config.linux.crc.json)。配置只使用原有支持的字段。

| 资源项 | Linux 方案 | 说明 |
|---|---|---|
| 主共享缓存 | `fft_cache_mode: memory` | 原始梯度、源频谱放在 RAM，不启用磁盘 FFT 缓存 |
| FFT worker | 24 | 32 核 allocation 中给压缩与系统留余量 |
| FFT slab | 16 | 单标量实数输入 slab 为 64 MiB；保持完整变换轴 |
| 主压缩 | 4 线程，level=3 | 原有 YAML 参数；不更换压缩算法或等级 |
| BLAS/OpenMP/MKL/BLIS/NumExpr | 各 1 线程 | 在启动 Python 前设置环境变量，避免嵌套线程池 |
| multiprocessing | 不增加进程池 | 一次运行一个 pipeline，不复制整帧或共享 RAM 缓存 |
| batch | 一帧/job；sigma 串行 | 主配置仍保留五尺度，不修改物理参数 |
| QPower 本体 | 原有整帧 RAM 读入 | 原函数没有 chunk/batch/memory-budget 配置，不添加无效字段 |
| QPower Blosc | 保留 numcodecs 原有默认，最多 8 线程 | 它在导入时设置线程数；不把仅设环境变量误写成生效的 2 线程限制 |
| 后处理块 | 保留原有 128³，脚本串行 | 已按块读取；保留统计累计顺序和 histogram 分辨率 |
| 下载 | 256×256×128 请求，1 个在途请求 | 速度 payload=96 MiB；保留已有 checksum/provenance |
| FD4 | `--block-size 64` | 原有参数；保留周期 halo 与四阶公式 |
| 下载/FD4 I/O | 分别用 `--stage download`、`--stage gradient` 顺序执行 | 避免 `--stage all` 原有的下载与 FD4 重叠 |
| 数据 chunk | 输入 checksum tile=128³，结果 chunk=64³ | 不修改缓存格式或重压缩已有输入 |
| 磁盘余量 | persistent=32 GiB，scratch=32 GiB | 使用原有磁盘预检参数 |

主谱导数、滤波、压力梯度、q 定义、阈值、percentile、显示 stride、数据 dtype 和 QA
容差均使用原有实现和参数。QPower 模板读取本地 `pressure_gradient_fd4_cache.zarr`，
与已有 `deploy.py` 的 FD4 流程一致。服务端 `fd4noint` 的
`pressure_gradient_cache.zarr` 是另一数据源，不应混用。
模板的 `gradient_method: spectral` 仅在配置 `pressure_path` 时生效；供应梯度时直接读该梯度。

## 存储与环境设置

| 路径 | 用途 | 未压缩容量规划 |
|---|---|---|
| `/ix/lfang/persistent/state` | 原始输入、catalog、manifest 和锁 | 速度 12 GiB；压力 4 GiB；FD4 梯度 12 GiB，另留 32 GiB |
| `/ix/lfang/xig134/JHTDB_CRC/results` | 主结果和 staging | 五尺度 110 GiB + 共享梯度 4.5 GiB，另留 32 GiB |
| `/ix/lfang/xig134/JHTDB_CRC/qpower` | QPower 结果、HTML 与 provenance | 按阈值点数与 run 数预留空间 |
| `/ix/lfang/xig134/JHTDB_CRC/cache` | XDG/Matplotlib 缓存 | 小文件 |
| `/vast/lfang/xig134/JHTDB_CRC/runs` | 原有每尺度工作文件 | 40 GiB + 32 GiB 余量 |
| `/vast/lfang/xig134/JHTDB_CRC/tmp` | TMPDIR | 另留临时空间 |

`memory` 关闭可选的磁盘 FFT 缓存；原有每尺度工作文件仍使用文件映射，不修改其实现。
本次没有创建上述外部目录、移动输入或修改 `/ix/lfang/persistent/pipeline.yaml`。

在实际运行前，在新 allocation 的 shell 中设置一次：

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

这些变量在导入 NumPy/SciPy/Matplotlib 前设置。不要把两条 pipeline 或多个 sigma 同时
放到后台运行；本文以顺序命令控制 I/O 并发，没有新增跨 pipeline 的锁或自动资源检查。

## 使用原有入口

已有完整速度输入时，主流程直接执行本地验证与 batch：

```bash
"$PYTHON" -m jhtdb_pipeline validate-input --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -u -m jhtdb_pipeline process-batch --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m jhtdb_pipeline status --config "$CONFIG"
```

若只算一个尺度，在原有 `process-batch` 命令后加 `--sigma-grids 10`，随后补齐其他尺度。
上述命令不会自动下载。已有压力时，FD4/QPower 使用原有模块：

```bash
"$PYTHON" -u -m jhtdb_pipeline.pressure_local --stage gradient --block-size 64 \
  --time-index "$TIME_INDEX" --config "$CONFIG" &&
"$PYTHON" -m qpower_analysis.qpower_analysis --config "$QCONFIG" --preflight-only &&
"$PYTHON" -u -m qpower_analysis.qpower_analysis --config "$QCONFIG"
```

已有验证完成的梯度可以跳过第一条。QPower JSON 默认第 1 帧；换帧时需要同步修改 JSON
里的 `frame`、`time`、两个 `tNNNNNN` 输入路径，不能仅修改 shell 中的 `TIME_INDEX`。
物理时间保持原公式 `(time_index-1)*0.002`。原有 preflight 校验压力/梯度元数据，
没有新增按 dtype 估算内存的代码。

若需要下载缺失输入，显式执行下面的原有命令；**这些命令会真实下载，本次未执行**：

```bash
"$PYTHON" -m jhtdb_pipeline cache --time-index "$TIME_INDEX" --config "$CONFIG"
"$PYTHON" -m jhtdb_pipeline.pressure_local --stage download \
  --time-index "$TIME_INDEX" --config "$CONFIG"
```

仅下载需要 token，读取 `JHTDB_TOKEN` 或配置中的 `${HOME}/.secrets/jhtdb_token`。
下载、FD4、主计算和 QPower 分阶段顺序执行。原有 `deploy.py` 保持原样，它会生成自身的
本机配置，不会自动采用这里的 Linux 参数；CRC 按上述命令显式指定配置。

QPower 完成后，原有后处理按依赖顺序执行：

```bash
RUN_DIR=/ix/lfang/xig134/JHTDB_CRC/qpower/实际run-id
"$PYTHON" -m qpower_analysis.threshold_contributions --run-dir "$RUN_DIR" &&
"$PYTHON" -m qpower_analysis.conditional_tails --run-dir "$RUN_DIR" &&
"$PYTHON" -m qpower_analysis.conditional_ranges --run-dir "$RUN_DIR" --coverage .95 &&
"$PYTHON" -m qpower_analysis.gradient_given_q --run-dir "$RUN_DIR" &&
"$PYTHON" -m qpower_analysis.angle_statistics --run-dir "$RUN_DIR" &&
"$PYTHON" -m qpower_analysis.lowest_q_bin_angles --run-dir "$RUN_DIR" &&
"$PYTHON" -m qpower_analysis.near_zero_diagnostic --run-dir "$RUN_DIR"
```

H0 连通分析与 cavity/mesh 可视化是原有的可选步骤，不自动加入上述统计链。
C++ 引擎为单线程；半径增大可能扩大 offset 列表并延长运行时间。额外申请 CPU 不会
自动改变这些算法的并行方式。按需要独立调用原有
`qpower_analysis.strong_event_h0` 及对应可视化脚本。

## 恢复和验证边界

主流程复用 provenance 匹配且带 `COMPLETE` 的结果；未完成尺度可能重算，RAM 缓存不会
跨 job 保存。FD4 保持原有逐块校验与续算。QPower 没有逐步骤 checkpoint，中断的 run
不视为完成。后台运行不能延长 Slurm walltime。

本次只检查配置解析、科学参数一致性、文档链接和命令参数，所有 Python 源码已恢复。
没有运行 doctor/smoke、输入遍历、下载、pipeline、后处理或全域基准。
