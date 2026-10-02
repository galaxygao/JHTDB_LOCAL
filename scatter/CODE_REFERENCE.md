# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## scatter/__init__.py

[完整源码](__init__.py)

此入口只包含导入、常量或顶层调用。

## scatter/plot_exact_scatter.py

[完整源码](plot_exact_scatter.py)

依赖：

```python
from __future__ import annotations
import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.store import open_complete_result, spatial_slices
```

模块常量/配置：

```python
AXIS_KEYS = ('work_full', 's_bar', 'pi_les')
AXIS_LABELS = ('W_full', 'S̄', 'Π_LES')
REQUIRED_FIELDS = ('s_bar', 'pi', 'work_full', 'work_resolved')
DEFAULT_BINS = 64
DEFAULT_BINS_2D = 256
```

### `FeatureChunk`

[实现：第 34 行](plot_exact_scatter.py#L34)

```python
class FeatureChunk()
```

字段/默认值：

```python
spatial_slices_zyx: tuple[slice, slice, slice]
s_bar: np.ndarray
pi_les: np.ndarray
work_full: np.ndarray
work_resolved: np.ndarray
delta_w: np.ndarray
```

One spatial chunk of exact, flattened feature values.

### `FeatureChunk.point_count`

[实现：第 45 行](plot_exact_scatter.py#L45)

```python
def FeatureChunk.point_count(self) -> int
```

调用：`int`

### `FeatureChunk.matrix`

[实现：第 48 行](plot_exact_scatter.py#L48)

```python
def FeatureChunk.matrix(self, *, dtype: Any=np.float32) -> np.ndarray
```

Return an ``N x 3`` matrix for clustering/classification code.

调用：`np.column_stack`, `np.column_stack((self.work_full, self.s_bar, self.pi_les)).astype`

### `FeatureChunk.matrix_with_delta_w`

[实现：第 57 行](plot_exact_scatter.py#L57)

```python
def FeatureChunk.matrix_with_delta_w(self, *, dtype: Any=np.float32) -> np.ndarray
```

Return all four physical features, including derived delta-W.

调用：`np.column_stack`, `np.column_stack((self.work_full, self.s_bar, self.pi_les, self.delta_w)).astype`

### `_validate_source`

[实现：第 65 行](plot_exact_scatter.py#L65)

```python
def _validate_source(root: Any) -> tuple[tuple[int, int, int], tuple[int, int, int]]
```

调用：`', '.join`, `RuntimeError`, `any`, `int`, `len`, `np.dtype`, `tuple`

显式异常：

```python
RuntimeError('S_bar, pi and work fields must be float32')
RuntimeError('S_bar, pi and work fields must have one identical 3-D shape')
RuntimeError(f"result is missing fields: {', '.join(missing)}")
```

### `iter_exact_feature_chunks`

[实现：第 80 行](plot_exact_scatter.py#L80)

```python
def iter_exact_feature_chunks(root: Any) -> Iterator[FeatureChunk]
```

Yield every point exactly once with three independent features.

The stored pipeline variable ``pi`` is ``tau:S``.  The LES-forward flux used
on the second axis is therefore ``Pi_LES = -pi``.

调用：`FeatureChunk`, `ValueError`, `_validate_source`, `any`, `np.all`, `np.asarray`, `np.asarray(root['pi'][key], dtype=np.float32).ravel`, `np.asarray(root['s_bar'][key], dtype=np.float32).ravel`, `np.asarray(root['work_full'][key], dtype=np.float32).ravel`, `np.asarray(root['work_resolved'][key], dtype=np.float32).ravel`, `np.isfinite`, `spatial_slices`

显式异常：

```python
ValueError(f'non-finite value found in spatial chunk {key}')
```

### `_manifest_axis_bounds`

[实现：第 110 行](plot_exact_scatter.py#L110)

```python
def _manifest_axis_bounds(result_dir: Path) -> tuple[tuple[float, float], ...] | None
```

Use committed exact extrema for the three independent axes.

调用：`all`, `float`, `json.loads`, `manifest.get`, `manifest_path.is_file`, `manifest_path.read_text`, `math.isfinite`

### `exact_feature_bounds`

[实现：第 137 行](plot_exact_scatter.py#L137)

```python
def exact_feature_bounds(root: Any, *, committed_bounds: tuple[tuple[float, float], ...] | None=None) -> tuple[tuple[float, float], ...]
```

Return exact extrema for all three axes using a chunked full scan.

调用：`RuntimeError`, `ValueError`, `all`, `enumerate`, `float`, `iter_exact_feature_chunks`, `len`, `math.isfinite`, `max`, `min`, `np.all`, `np.full`, `np.isfinite`, `tuple`, `values.max`, `values.min`, `zip`

显式异常：

```python
RuntimeError('could not determine finite feature bounds')
ValueError('committed feature bounds must be finite')
ValueError('committed_bounds must contain all three axis bounds')
```

### `_edges`

[实现：第 171 行](plot_exact_scatter.py#L171)

```python
def _edges(low: float, high: float, bins: int) -> np.ndarray
```

调用：`ValueError`, `abs`, `max`, `np.linspace`

显式异常：

```python
ValueError('feature bound maximum is smaller than minimum')
```

### `exact_density_histogram`

[实现：第 181 行](plot_exact_scatter.py#L181)

```python
def exact_density_histogram(root: Any, bounds: Sequence[tuple[float, float]], *, bins: int=DEFAULT_BINS) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray], int]
```

Compatibility wrapper returning only the exact 3-D histogram.

调用：`exact_density_histograms`

### `exact_density_histograms`

[实现：第 195 行](plot_exact_scatter.py#L195)

```python
def exact_density_histograms(root: Any, bounds: Sequence[tuple[float, float]], *, bins_3d: int=DEFAULT_BINS, bins_2d: int=DEFAULT_BINS_2D) -> tuple[np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray], np.ndarray, tuple[np.ndarray, np.ndarray], int]
```

Count every point into independent exact 3-D and 2-D histograms.

调用：`RuntimeError`, `ValueError`, `_edges`, `chunk_density_2d.astype`, `chunk_density_3d.astype`, `density_2d.sum`, `density_3d.sum`, `float`, `int`, `iter_exact_feature_chunks`, `len`, `np.histogram2d`, `np.histogramdd`, `np.zeros`, `tuple`

显式异常：

```python
RuntimeError(f'exact-density closure failed: 3-D={counted_3d}, 2-D={counted_2d}, source={point_count}')
ValueError('2-D bins must be between 2 and 4096')
ValueError('3-D bins must be between 2 and 256')
ValueError('three feature bounds are required')
```

### `probability_density`

[实现：第 250 行](plot_exact_scatter.py#L250)

```python
def probability_density(counts: np.ndarray, edges: Sequence[np.ndarray]) -> tuple[np.ndarray, float]
```

Normalize integer histogram counts to a Cartesian PDF.

调用：`ValueError`, `counts.astype`, `counts.sum`, `float`, `int`, `len`, `np.any`, `np.asarray`, `np.diff`, `np.multiply.outer`, `np.sum`, `tuple`

显式异常：

```python
ValueError('PDF edges must be strictly increasing')
ValueError('cannot normalize an empty histogram')
ValueError('histogram rank and number of edge arrays differ')
ValueError('histogram shape does not match its edge arrays')
```

### `top_pdf_mask`

[实现：第 273 行](plot_exact_scatter.py#L273)

```python
def top_pdf_mask(pdf: np.ndarray, percentile: float=95.0) -> tuple[np.ndarray, float]
```

Select occupied bins at or above the requested PDF percentile.

调用：`ValueError`, `float`, `np.percentile`

显式异常：

```python
ValueError('PDF contains no occupied bins')
ValueError('PDF percentile must lie strictly between 0 and 100')
```

### `pdf_display_scale`

[实现：第 285 行](plot_exact_scatter.py#L285)

```python
def pdf_display_scale(pdf: np.ndarray, occupied_from_counts: np.ndarray, *, lower_percentile: float=1.0, upper_percentile: float=99.0) -> tuple[np.ndarray, float, float]
```

Map occupied PDF values to [0, 1] on a robust log10 color scale.

调用：`ValueError`, `float`, `np.any`, `np.clip`, `np.full`, `np.log10`, `np.percentile`

显式异常：

```python
ValueError('PDF and count-derived occupancy masks must match')
ValueError('cannot scale a PDF without occupied count bins')
```

### `nice_axis_limits`

[实现：第 310 行](plot_exact_scatter.py#L310)

```python
def nice_axis_limits(low: float, high: float, *, padding_fraction: float=0.05, target_intervals: int=6) -> tuple[float, float]
```

Return zero-aware, padded limits rounded outward to a 1/2/5 step.

调用：`ValueError`, `abs`, `float`, `int`, `math.ceil`, `math.floor`, `math.isfinite`, `math.log10`, `max`, `min`

显式异常：

```python
ValueError('axis extrema must be finite and ordered')
```

### `_pdf_colorbar`

[实现：第 348 行](plot_exact_scatter.py#L348)

```python
def _pdf_colorbar(title: str, log_min: float, log_max: float, x: float, *, y: float, length: float) -> dict[str, Any]
```

调用：`np.linspace`, `ticks.tolist`

### `density_figure`

[实现：第 371 行](plot_exact_scatter.py#L371)

```python
def density_figure(density: np.ndarray, edges: Sequence[np.ndarray], *, density_2d: np.ndarray | None=None, edges_2d: Sequence[np.ndarray] | None=None, title: str) -> go.Figure
```

Create equal-scale 3-D/2-D densities with physical boundary planes.

调用：`RuntimeError`, `ValueError`, `_pdf_colorbar`, `add_plane`, `density.ravel`, `density.sum`, `display_3d.ravel`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `float`, `go.Heatmap`, `go.Scatter`, `go.Scatter3d`, `go.Surface`, `go.Volume`, `len`, `limit_text`, `list`, `make_subplots`, `max`, `min`, `nice_axis_limits`, `np.asarray`, `np.clip`, `np.column_stack`, `np.isclose`, `np.linspace`, `np.log10`, `np.meshgrid`, `np.stack`, `np.where`, `np.where(top_3d, display_3d, -1.0).ravel`, `np.zeros_like`, `pdf_3d.ravel`, `pdf_display_scale`, `probability_density`, `range_text`, `top_pdf_mask`, `tuple`, `x_grid.ravel`, `y_grid.ravel`, `z_grid.ravel`

显式异常：

```python
RuntimeError(f'2-D PDF normalization failed: integral={integral_2d}')
RuntimeError(f'3-D PDF normalization failed: integral={integral_3d}')
ValueError('2-D density shape does not match its axis edges')
ValueError('3-D density shape does not match its axis edges')
```

### `density_figure.range_text`

[实现：第 423 行](plot_exact_scatter.py#L423)

```python
def density_figure.range_text(edge: np.ndarray) -> str
```

调用：`float`

### `density_figure.limit_text`

[实现：第 426 行](plot_exact_scatter.py#L426)

```python
def density_figure.limit_text(limits: tuple[float, float]) -> str
```

### `density_figure.add_plane`

[实现：第 515 行](plot_exact_scatter.py#L515)

```python
def density_figure.add_plane(x: np.ndarray, y: np.ndarray, z: np.ndarray, *, name: str, color: str) -> None
```

调用：`figure.add_trace`, `go.Surface`, `np.zeros_like`

### `write_outputs`

[实现：第 787 行](plot_exact_scatter.py#L787)

```python
def write_outputs(output_dir: Path, density: np.ndarray, edges: Sequence[np.ndarray], metadata: dict[str, Any], *, density_2d: np.ndarray | None=None, edges_2d: Sequence[np.ndarray] | None=None) -> tuple[Path, Path, Path]
```

调用：`density.sum`, `density_figure`, `figure.write_html`, `json.dumps`, `metadata_path.write_text`, `np.savez_compressed`, `output_dir.mkdir`, `probability_density`

### `build_parser`

[实现：第 836 行](plot_exact_scatter.py#L836)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`argparse.ArgumentParser`, `parser.add_argument`

### `main`

[实现：第 866 行](plot_exact_scatter.py#L866)

```python
def main(argv: Sequence[str] | None=None) -> int
```

调用：`Path`, `Path(__file__).resolve`, `RuntimeError`, `_manifest_axis_bounds`, `_validate_source`, `build_parser`, `build_parser().parse_args`, `cfg.physical_time`, `cfg.result_id`, `cfg.result_path`, `density.sum`, `density_2d.sum`, `exact_density_histograms`, `exact_feature_bounds`, `float`, `int`, `list`, `load_config`, `nice_axis_limits`, `np.count_nonzero`, `np.prod`, `open_complete_result`, `pdf_display_scale`, `print`, `probability_density`, `str`, `top_pdf_mask`, `write_outputs`, `zip`

显式异常：

```python
RuntimeError(f'exact scatter requires the full domain: source={shape}, expected={cfg.full_shape_zyx}')
RuntimeError(f'point-count closure failed: visited={point_count}, expected={expected_count}')
```

