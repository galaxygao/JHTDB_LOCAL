# Exact Cartesian density views

`plot_exact_scatter.py` 对指定 frame 和 sigma 的完整 `1024^3` 场逐块读取，不进行抽样。

三维密度云使用三个独立坐标：

- x：`W_full`（结果中的 `work_full`）
- y：`S̄`（结果中的 `s_bar`）
- z：`Pi_LES = -pi = -tau:S`

二维密度图使用 `(S̄, Pi_LES)`，并叠加红色虚线
`delta W = S̄ + Pi_LES = 0`。另外两个物理量可由独立坐标恢复：

```text
delta W = S̄ + Pi_LES
W_res   = W_full - S̄ - Pi_LES
```

三维图显式绘制经过原点的三条 regime 边界平面：

- `W_full = 0`，即 `x = 0`
- `delta W = 0`，即 `y + z = 0`
- `W_res = 0`，即 `x - y - z = 0`

图中还绘制穿过原点的 x/y/z 三条坐标轴。三个物理量分别使用自身的精确最小值和最大值，
三维图使用 `aspectmode=data`，所以不同轴上的一个数值单位具有相同视觉长度。二维图独立
累计更高分辨率的整数直方图，并锁定 1:1 坐标比例。显示范围在真实极值外增加5%留白，再按
数据数量级向外取到 `1/2/5 × 10^n` 的易读刻度。坐标轴标题同时标注 `data=[精确极值]` 和
`lim=[显示边界]`。

HTML 中两张图上下排列，3D 占约75%的绘图区高度，2D 占约25%，中间保留13%的垂直间距。
3D PDF 色条贴近云图右侧；3D、2D 的 top-5% 开关分别放在对应面板右上角。

每个全域格点都恰好进入一个三维 Cartesian bin 和一个二维 bin。程序分别进行严格计数闭合
检查：两份直方图的计数和都必须等于源数据格点数。二维密度直接由原始格点独立累计，不是
从较粗的三维 bins 投影，因此同样包含全部格点且可以使用更高分辨率。

图中颜色显示的是概率密度函数（PDF），不是原始 `points/bin`：

```text
PDF_3D = count / (N * dW_full * dS_bar * dPi_LES)
PDF_2D = count / (N * dS_bar * dPi_LES)
```

程序分别检查三维与二维 PDF 在各自特征空间上的数值积分等于 1。悬停信息同时保留该 bin
的原始格点计数和 PDF。显示色标使用非零 PDF 的 `log10` 尺度，并按非零区域的第1至第99
百分位映射颜色；colorbar 刻度仍标注实际 PDF 数值。这个变换只影响颜色，不改变保存的 PDF。

空区域在计算 PDF 之前严格通过整数 `count == 0` 判断。3D 中为空 bin 赋予低于可见阈值的
哨兵值，以维持 Plotly Volume 所需的规则网格；2D 中为空 bin 设为 `NaN`。因此零计数 bin
不显示，而非零 PDF 不会被误删。

3D、2D 面板分别带有 top 5% ON/OFF 按钮。打开后，所有非空 bin 中 PDF 位于第95百分位
及以上的区域会用红色覆盖标注；三维与二维使用各自的 PDF 阈值。

## 运行

在项目根目录执行，例如绘制 frame 1、sigma 20：

```powershell
.\.venv\Scripts\python.exe scatter\plot_exact_scatter.py `
  --time-index 1 `
  --sigma-grid 20 `
  --bins 64 `
  --bins-2d 256 `
  --config configs\pipeline.yaml
```

输入结果的 filter type 和 smooth-sharp 宽度由配置文件决定；脚本会使用与配置完全一致的
`result_id`。要分析另一类滤波结果，请传入对应的 YAML 配置副本，不要只修改输出目录名。

输出默认位于 `scatter/output/<result_id>/`：

- `exact_density_views.html`：三维密度云和二维密度图
- `exact_density.npz`：精确整数计数、归一化 PDF 及对应 bin edges
- `metadata.json`：轴定义、派生关系、范围、格点总数和闭合信息

`--bins` 控制三维密度每条轴的分箱数，可取 2--256。`--bins-2d` 独立控制二维密度每条轴
的分箱数，可取 2--4096，默认 256。两个参数都只改变显示分辨率，不改变参与统计的格点数。
二维计数由源数据直接累计，不再由较粗的三维密度投影获得。

## 后续分类

不要从 HTML 或密度 bin 反推训练数据。后续 DBSCAN 或 decision tree 应直接导入脚本中的
`iter_exact_feature_chunks(root)`。它逐块返回未经分箱、未经抽样的 `S̄`、`Pi_LES`、
`W_full`、`W_res` 和派生的 `delta W`，每个格点恰好出现一次：

- `FeatureChunk.matrix()` 返回三个独立特征 `(W_full, S̄, Pi_LES)`。
- `FeatureChunk.matrix_with_delta_w()` 返回 `(W_full, S̄, Pi_LES, delta W)`。
