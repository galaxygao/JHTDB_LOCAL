# 三维湍流压力功率间歇事件分析任务

## 1. 目标与范围

对三维不可压缩湍流的多个时间帧，计算压力功率场，识别强压力功率事件和高速区域，展示两者的空间重叠关系，并分析压力功率在不同速度模平方条件下的均值。

本文件是可在新项目目录独立使用的任务说明，不依赖原目录、特定数据来源或已有代码。本文描述待实现工作，不表示程序或分析结果已经完成。

分析必须在三维数据上进行。二维切片用于辅助展示，不能代替三维事件识别、体积统计或三维叠加图。

## 2. 每帧所需输入

每个时间帧需要：

- 三维速度分量 `u, v, w`。
- 压力 `P`，或三个压力梯度分量 `dPdx, dPdy, dPdz`。
- 帧号、物理时间、坐标、网格间距及边界条件。

速度和压力梯度必须对应同一时刻、同一空间位置。明确数组轴顺序与物理坐标的对应关系，所有输入场形状一致。

这里采用单位密度压力 `P = p/rho`；如果输入是物理压力 `p`，恒密度情况下应先除以密度。若输入已无量纲化，记录其定义。

若已有压力梯度，直接复用并记录其求导方式；若只有压力，按数据边界条件计算梯度。周期均匀网格优先采用谱求导；如使用有限差分，记录阶数、间距与边界处理。非周期子区域不能直接当作周期域做 FFT。若压力及其梯度均缺失，应报告缺少输入，不默认填零。

## 3. 核心物理量

压力功率定义为：

\[
q(\mathbf{x},t)=-\mathbf{u}\cdot\nabla P
=-(uP_x+vP_y+wP_z).
\]

`q > 0` 表示压力项对局部单位质量动能产生正贡献；它不等于所有作用共同导致的净加速。

速度模平方记为 `u2`，文中用 `s` 表示，避免与 x 方向速度分量 `u` 混淆：

\[
s=u^2+v^2+w^2.
\]

每帧独立计算空间统计量：

\[
q_{\mathrm{rms}}(t)=\sqrt{\langle q^2\rangle_V},
\qquad s_{\mathrm{mean}}(t)=\langle s\rangle_V.
\]

这里 RMS 不减去均值。默认对均匀网格使用等权空间平均；非均匀网格需改用单元体积加权，并同步调整下文概率和条件统计。

实现可复用函数，至少返回 `q, u2, q_rms, u2_mean`。采用数组运算，不逐网格点执行 Python 循环。

## 4. 事件与区域定义

### 4.1 强压力功率事件

默认研究正事件：

\[
\mathcal A_\alpha=\{\mathbf{x}:q>\alpha q_{\mathrm{rms}}\}.
\]

集中配置 `event_mode`，支持：

| 模式 | 判断条件 |
|---|---|
| `positive`，默认 | `q > alpha * q_rms` |
| `negative` | `q < -alpha * q_rms` |
| `absolute` | `abs(q) > alpha * q_rms` |

### 4.2 高速区域

\[
\mathcal B_\beta=\{\mathbf{x}:s>\beta\langle s\rangle_V\}.
\]

阈值作用于速度模平方，不是速度模。

### 4.3 交集

\[
\mathcal I_{\alpha,\beta}=\mathcal A_\alpha\cap\mathcal B_\beta.
\]

采用严格不等号；归一化始终使用当前帧的空间统计量。掩膜使用布尔数组。

## 5. 逐帧诊断与重叠统计

每帧记录：

```text
frame, time
q_min, q_max, q_mean, q_rms
u2_min, u2_max, u2_mean
fraction(q > 0)
```

对每个 alpha、beta 和它们的全部组合计算：

\[
f_\alpha=|\mathcal A_\alpha|/N,
\quad g_\beta=|\mathcal B_\beta|/N,
\quad h_{\alpha,\beta}=|\mathcal I_{\alpha,\beta}|/N.
\]

其中 `N` 是分析体积中的网格点总数，均匀网格下这些值为体积占比。

另计算：

\[
P(\mathcal A_\alpha\mid\mathcal B_\beta)
=|\mathcal I_{\alpha,\beta}|/|\mathcal B_\beta|,
\]

