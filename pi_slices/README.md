# Pi 正交切片三维图

本目录从正式结果的完整域 `pi[z,y,x]` 中读取两个或三个正交平面，在三维坐标中绘制 Pi
分布。只读取并降采样所选二维切片，不扫描或复制完整 `1024³` 数组。静态 PNG 按
`D:/Xingqun_Gao/slice.png` 的版式输出：白底、网格索引坐标、红白蓝对称色标、斜视角和
左上角面板标记；同时保留可旋转的交互式 HTML。

默认设置：

- YZ 面：`x-index=512`；
- XZ 面：`y-index=512`；
- 面内每 4 个格点取 1 点，即每个平面显示 `256×256` 点；
- 使用全部所选切片合并后的 `|Pi|` 99% 分位数作为关于 0 对称的色限；
- 符号与 GUI 一致：`Pi=tau:S`，正值为 backscatter，负值为 forward cascade。

采样会额外保留全域两端索引 `0/1023`，并把另一平面的法向索引强制加入当前平面的
面内采样。因此即使切片索引不能被 `sample-step` 整除（例如 150），任意两面的公共交线仍由
完全相同的原始 Pi 格点组成。所有面共用同一个 `Normalize`、colormap 和色标范围，交线上
相同 Pi 值得到完全相同的 RGBA 色号。

静态 PNG 会把所有平面拆成小四边形并合并到同一个 3D collection，所有面片按相机深度
统一排序。这样相交平面不会按“整张平面”的平均深度互相覆盖，任一局部位置都显示更靠近
视角的面片。

运行 `sigma=30`：

```powershell
.\.venv\Scripts\python.exe pi_slices\plot_orthogonal_slices.py `
  --time-index 1 --sigma-grid 30 `
  --planes yz,xy,xz --x-index 150 --y-index 150 --z-index 150 `
  --sample-step 4 --color-limit 1.5 --panel-label "(d)" `
  --config configs\pipeline.yaml
```

默认输出：

```text
pi_slices/output/<result_id>/pi_orthogonal_slices_<plane_and_index>.html
pi_slices/output/<result_id>/pi_orthogonal_slices_<plane_and_index>.png
pi_slices/output/<result_id>/pi_orthogonal_slices_<plane_and_index>.json
```

文件名包含平面及其法向索引，例如
`pi_orthogonal_slices_yz_x0150_xy_z0150_xz_y0150.png`，因此不同切片不会互相覆盖。如果同一文件正被
Windows 图片查看器占用，程序会自动写成 `_1`、`_2` 等备用名称。

PNG 是参考图风格的静态图；HTML 可旋转、缩放和查看每个采样点。HTML 中的黑线是两两
平面的公共交线。静态图坐标使用原始网格索引，HTML 坐标使用物理区间 `[0,2*pi)`。

## 自定义平面

`--planes` 从 `xy,xz,yz` 中选择两个或三个不同平面。每个平面的位置由其法向索引控制：

| 平面 | 法向位置参数 |
|---|---|
| `xy` | `--z-index` |
| `xz` | `--y-index` |
| `yz` | `--x-index` |

没有给定的索引默认为对应方向中点。示例：在 `z=256` 的 XY 面和 `x=700` 的 YZ 面
绘图，并进一步降采样：

```powershell
.\.venv\Scripts\python.exe pi_slices\plot_orthogonal_slices.py `
  --time-index 1 --sigma-grid 30 `
  --planes xy,yz --z-index 256 --x-index 700 `
  --sample-step 8 --config configs\pipeline.yaml
```

可用 `--color-limit VALUE` 明确指定对称色限；它会覆盖 `--color-percentile`。使用常见
LES 符号时添加 `--sign-convention les`，此时图中显示
`Pi_LES=-stored pi=-tau:S`，正值为 forward cascade。`--result-dir` 可直接指定任一已完成
的结果目录，并覆盖 `--time-index/--sigma-grid` 的路径选择。`--png-dpi` 控制静态图分辨率，
`--panel-label` 可替换或用空字符串移除左上角标记；`--view-elevation` 和
`--view-azimuth` 可调整静态三维视角。静态图默认使用 `--projection orthographic`，并保持
x/y/z 三轴严格 `1:1:1`，所以各平面相同的网格范围不会因透视而显得大小不同；需要透视
缩短效果时可改为 `--projection perspective`。
