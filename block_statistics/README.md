# 全域 block 统计与 SijSij

本目录把一个正式 `1024³` 结果精确划分成等大的三维 block，计算每块的应变收缩和能量
传输量。实现代码：

- `compute_block_statistics.py`：用全域原场速度计算应变并写逐 block CSV；
- `plot_vs_strain.py`：按 block mean `SijSij` 排序并绘制三个二维关系图。

## 定义

```text
gradient[i,j] = d_j velocity_i
S[i,j] = 0.5 * (gradient[i,j] + gradient[j,i])
SijSij = sum_ij S[i,j] * S[i,j]
```

脚本直接读取共享的完整原场速度缓存 `velocity`，用周期谱导数逐项累计 `SijSij`；
这里的速度不经过滤波。`Pi` 等正式结果本身的定义不变。

完整域 `SijSij` 按帧保存在本子项目 `cache/tNNNNNN/strain_cache.zarr`；临时数组位于 `.scratch/tNNNNNN/`。已有 state 下的旧 strain 缓存保留，本入口会在新位置重新建立缓存。实现位于 `strain.py`，主库 `jhtdb_pipeline.strain` 仅保留兼容导出。缓存记录原速度
manifest hash、定义、帧号和完成状态；同一帧的所有 filter/sigma 共用这一份数据。第一次运行
该帧的 block 统计时执行 9 次谱导数并创建缓存，后续 sigma 只读取缓存并进行 block 聚合。

默认 `blocks-per-axis=16`，产生 `16³=4096` 个互不重叠的 `64³` block，每块包含
262144 个格点。没有空间抽样，每个完整域格点恰好进入一个 block。该参数必须整除 1024。

每个 CSV 行包含：

- block ID、三维 block index、网格和物理坐标范围、点数；
- `sij_sij` 的 mean 和 sum；
- `work_resolved`、`work_full`、`pi` 的 mean、sum、std、min 和 max。

## 运行

比例 smooth-sharp：

```powershell
.\.venv\Scripts\python.exe block_statistics\compute_block_statistics.py `
  --time-index 1 --sigma-grid 30 `
  --filter-type smooth_sharp --sharp-edge-width-fraction 0.1171875 `
  --blocks-per-axis 16 `
  --output-root block_statistics\output `
  --scratch-root block_statistics\.scratch `
  --config configs\pipeline.yaml
```

Gaussian：

```powershell
.\.venv\Scripts\python.exe block_statistics\compute_block_statistics.py `
  --time-index 1 --sigma-grid 20 --filter-type gaussian `
  --blocks-per-axis 16 --config configs\pipeline.yaml
```

有效 CSV 和 metadata 默认复用；加 `--overwrite` 强制重算。`--overwrite` 只强制重建该
sigma 的 block CSV，不会重复计算仍然有效的逐帧 `strain_cache.zarr`。首次创建共享缓存时需要
两个完整域 float32 FFT 临时数组；多个 sigma 可以串行执行并自动复用共享缓存。

## 绘图

将 `<result_id>` 替换为实际输出目录名：

```powershell
.\.venv\Scripts\python.exe block_statistics\plot_vs_strain.py `
  --input block_statistics\output\<result_id>
```

输出目录包括：

- `block_statistics_16x16x16.csv`：未排序完整统计；
- `metadata.json`：参数、源 manifest hash、共享 strain cache 引用、定义和全域均值；
- `block_statistics_sorted_by_sij_sij.csv`：按 mean `SijSij` 升序；
- `quantities_vs_sij_sij.html`：mean `W_res/W_full/Pi` 对 mean `SijSij`；
- `visualization_metadata.json`：绘图来源和排序信息。

HTML 对所有 block 逐点绘制，不做抽样。悬停包含排名、block ID 和三维 block 坐标。

## Regime 成对 Pi 非对称性

`regime_pair_asymmetry.py` 在每个 block 内比较 legacy regime Q1/Q4 和
Q2/Q3。六编码结果按以下方式还原为 legacy regime：

- Q1 = `1+` + `1-`（regime code 1、2）；
- Q2 = regime code 3；
- Q3 = regime code 4；
- Q4 = `4+` + `4-`（regime code 5、6）。

对于一个 regime $q$，定义 backscatter 和 forward 的正幅值总量：

$$
B_q=\sum_{\boldsymbol{x}\in q,\,\Pi(\boldsymbol{x})>0}\Pi(\boldsymbol{x}),
$$

$$
F_q=\sum_{\boldsymbol{x}\in q,\,\Pi(\boldsymbol{x})<0}
\left[-\Pi(\boldsymbol{x})\right].
$$

对于成对 regime $(a,b)$，backscatter 和 forward 非对称性定义为：

$$
A_B^{a,b}=\frac{B_a-B_b}{B_a+B_b},
$$

$$
A_F^{a,b}=\frac{F_a-F_b}{F_a+F_b}.
$$

每个 regime 的带符号净传输为 $T_q=B_q-F_q$。为避免正负传输抵消造成
分母接近零，total 非对称性使用总绝对传输活动量归一化：

$$
A_T^{a,b}
=\frac{T_a-T_b}{B_a+F_a+B_b+F_b}
=\frac{(B_a-F_a)-(B_b-F_b)}{B_a+F_a+B_b+F_b}.
$$

三个指标均满足 $-1\leq A\leq 1$。$A=0$ 表示成对对称；$A>0$ 表示左侧
regime 更强；$A<0$ 表示右侧 regime 更强；$\lvert A\rvert$ 越大表示不对称
越明显。若分母为零则输出 `NaN`。

运行示例：

```powershell
.\.venv\Scripts\python.exe block_statistics\regime_pair_asymmetry.py `
  --time-index 1 --sigma-grid 10 `
  --filter-type smooth_sharp `
  --sharp-edge-width-fraction 0.1171875 `
  --blocks-per-axis 16 `
  --config configs\pipeline.yaml
```

该命令要求相同结果目录中已经存在对应的
`block_statistics_16x16x16.csv`，并输出：

- `regime_pair_pi_asymmetry.csv`：每个 block 的六个 `A` 值；
- `regime_pair_pi_asymmetry.json`：定义、符号约定和来源校验信息；
- `regime_pair_pi_asymmetry_vs_sij_sij.html`：Q1/Q4、Q2/Q3 分别针对
  backscatter、forward、total 的六面板二维散点图。横坐标为 block mean
  `SijSij`，纵坐标为对应的 `A`，完整绘制所有 block，不抽样。

## 代码与验证导航

所有运行命令从项目根目录执行。完整参数见 [CLI 参考](../docs/cli_reference.md)，所有函数与实现定位见 [本项目代码参考](CODE_REFERENCE.md)。测试：`python -m pytest block_statistics/tests -q`；解释器使用根 README 对应平台虚拟环境。返回 [项目 README](../README.md)。

`--scratch-root` 当前是保留的兼容参数，统计函数并未使用它改变 strain 工作区；真实应变临时文件由 `strain.py` 固定置于本目录 `.scratch/tNNNNNN/`。
