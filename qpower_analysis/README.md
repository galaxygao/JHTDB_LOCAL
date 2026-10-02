# 3-D pressure-power analysis

独立任务定义见 [TASK.md](TASK.md)。所有命令从项目根目录执行。

It computes

`q = -(u*dPdx + v*dPdy + w*dPdz)` and `u2 = u*u + v*v + w*w`

for one or more 3-D frames, writes per-frame and aggregate CSV files, orthogonal
slices, threshold-region HTML visualizations, overlays, and conditional means.

## Safety rule: pressure is required

Every invocation performs a metadata-only preflight before allocating a run
directory or loading full arrays. A frame must provide either:

- `pressure_path` containing `pressure_key`, or
- all three arrays named by `pressure_gradient_keys`.

Missing pressure is a hard error. It is never replaced with zero.

## Input formats

Zarr v2 directories, `.npy`, and `.npz` files are supported. Velocity may be a
single component-first array `(3, z, y, x)`. Pressure
is `(z, y, x)`. Pressure gradients may be a component-first `(3, z, y, x)`
array or three separate arrays. All fields must have the same finite 3-D shape.

Copy `config.example.json`, set the paths and frame metadata, then run:

```powershell
.\.venv\Scripts\python.exe qpower_analysis\qpower_analysis.py --config qpower_analysis\config.example.json --preflight-only
.\.venv\Scripts\python.exe qpower_analysis\qpower_analysis.py --config qpower_analysis\config.example.json
```

The example points at the local velocity cache and the managed pressure-gradient
cache. Its preflight fails until the pressure-gradient download is complete.
See `../docs/pressure_gradient_loading.md` for acquisition commands.

Tests use small synthetic fields and do not need production data:

```powershell
.\.venv\Scripts\python.exe -m pytest qpower_analysis/tests -q
```

## Analytic random-overlap baseline

`overlap_statistics.csv` also includes `random_p_a_given_b = a_fraction`,
`random_p_b_given_a = b_fraction`, and `p_a_given_b_over_random` /
`p_b_given_a_over_random`. These compare the measured conditional probabilities
against independent random subsets of the same sizes in the same full domain.
Both ratios equal `N * intersection_count / (a_count * b_count)`:
1 means the independent expectation, above 1 means enhanced overlap, below 1 means
reduced overlap. No simulation is used. A conditional probability with an empty
conditioning set, or a ratio with a zero baseline, is reported as NaN.

## Threshold contribution fractions

After a completed run, calculate full-grid contributions using bounded-memory reads:

```bash
.venv-mac/bin/python qpower_analysis/threshold_contributions.py --run-dir qpower_analysis/output/<run-id>
```

On Windows use `.venv-windows\Scripts\python.exe` with the same script and arguments.
This writes `threshold_contributions.csv` (A, B and their intersections),
`contribution_totals.csv`, and `contribution_metadata.json`. Each `_fraction` is the
regional sum divided by the full-domain sum of the same quantity: `u2`, positive q,
negative-q magnitude, absolute q, or q squared. `u2_fraction` also gives the kinetic
energy fraction for constant density. Signed net q is retained as a sum, not a
fraction, because its global sum is close to zero. Nested threshold fractions
must not be added. Existing thresholds are reused and intersection counts must
match `overlap_statistics.csv` exactly. No sampling or new download is performed.

## Full-tail bidirectional conditional plots

```bash
.venv-mac/bin/python qpower_analysis/conditional_tails.py --run-dir qpower_analysis/output/<run-id>
```

Windows uses `.venv-windows\Scripts\python.exe` with identical arguments.
Outputs are in the run's `conditional_tails/` directory: PNG, PDF and CSV for both
`q_given_u2` and `u2_given_q`, plus metadata. Inputs remain full-grid; no tail is
excluded. The 2.5th and 97.5th percentiles are estimated by interpolating a
131072-bin full-grid histogram; metadata records its resolution and the actual
volume fraction in each region. Means and bin counts then use all grid points
with float64 sums. The 95% interval refers to the distribution of the horizontal
variable, not a confidence interval for the conditional mean.

