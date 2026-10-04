# QPower 图片审查

现有 7 张 PNG 已集中复制到本目录；原有 PNG 保留。已删除 qpower_analysis 下的 6 个 PDF。

打开 [index.html](index.html) 可按顺序审查全部图片，点击图片查看原尺寸。所有图片已嵌入 HTML，单独复制或发送该文件即可离线浏览，无需附带 PNG 文件。

复制图片逐一核对 SHA-256，与来源文件一致。来源映射见 manifest.csv，已删除 PDF 清单见 deleted_pdfs.json。

- [01_qpower_slices.png](01_qpower_slices.png)：压力功率三正交切片。q=-u·∇P 的 XY、XZ、YZ 切片。
- [02_conditional_q_given_u2.png](02_conditional_q_given_u2.png)：初始条件均值：q 随速度能量变化。早期图，横轴为 u²/⟨u²⟩，上界按 99.9% 分位截断；与后续全尾部图范围不同。
- [03_frame_000001_q_given_u2.png](03_frame_000001_q_given_u2.png)：全尾部：给定速度能量的 q。横轴 u²/⟨u²⟩；上下 2.5% 尾部与中间 95% 分开显示，阴影为箱内中间 50% 点值。
- [04_frame_000001_u2_given_q.png](04_frame_000001_u2_given_q.png)：全尾部：给定 q 的速度能量。横轴 q/q_rms，包含正 q、负 q 和零附近；阴影为箱内中间 50% 点值。
- [05_angle_relationships.png](05_angle_relationships.png)：强正功率、高速度交集的夹角关系。仅 q/q_rms>1 且 u²/⟨u²⟩>1；夹角为 u 与 −∇P 的夹角。平均 45.22°，图中没有 q≈0 的分箱。
- [07_factor_cdfs.png](07_factor_cdfs.png)：q≈0 点的速度、梯度与方向投影分布。比较全域、q≈0 最高分箱（−0.03921 ≤ q/q_rms < 0.02203）与 |q|<0.01q_rms；纵轴为各集合内部累计比例。
- [08_sign_split_angle_check.png](08_sign_split_angle_check.png)：零附近正、负 q 的角度对照。分别统计 0<q/q_rms<0.01 和 −0.01<q/q_rms<0，不限制速度；绿色为原交集的最左可见分箱。夹角为 u 与 −∇P 的夹角。
