# α=β=2：top3 周期连通结构与封闭空腔

选择条件：q/q_rms > 2 且 u²/⟨u²⟩ > 2，正 q，严格不等式。
原始 1024³ 网格；事件点 8,023,815，占全域 0.747276%；r=Δx 时共 70,767 个周期连通结构。事件点数与原 overlap_statistics.csv 完全一致。

结构在 r=Δx 下使用周期 6 邻域；背景使用周期 26 邻域，允许对角逃逸。每个结构的外部背景均验证为超过全域一半的分量，其余背景检查周期绕行，绕行分量排除。本次没有额外绕行背景分量。

| 排名 | 结构点数 | 封闭空腔数 | 绿色点数 | 红色点数 |
|---:|---:|---:|---:|---:|
| 1 | 442,213 | 1 | 0 | 8 |
| 2 | 363,430 | 0 | 0 | 0 |
| 3 | 297,970 | 3 | 0 | 56 |

蓝色是当前结构；绿色是其封闭空腔内属于其他过阈值结构的点；红色是空腔内未同时通过两个阈值的点。外部背景不显示。

打开 [top3_cavities.html](top3_cavities.html) 离线查看。三个独立结构视图、一个合并视图，以及 rank 1 和 rank 3 的最大空腔局部视图，共六个视图；rank 2 无空腔。
全局范围统一为 [-256.5,1279.5]，主周期盒保留原坐标，面、棱、角周期延伸到 256 格的 halo。副本不参与计数；周期接合面省略内部面。可切换周期延伸并调整蓝色透明度。
三个结构均小于 200 万点，全局蓝色、红绿及空腔局部表面全部保留原始格点分辨率。局部视图按周期展开，蓝色在局部边缘裁切。preview.png 是主盒 XY 抽样投影，不表示三维空腔几何。

验证：周期闭壳识别出 1 个绿色点和 124 个红色点，开通一格通道后空腔消失；跨周期面的两格表面为 20 个三角形，没有周期接合封口。生产数据核对二进制点数、索引范围/唯一性、top3 不重叠、各通道阈值归属和逐结构全域分区守恒，见 validation.json。

## 复现

从 qpower_analysis 目录执行：

```sh
../.venv-mac/bin/python strong_event_h0.py --run-dir output/20261001T044629Z --alpha 2 --beta 2 --prepare-only
clang++ -O3 -std=c++17 scripts/visualize_h0_cavities.cpp -o .local/bin/visualize_h0_cavities
.local/bin/visualize_h0_cavities output/20261001T044629Z/strong_event_h0_alpha2_beta2/selection_mask.bits 1024 output/20261001T044629Z/strong_event_h0_alpha2_beta2/cavities_r1
MPLCONFIGDIR=/tmp/h0-mpl ../.venv-mac/bin/python scripts/render_h0_cavities.py output/20261001T044629Z/strong_event_h0_alpha2_beta2/cavities_r1
```

二进制点表为 uint32 C-order z,y,x 平坦索引；selection.json 保存阈值和数据来源。此流程计算 r=Δx 的 top3 cavity；距离变化的完整 H₀ 滤波需另行运行 strong_event_h0.py（去掉 --prepare-only）。