\[
P(\mathcal B_\beta\mid\mathcal A_\alpha)
=|\mathcal I_{\alpha,\beta}|/|\mathcal A_\alpha|.
\]

分母为零时保存 `NaN` 并保留原始点数，不将未定义概率写成零。所有诊断与统计保存为 CSV，注明帧号、时间、阈值和事件模式。

## 6. 每帧必须生成的图

### A. 压力功率场切片

绘制经过体积中心的 XY、XZ、YZ 三个正交切片。

- 使用以零为中心的发散色图。
- 同一帧三个切片共用对称色限，默认取完整场 `abs(q)` 的 99.5 百分位。
- 标明帧号、时间、`q_rms`、切片位置和物理坐标。
- 零场或退化色限需单独处理。

### B. 多 alpha 的三维压力功率事件区域

展示不同 alpha 下 `A_alpha` 的三维空间范围，采用等值面、体渲染或等价的三维区域表示。可以逐阈值输出，也可以制作多面板对比。各图保持相同空间范围、坐标比例与相机视角。

### C. 多 beta 的三维高速区域

按相同要求展示 `B_beta`，与压力事件图使用一致的坐标系。

### D. 两类区域的三维半透明叠加

这是必需输出。对每个选定的 `(alpha, beta)`，在同一三维图中叠加 `A_alpha` 和 `B_beta`。

- 两类区域采用不同颜色，均使用半透明显示，透明度参数可从 `0.25...0.45` 开始调整。
- 两者的空间轴和相机必须一致。
- 图例写明事件模式及两个阈值，能辨别区域的重叠关系。
- 可选用第三种表示突出交集，但需独立标注。
- 默认绘制全部 alpha/beta 组合；提供 `overlay_pairs` 时只绘制指定组合。
- 不用数百万散点代替清晰的区域表达。

若采用交互式绘图库，保存可独立打开的 HTML；支持时另存 PNG。绘图可降采样，但必须记录倍率，所有数值统计仍使用完整分析网格。

## 7. 条件均值 ⟨q | u²⟩

计算的是分箱条件期望，不是联合概率密度。对速度模平方落在箱 `B_k` 中的点：

\[
\langle q\mid s\in B_k\rangle
=\frac{\sum_{s(\mathbf{x})\in B_k}q(\mathbf{x})}{N_k}.
\]

主图使用归一化坐标：

\[
X=s/\langle s\rangle_V,
\qquad Y=\langle q\mid s\rangle/q_{\mathrm{rms}}.
\]

要求：

1. 默认 60 个箱，`MIN_BIN_COUNT=100`。
2. 使用稳健分箱，避免绝对最大值导致大部分尾部箱为空。
3. 多帧必须使用同一套归一化 `X` 箱边界。可配置固定上界；或先逐帧预扫描 `X` 的 99.9 百分位，取这些分位数的最大值作为共同上界，再进行正式分析。
4. 记录每帧超过分箱上界的点数与占比，明确箱边界约定，最后一个箱包含右端点。
5. 低样本数箱在图中屏蔽，CSV 保留计数和有效性标记；空箱条件均值为 `NaN`。
6. 图中加入水平零线、明确轴标签、帧号和时间，默认不平滑。
7. 同时保存未归一化的条件均值及该帧对应的原始 `s` 箱坐标。

每个箱至少保存：

```text
bin_left, bin_right, bin_center       # 归一化 X 坐标
u2_bin_left, u2_bin_right, u2_bin_center
count, probability, valid
conditional_q, conditional_q_normalized
```

`probability = count / N`，以完整分析网格为分母，不对截断后区间重新归一化。若 `q_rms` 或 `u2_mean` 为零，明确记录归一化不可用，不能用任意小数代替后生成常规曲线。

## 8. 跨帧统计

处理完所选帧后输出：

- 各帧归一化条件均值曲线，用透明细线展示帧间变化。
- 每个共同箱内的等权帧均值与帧间标准差带，保存有效帧数；只对通过样本数要求的帧进行汇总。
- 只有一帧有效时不绘制帧间标准差带。
- alpha 事件体积占比随阈值的时间平均曲线。
- beta 高速区域体积占比随阈值的时间平均曲线。
- 交集体积占比的 alpha/beta 热图，以及两种条件重叠概率的汇总。