Each figure has three columns: lower 2.5% tail (red), central 95% (blue), and
upper 2.5% tail (red). Central x uses 60 linear bins; each tail uses 20 geometric
bins where the endpoints have the same nonzero sign. Negative q retains its sign
on a logarithmic-magnitude axis. Conditional-mean y axes are linear with separate
limits per panel. The lower row shows each bin's full-domain volume percentage,
not probability density; tail volume y axes are logarithmic. Hollow markers
identify nonempty bins with fewer than 100 points; all means are retained in CSV.
The earlier 99.9%-truncated figure is preserved separately.

### Within-bin 95% value ranges

```bash
.venv-mac/bin/python qpower_analysis/conditional_ranges.py --run-dir qpower_analysis/output/<run-id> --coverage .95
```

This adds shaded point-value percentile bands to both conditional-tail plots,
without changing their x-bin boundaries, normalization, counts, or mean curves.
CSV columns `value_p025` and `value_p975` give the vertical variable's 2.5th and
97.5th percentiles within each horizontal bin. These describe within-bin spread,
not confidence intervals or uncertainty of the conditional mean. The horizontal
central-95% split and the vertical within-bin 95% band are separate definitions.

All grid points enter 65536-bin nonuniform conditional histograms. q uses symmetric
geometric resolution around zero, and u² uses positive geometric resolution.
Percentiles are interpolated inside histogram cells; bins with fewer than 100
points instead retain all values and use exact NumPy linear percentiles. Sparse
bins remain marked; empty bins have NaN bounds. Histograms and their edges are
saved as NPZ for reproducibility. Each histogram's count must exactly match the
previous CSV. Wide bands may expand the linear vertical limits and make the
unchanged mean curve appear flatter.

To display the middle 50% (25th–75th percentiles), reuse the saved full-grid histograms:

```bash
.venv-mac/bin/python qpower_analysis/conditional_ranges.py --run-dir qpower_analysis/output/<run-id> --coverage .5 --from-histograms
```

Coverage defaults to 0.5. The horizontal central-95% split is unchanged. Cached
mode interpolates percentiles for every bin (including sparse bins) from saved
histograms and needs no grid scan. The current band uses CSV `value_lower`,
`value_upper`, and `value_coverage`; 50% bounds are also stored as `value_p25` and
`value_p75`. Previous 95% columns remain available when already present.

### Velocity–pressure-gradient angles in overlap regions

