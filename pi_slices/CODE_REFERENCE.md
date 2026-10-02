# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## pi_slices/__init__.py

[完整源码](__init__.py)

此入口只包含导入、常量或顶层调用。

## pi_slices/plot_orthogonal_slices.py

[完整源码](plot_orthogonal_slices.py)

依赖：

```python
from __future__ import annotations
import argparse
import errno
import json
import math
import sys
import uuid
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Sequence
import numpy as np
import plotly.graph_objects as go
from matplotlib import colormaps
from matplotlib import pyplot as plt
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.store import open_complete_result
```

模块常量/配置：

```python
PLANE_NORMAL = {'xy': 'z', 'xz': 'y', 'yz': 'x'}
AXIS_TO_ZYX = {'x': 2, 'y': 1, 'z': 0}
```

### `PlaneSlice`

[实现：第 33 行](plot_orthogonal_slices.py#L33)

```python
class PlaneSlice()
```

字段/默认值：

```python
plane: str
normal_axis: str
index: int
coordinate: float
x: np.ndarray
y: np.ndarray
z: np.ndarray
values: np.ndarray
```

One sampled plane with physical coordinates for a Plotly surface.

### `parse_planes`

[实现：第 46 行](plot_orthogonal_slices.py#L46)

```python
def parse_planes(value: str) -> tuple[str, ...]
```

调用：`any`, `argparse.ArgumentTypeError`, `item.strip`, `item.strip().lower`, `len`, `set`, `tuple`, `value.split`

显式异常：

```python
argparse.ArgumentTypeError('--planes must contain two or three planes')
argparse.ArgumentTypeError('all selected planes must be different')
argparse.ArgumentTypeError('planes must be selected from xy, xz and yz')
```

### `_plane_index`

[实现：第 57 行](plot_orthogonal_slices.py#L57)

```python
def _plane_index(plane: str, shape_zyx: tuple[int, int, int], indices_xyz: dict[str, int | None]) -> int
```

调用：`ValueError`, `int`

显式异常：

```python
ValueError(f'--{normal}-index must be in [0, {size - 1}] for the {plane} plane')
```

### `extract_plane`

[实现：第 73 行](plot_orthogonal_slices.py#L73)

```python
def extract_plane(field: Any, plane: str, index: int, *, sample_step: int, domain_length: float, multiplier: float=1.0, include_indices_xyz: dict[str, Sequence[int]] | None=None) -> PlaneSlice
```

Read one strided plane from a ``field[z, y, x]`` array.

调用：`PlaneSlice`, `ValueError`, `any`, `float`, `hasattr`, `include_indices_xyz.get`, `indices.astype`, `int`, `len`, `math.isfinite`, `np.all`, `np.arange`, `np.asarray`, `np.concatenate`, `np.float32`, `np.full_like`, `np.isfinite`, `np.ix_`, `np.meshgrid`, `np.unique`, `orthogonal_values`, `required.extend`, `sampled_indices`, `tuple`

显式异常：

```python
ValueError('Pi must be a three-dimensional field in z,y,x order')
ValueError('domain_length must be finite and positive')
ValueError('sample_step must be positive')
ValueError(f'non-finite Pi value found on the {plane} plane')
ValueError(f'required {axis} sample index is outside [0, {size - 1}]')
ValueError(f'unknown plane: {plane}')
ValueError(f'{plane} plane index must be in [0, {normal_size - 1}]')
```

### `extract_plane.sampled_indices`

[实现：第 98 行](plot_orthogonal_slices.py#L98)

```python
def extract_plane.sampled_indices(axis: str, size: int) -> np.ndarray
```

调用：`ValueError`, `any`, `include_indices_xyz.get`, `int`, `np.arange`, `np.asarray`, `np.concatenate`, `np.unique`, `required.extend`

显式异常：

```python
ValueError(f'required {axis} sample index is outside [0, {size - 1}]')
```

### `extract_plane.orthogonal_values`

[实现：第 131 行](plot_orthogonal_slices.py#L131)

```python
def extract_plane.orthogonal_values(*selection: Any) -> np.ndarray
```

调用：`hasattr`, `np.asarray`, `np.ix_`

### `extract_orthogonal_planes`

[实现：第 170 行](plot_orthogonal_slices.py#L170)

```python
def extract_orthogonal_planes(field: Any, planes: Sequence[str], indices_xyz: dict[str, int | None], *, sample_step: int, domain_length: float, multiplier: float=1.0) -> list[PlaneSlice]
```

Extract planes while retaining every exact full-length intersection.

调用：`_plane_index`, `extract_plane`, `fixed_indices.items`, `int`, `tuple`

### `symmetric_color_limit`

[实现：第 204 行](plot_orthogonal_slices.py#L204)

```python
def symmetric_color_limit(planes: Sequence[PlaneSlice], percentile: float, explicit_limit: float | None) -> float
```

调用：`ValueError`, `absolute.max`, `float`, `math.isfinite`, `np.abs`, `np.abs(item.values).astype`, `np.abs(item.values).astype(np.float64, copy=False).ravel`, `np.concatenate`, `np.percentile`

显式异常：

```python
ValueError('--color-limit must be finite and positive')
ValueError('--color-percentile must be in (0, 100]')
ValueError('could not determine a finite Pi color limit')
```

### `_intersection_coordinates`

[实现：第 224 行](plot_orthogonal_slices.py#L224)

```python
def _intersection_coordinates(first: PlaneSlice, second: PlaneSlice, shape_zyx: tuple[int, int, int], domain_length: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]
```

调用：`next`, `np.asarray`

### `build_figure`

[实现：第 246 行](plot_orthogonal_slices.py#L246)

```python
def build_figure(planes: Sequence[PlaneSlice], *, shape_zyx: tuple[int, int, int], domain_length: float, color_limit: float, title: str, quantity_label: str) -> go.Figure
```

调用：`ValueError`, `_intersection_coordinates`, `combinations`, `figure.add_trace`, `figure.update_layout`, `first.plane.upper`, `go.Figure`, `go.Scatter3d`, `go.Surface`, `item.plane.upper`, `len`, `second.plane.upper`

显式异常：

```python
ValueError('two or three different coordinate planes are required')
```

### `build_static_figure`

[实现：第 318 行](plot_orthogonal_slices.py#L318)

```python
def build_static_figure(planes: Sequence[PlaneSlice], *, shape_zyx: tuple[int, int, int], domain_length: float, color_limit: float, panel_label: str, view_elevation: float=22.0, view_azimuth: float=55.0, projection: str='orthographic') -> Any
```

Build a publication-style PNG figure matching the slice.png layout.

调用：`Normalize`, `Poly3DCollection`, `ValueError`, `all_facecolors.append`, `all_vertices.append`, `axis.add_collection3d`, `axis.set_box_aspect`, `axis.set_proj_type`, `axis.set_xlabel`, `axis.set_xlim`, `axis.set_xticks`, `axis.set_ylabel`, `axis.set_ylim`, `axis.set_yticklabels`, `axis.set_yticks`, `axis.set_zlabel`, `axis.set_zlim`, `axis.set_zticks`, `axis.tick_params`, `axis.view_init`, `color_map`, `colorbar.ax.tick_params`, `colorbar.outline.set_edgecolor`, `colorbar.outline.set_linewidth`, `colorbar.set_ticks`, `face_values.reshape`, `figure.add_subplot`, `figure.colorbar`, `figure.subplots_adjust`, `figure.text`, `int`, `len`, `min`, `normalization`, `np.arange`, `np.concatenate`, `np.linspace`, `np.stack`, `np.stack((coordinates[:-1, :-1], coordinates[1:, :-1], coordinates[1:, 1:], coordinates[:-1, 1:]), axis=2).reshape`, `np.stack((item.x * scale['x'], item.y * scale['y'], item.z * scale['z']), axis=-1).astype`, `pane_axis.pane.set_edgecolor`, `pane_axis.pane.set_facecolor`, `plt.cm.ScalarMappable`, `plt.figure`, `scalar.set_array`, `str`

显式异常：

```python
ValueError('two or three different coordinate planes are required')
```

### `_replace_or_number`

[实现：第 429 行](plot_orthogonal_slices.py#L429)

```python
def _replace_or_number(temporary: Path, target: Path) -> Path
```

Replace target, or keep a numbered sibling when Windows has it open.

调用：`RuntimeError`, `candidate.exists`, `range`, `target.with_name`, `temporary.replace`

显式异常：

```python
RuntimeError(f'could not find an available output filename beside {target}')
```

### `_temporary_path`

[实现：第 447 行](plot_orthogonal_slices.py#L447)

```python
def _temporary_path(target: Path) -> Path
```

调用：`target.with_name`, `uuid.uuid4`

### `_atomic_json`

[实现：第 451 行](plot_orthogonal_slices.py#L451)

```python
def _atomic_json(path: Path, payload: dict[str, Any]) -> Path
```

调用：`_replace_or_number`, `_temporary_path`, `json.dumps`, `temporary.write_text`

### `visualize`

[实现：第 459 行](plot_orthogonal_slices.py#L459)

```python
def visualize(args: argparse.Namespace) -> dict[str, Path]
```

调用：`'_'.join`, `(Path('pi_slices') / 'output' / result_dir.name).resolve`, `Path`, `RuntimeError`, `_atomic_json`, `_replace_or_number`, `_temporary_path`, `args.output_dir.resolve`, `args.result_dir.resolve`, `build_figure`, `build_static_figure`, `cfg.result_path`, `extract_orthogonal_planes`, `figure.write_html`, `float`, `int`, `len`, `list`, `load_config`, `np.abs`, `np.max`, `np.min`, `np.percentile`, `open_complete_result`, `output_dir.mkdir`, `plt.close`, `static_figure.savefig`, `str`, `sum`, `symmetric_color_limit`, `tuple`

显式异常：

```python
RuntimeError(f'Pi field is not three-dimensional: {shape}')
RuntimeError(f'result has no Pi field: {result_dir}')
```

### `build_parser`

[实现：第 591 行](plot_orthogonal_slices.py#L591)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`argparse.ArgumentParser`, `parser.add_argument`

### `main`

[实现：第 636 行](plot_orthogonal_slices.py#L636)

```python
def main(argv: Sequence[str] | None=None) -> int
```

调用：`ValueError`, `build_parser`, `build_parser().parse_args`, `outputs.items`, `print`, `visualize`

显式异常：

```python
ValueError('--png-dpi must be at least 72')
ValueError('--sample-step must be positive')
```

