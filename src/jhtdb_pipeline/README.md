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
| `physics.py` | 周期谱导数、Gaussian 与 smooth-sharp 传递函数、regime 基础运算 |
| `processing.py` | 多 sigma 共享 FFT、完整物理量、QA、staging 和原子正式提交 |
| `sbar_qa.py` | 能量恒等式和周期域净 S-bar 检查 |
| `cq.py` | 六 regime 五场统计与 closure |
| `weak_asymmetry.py` | Pi 正负分拆、p99/max 和弱非对称指标 |
| `regime_pi.py` | 每个 regime 内 Pi forward/backscatter 统计 |
| `migration.py` | 旧 schema 结果迁移与共享原始字段 |
| `doctor.py` | Python、token、路径、内存和磁盘前检 |
| `dashboard.py` | 只读 Streamlit 结果查看器 |
| `cli.py` | `python -m jhtdb_pipeline` 命令入口 |

## 计算域与数组顺序

- 物理周期域：`[0,2π)^3`；
- 完整网格：`1024³`；
- 速度：`(component,z,y,x)`；
- 梯度：`(velocity_component,derivative_component,z,y,x)`，即
  `gradient[i,j]=∂_j velocity_i`；
- 中心裁剪：`[256:768)^3`；
- 下载后所有滤波和导数仍在完整周期域计算，不能对中心裁剪单独 FFT。

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
| `velocity_bar[3,...]` | 中心 `512³` | 滤波速度 |
| `gradient_bar[3,3,...]` | 中心 `512³` | 滤波速度梯度 |
| `work_full` | 完整 `1024³` | 完整场 work |
| `work_resolved` | 完整 `1024³` | resolved work |
| `pi` | 完整 `1024³` | `τ_ij∂_j velocity_bar_i` |
| `s_bar` | 完整 `1024³` | `∂_j(velocity_bar_i τ_ij)` |
| `regime` | 完整 `1024³` | `uint8` 六分区编码 |

逻辑字段 `velocity` 和 `gradient` 由 `shared_refs.json` 引用每帧共享数据：原始速度从
全域缓存现场裁出中心区域，原始中心梯度从共享 Zarr 读取，不在每个 sigma 下重复保存。

能量等式和符号约定：

```text
W_full = W_resolved - pi + s_bar
pi = tau:S
pi < 0 : forward cascade
pi > 0 : backscatter
Pi_LES = -pi
```

## Regime 编码

`0` 为 uncertain。其余编码使用 `W_full`、`W_resolved` 和
`ΔW=W_full-W_resolved`：

| code | label | 条件 |
|---:|---|---|
| 1 | `1+` | 两个 work 非负，`ΔW>=0` |
| 2 | `1-` | 两个 work 非负，`ΔW<0` |
| 3 | `2` | `W_full>=0, W_resolved<0` |
| 4 | `3` | `W_full<0, W_resolved>=0` |
| 5 | `4+` | 两个 work 为负，`ΔW>=0` |
| 6 | `4-` | 两个 work 为负，`ΔW<0` |

精确零归入非负侧。uncertain 阈值由配置中的
`max(epsilon_abs, epsilon_rel*RMS(work))` 控制。

## 原子提交与复用

计算首先写入 `result_root/.staging/<result_id>`。只有字段 shape/dtype/有限值、全域 QA 和
逐字段 SHA-256 全部完成后，目录才原子移动到正式路径并最后创建 `COMPLETE`。读取器只接受
正式完整结果。batch manifest 会记录所有 sigma 的路径和完成状态；再次运行时只有参数、
输入 manifest 和 schema 都匹配的结果才复用。

不要手动编辑 `.zattrs`、`manifest.json` 或 `COMPLETE`。旧 schema 必须通过迁移命令。
