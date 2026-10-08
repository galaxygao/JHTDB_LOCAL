# QPower 图片审查

现有 9 张 PNG 已集中复制到本目录；原有 PNG 保留。已删除 qpower_analysis 下的 6 个 PDF。

打开 [index.html](index.html) 可按顺序审查全部图片，点击图片查看原尺寸。所有图片已嵌入 HTML，单独复制或发送该文件即可离线浏览，无需附带 PNG 文件。

复制图片逐一核对 SHA-256，与来源文件一致。来源映射见 manifest.csv，已删除 PDF 清单见 deleted_pdfs.json。

- [01_qpower_slices.png](01_qpower_slices.png)：压力功率三正交切片。q=-u·∇P 的 XY、XZ、YZ 切片。
- [02_conditional_q_given_u2.png](02_conditional_q_given_u2.png)：初始条件均值：q 随速度能量变化。早期图，横轴为 u²/⟨u²⟩，上界按 99.9% 分位截断；与后续全尾部图范围不同。
- [03_frame_000001_q_given_u2.png](03_frame_000001_q_given_u2.png)：全尾部：给定速度能量的 q。横轴 u²/⟨u²⟩；上下 2.5% 尾部与中间 95% 分开显示，阴影为箱内中间 50% 点值。
- [04_frame_000001_u2_given_q.png](04_frame_000001_u2_given_q.png)：全尾部：给定 q 的速度能量。横轴 q/q_rms，包含正 q、负 q 和零附近；阴影为箱内中间 50% 点值。
- [05_angle_relationships.png](05_angle_relationships.png)：强正功率、高速度交集的夹角关系。仅 q/q_rms>1 且 u²/⟨u²⟩>1；夹角为 u 与 −∇P 的夹角。平均 45.22°，图中没有 q≈0 的分箱。
- [07_factor_cdfs.png](07_factor_cdfs.png)：q≈0 点的速度、梯度与方向投影分布。比较全域、q≈0 最高分箱（−0.03921 ≤ q/q_rms < 0.02203）与 |q|<0.01q_rms；纵轴为各集合内部累计比例。
- [08_sign_split_angle_check.png](08_sign_split_angle_check.png)：零附近正、负 q 的角度对照。分别统计 0<q/q_rms<0.01 和 −0.01<q/q_rms<0，不限制速度；绿色为原交集的最左可见分箱。夹角为 u 与 −∇P 的夹角。

- [09_gradient_given_q.png](09_gradient_given_q.png)：压力梯度幅值随 q 的变化。横轴 q/q_rms，纵轴 |∇P|/∇P_rms；曲线为每个 q 分箱内的梯度幅值均值，阴影为箱内 25%–75% 点值范围（直方图近似）。使用全部 1024³ 格点，包含负 q、零附近和正 q；上下 2.5% 尾部与中间 95% 分开显示。空心点表示少于 100 个格点的分箱。P=p/ρ，与现有数据定义一致。

- [10_structure_count_vs_r.png](10_structure_count_vs_r.png)：α=β=1 强事件的结构数量随空间距离 r 的变化。只在 q/q_rms>1 且 u²/⟨u²⟩>1 的交集点之间连边；两点周期欧氏距离不超过 r 时合并。曲线给出 N(r)=β₀(r)，并显示最大结构占比及至少 10、100、1000 个点的结构数。
