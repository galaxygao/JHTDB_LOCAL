# 核心流水线实现

本目录包含下载、验证、谱计算、正式提交、统计报告和 GUI 的实现。用户安装、配置及完整
CLI 顺序见项目根目录 [`README.md`](../../README.md)。

## 模块职责

| 模块 | 职责 |
|---|---|
| `config.py` | 解析和验证 YAML；生成 result/workspace/batch 路径与 sigma tag |
| `auth.py` | 环境变量或 token 文件解析，只报告来源，不打印 token |
| `planning.py` | 完整请求块和 `128³` checksum tile 规划 |
| `jhtdb.py` | `givernylocal.getCutout` smoke、严格串行下载、重试及续传 |
| `catalog.py` | SQLite 输入 tile 状态和 checksum catalog |
| `store.py` | Zarr 输入/结果读写、数组 hash、共享字段逻辑视图 |
| `validation.py` | 输入覆盖、shape/dtype/有限值、SHA-256、接缝检查 |
| `physics.py` | 周期谱导数、Gaussian 与 smooth-sharp 传递函数 |
| `processing.py` | 多 sigma 共享 FFT、完整物理量、QA、staging 和原子正式提交 |
| `sbar_qa.py` | 能量恒等式和周期域净 S-bar 检查 |
| `weak_asymmetry.py` | Pi 正负分拆、p99/max 和弱非对称指标 |
| `doctor.py` | Python、token、路径、内存和磁盘前检 |
| `dashboard.py` | 只读 Streamlit 结果查看器 |
| `cli.py` | `python -m jhtdb_pipeline` 命令入口 |

## 计算域与数组顺序

- 物理周期域：`[0,2π)^3`；
- 完整网格：`1024³`；
- 速度：`(component,z,y,x)`；
- 梯度：`(velocity_component,derivative_component,z,y,x)`，即
  `gradient[i,j]=∂_j velocity_i`；

## 滤波器

Gaussian 传递函数：

```text
G(theta) = exp[-0.5 * (sigma_grid * theta)^2]
```

Smooth-sharp 径向传递函数：

```text
G(k) = 0.5 * erfc((|k|-k_c)/(sqrt(2)*w))
k_c = pi/(sigma_grid*dx)
```

Smooth-sharp 只支持比例宽度：`w=sharp_edge_width_fraction*k_c`。同一 `alpha=w/k_c`
用于所有 sigma，避免跨尺度时改变传递函数的相对形状。

## 正式结果字段

每个 sigma 结果目录包含一个命名 Zarr、JSON/HTML QA 和 `COMPLETE`：

| 字段 | 范围 | 含义 |
|---|---|---|
| `velocity_bar[3,...]` | 步长 2 `512³` | 滤波速度 |
| `gradient_bar[3,3,...]` | 步长 2 `512³` | 滤波速度梯度 |
| `work_full` | 完整 `1024³` | 完整场 work |
| `work_resolved` | 完整 `1024³` | resolved work |
| `pi` | 完整 `1024³` | `τ_ij∂_j velocity_bar_i` |
| `s_bar` | 完整 `1024³` | `∂_j(velocity_bar_i τ_ij)` |

逻辑字段 `velocity` 和 `gradient` 由 `shared_refs.json` 引用每帧共享数据：原始速度从
完整缓存读取，步长 2 原始梯度从共享 Zarr 读取，不在每个 sigma 下重复保存。

能量等式和符号约定：

```text
W_full = W_resolved - pi + s_bar
pi = tau:S
pi < 0 : forward cascade
pi > 0 : backscatter
Pi_LES = -pi
```

## 原子提交与复用

计算首先写入 `result_root/.staging/<result_id>`。只有字段 shape/dtype/有限值、全域 QA 和
逐字段 SHA-256 全部完成后，目录才原子移动到正式路径并最后创建 `COMPLETE`。读取器只接受
正式完整结果。batch manifest 会记录所有 sigma 的路径和完成状态；再次运行时只有参数、
输入 manifest 和 schema 都匹配的结果才复用。

不要手动编辑 `.zattrs`、`manifest.json` 或 `COMPLETE`。当前读取 v7/v8/v9，写入 v9；新结果使用独立 `_v9` 路径，见[当前数据格式](../../docs/data_versions.md)。


## 全域计算、步长 2 向量存储与磁盘 FFT

- 原始速度：`state/inputs/tNNNNNN/velocity_cache.zarr/velocity`。
- 原始梯度：`results/tNNNNNN_shared_stride2_v9/sampled_raw.zarr/gradient`，每轴步长 2。
- 每尺度结果：`<result_id>/full_result_sigma_<sigma>.zarr`。
- 原始梯度、滤波速度、滤波梯度保存 `[::2,::2,::2]`，空间维度 `512³`，scope 为 `full_domain_stride2`；原始速度输入和所有标量场完整 `1024³`，scope 为 `full_domain`。
- `field_sampling` 逐字段记录原网格 origin、stride 与 shape；采样起点固定为 0，周期域均匀覆盖。GUI 速度对比在相同原网格点读取两场，图轴和切片索引使用原网格坐标。
- `process-full` 计算单尺度，`finalize-result` 提交；`process-batch` 保留跨尺度计算复用。
- `disk_fft.py` 为 memmap 模式提供逐轴全长度 FFT。九个原始梯度、十二个源频谱在同一 batch
  只生成一次；径向滤波写入独立磁盘临时频谱，不修改共享频谱。每个 slab 保留完整被变换轴。
- 共享 batch 缓存是临时文件，正常退出或异常处理时关闭并删除；下次运行会重新构建必要缓存。
  正式共享梯度和各尺度结果会永久保留。旧数据文件不会通过转换补齐。

完整函数签名、调用和异常见 [代码参考](../../docs/code_reference.md)。