可额外计算按样本数加权的 pooled 条件统计，但必须单独标注，不能称为等权帧均值。时间汇总默认对所选帧等权；若改用时间间隔加权，需明确记录。

## 9. 配置与批处理

提供统一配置，至少包含：

```python
ALPHAS = [1.0, 2.0, 3.0, 4.0]
BETAS = [1.0, 1.5, 2.0, 3.0]
EVENT_MODE = "positive"

# 显式帧列表或 start/stop/step，二选一。
FRAMES = [0, 1, 2]  # 示例，需按实际输入设置
# FRAME_START = 0
# FRAME_STOP = 3    # 不包含 stop
# FRAME_STEP = 1

N_CONDITIONAL_BINS = 60
MIN_BIN_COUNT = 100
CONDITIONAL_PERCENTILE = 99.9
OVERLAY_PAIRS = None  # 默认绘制全部组合
VISUALIZATION_STRIDE = 1
OUTPUT_ROOT = "qpower_analysis/output"
```

提供一个高层运行入口，由配置控制整个批处理过程，不能要求用户逐帧修改代码。帧号只作为标识，物理时间从输入元数据读取。

默认逐帧加载、计算、绘图、保存并释放临时数组，不同时保留所有完整三维帧。统计覆盖全部 alpha/beta 组合，`OVERLAY_PAIRS` 只影响绘图。

遇到损坏或缺失帧时，默认停止并报告帧号与原因；可选继续模式必须记录失败列表，禁止静默跳过。

## 10. 输出与可复现性

每次运行使用独立时间戳目录，或要求显式覆盖选项，禁止静默覆盖已有分析。

```text
qpower_analysis/output/<run_id>/
├── config_used.json
├── run_metadata.json
├── run_summary.csv
├── threshold_statistics.csv
├── overlap_statistics.csv
├── aggregate/
│   ├── conditional_q_given_u2_all_frames.png
│   ├── conditional_q_given_u2_ensemble.png
│   ├── conditional_q_given_u2_ensemble.csv
│   ├── alpha_event_fraction.png
│   ├── beta_volume_fraction.png
│   └── overlap_fraction_alpha_beta.png
└── frame_000000/
    ├── frame_summary.csv
    ├── qpower_slices.png
    ├── conditional_q_given_u2.png
    ├── conditional_q_given_u2.csv
    ├── alpha_events/
    ├── beta_events/
    └── overlays/
        └── alpha_2.0_beta_1.5.html
```

保存实际配置、时间戳、代码版本（若可用）、输入标识、所选帧和时间、网格与边界、压力定义、求导方法、共同箱边界、归一化规则以及可视化降采样倍率。

## 11. 验证与执行顺序

先完成轻量测试，再运行 1～3 帧检查，通过后才处理全部所选帧。

| 测试 | 验收要求 |
|---|---|
| q 代数 | `u=1,v=2,w=3`，`Px=4,Py=5,Pz=6` 时 `q=-32` |
| 梯度 | 如自行求导，用解析场验证三轴导数、符号、坐标与边界处理 |
| 事件掩膜 | 小数组手工核对三种模式、严格阈值和高速区域 |
| 交集与概率 | 核对交集、占比、条件概率及空集合 |
| 条件均值 | 手工用例验证分箱、端点、低样本箱与尾部占比 |
| 跨帧汇总 | 验证共同箱、有效帧数、等权帧均值与 pooled 统计的区别 |
| 异常输入 | 缺失帧、非有限值、形状不一致及零归一化都有明确处理 |

首轮实际数据检查包括：压力梯度数值合理，`q` 正负分布与 `q_rms` 有记录，阈值增大时事件占比不增加，交集占比不超过任一单独区域占比，三维叠加确为半透明，坐标比例正确，条件箱样本数足够，内存不随已处理完整帧数量累积。

## 12. 本阶段不实现的内容

本阶段仅完成场、阈值区域、重叠和条件统计。暂不实现连通域对象识别、小连通域删除、对象中心、惯性张量、主轴、旋转对齐、尺度归一化、对象周围条件结构平均、时间追踪、寿命统计或压力 Hessian 分析。

代码保持模块化，后续可以在现有事件掩膜与统计结果上扩展上述功能。