Run `.venv-mac/bin/python qpower_analysis/angle_statistics.py --run-dir qpower_analysis/output/20261001T044629Z` (use your platform's Python environment). Defaults select `q/q_rms > 1 AND u²/mean(u²) > 1`; override with `--alpha` and `--beta`. This reads the first configured frame in bounded blocks and retains only selected angle/power/energy values. The horizontal variables are `q/q_rms` and `u²/mean(u²)`, using `q=-u·grad(P)`.

Outputs in `angle_statistics/` include volume-weighted angle statistics, Pearson correlations, conditional-bin CSVs and PNG/PDF plots. Angles are between `u` and the pressure force direction `-grad(P)`, in degrees, where `P=p/rho`. They are supplementary to velocity–pressure-gradient angles: `theta_force = 180° - theta_gradient`, and their cosines have opposite signs. CSV bins cover the entire selected population: 40 equal-width bins in its central 95%, with each 2.5% tail pooled separately. Plots show the central bins on shared horizontal axes and report tail volume and mean angle separately in red text, avoiding misleading wide tail bars. Volume axes are linear. Vertical shading shows the within-bin 25th–75th percentiles, not confidence intervals. Volume bars use selected-region volume as denominator. Correlations are conditional on the overlap selection and should not be interpreted as unconditional or causal relationships.

Angle plots also show an orange dashed curve on an independent right axis: the within-bin mean of `cos(theta)`, computed point by point before averaging. This differs from the cosine of the mean angle. The overall mean cosine is saved in `summary.json`, and each bin's mean cosine is saved in its CSV.

## 代码与验证导航

所有运行命令从项目根目录执行。完整参数见 [CLI 参考](../docs/cli_reference.md)，所有函数与实现定位见 [本项目代码参考](CODE_REFERENCE.md)。测试：`python -m pytest qpower_analysis/tests -q`；解释器使用根 README 对应平台虚拟环境。返回 [项目 README](../README.md)。

## 辅助入口与目录

- `scripts/download_then_qpower.py --job-dir qpower_analysis/output/qpower_jobs/NEW_JOB`：已有速度前提下下载服务端梯度，依次 preflight、分析；新 job-dir 必须不存在，失败停止并保存 status/log。
- `scripts/quickstart_qpower_subset.py --config configs/pipeline.yaml --shape-xyz 128 128 64`：仅使用已校验服务端梯度子域，不发网络请求，不代表全域统计。调用时脚本前加 `qpower_analysis/`。
- 新部署推荐 [deploy 本地 FD4 流程](../docs/deployment.md)。config.example.json 是服务端梯度例子；deploy 生成的配置会指向本地 FD4，二者不可混用。
- `output/qpower_jobs/`、`output/qpower_subset/` 保留搬入的历史任务；其中记录的旧绝对路径不改写。`output/logs/` 放子项目补充日志。
- 后处理依赖顺序：先主分析，再 conditional_tails，再 conditional_ranges；threshold_contributions 和 angle_statistics 可在主分析后单独执行。

## 配置字段与实现限制

`config.example.json` 中路径相对于启动工作目录，而非 JSON 文件所在目录。采用 project-root 命令约定。`frames` 至少一帧：`frame` 是整数帧号，`time` 为物理时间；`velocity_path/velocity_key` 指定 `(3,z,y,x)` 速度。`pressure_path/pressure_key` 与 `pressure_gradient_path/pressure_gradient_keys` 二选一；如果同时给出，当前代码优先 pressure_path。梯度 keys 可为一个三分量数组名或三个标量数组名。已管理梯度需 validated 且帧/时间匹配。

| 字段 | 默认/约束 | 实际作用 |
|---|---|---|
| axis_order | zyx | 仅支持 zyx，不自动转轴 |
| domain_lengths_xyz | 三轴长度 | 从标量压力求导时使用 |
| periodic_xyz | 全 true | spectral preflight 要求三轴周期 |
| gradient_method | spectral / finite_difference | 只有输入标量压力时才求导；已有梯度直接读取 |
| pressure_definition | 描述字符串 | 写 provenance，不执行 p/rho 单位换算 |
| alphas | [1,2,3,4] | A 事件阈值，相对于 q_rms |
| betas | [1,1.5,2,3] | B 事件 `u²>beta*mean(u²)` |
| event_mode | positive/negative/absolute | A 为 q、-q 或 abs(q) 严格超过 alpha*q_rms |
| n_conditional_bins | 60 | 初始 E[q/q_rms\|u²/mean(u²)] 公共线性分箱 |
| min_bin_count | 100 | 初始条件均值有效性阈值 |
| conditional_percentile | 99.9 | 各帧横变量分位上界取最大值；超出点数写 metadata |
| overlay_pairs | null | 默认 alpha×beta 全组合；显式 pair 必须在阈值列表中 |
| visualization_stride | 配置示例 8；缺省 1 | 只降低图形点数，不改变事件计数 |
| output_root | qpower_analysis/output | 新 UTC 秒时间戳运行目录；同名存在则拒绝覆盖 |

`gradient_method=finite_difference` 在 QPower 内部调用 `numpy.gradient(...,edge_order=2)`，**不是** pressure_local 的周期四阶 FD4；已有 FD4 梯度时应通过 gradient_path 直接传入。QPower 速度当前只支持一个 `(3,z,y,x)` 数组，不能以三个独立速度 key 输入。

多帧 aggregate 是各有效帧条件均值的等权平均和样本标准差（ddof=1），不是按格点总数加权的 ensemble PDF。初始条件图截断上界与后续 `conditional_tails` 全尾部图不同。没有压力、NaN/Inf、shape 不一致会失败；preflight 是元数据检查，完整数组有限值在加载后再检查。后处理脚本目前读取首个配置帧，不自动聚合多帧，需按帧独立运行和记录。
