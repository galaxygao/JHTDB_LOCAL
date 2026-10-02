# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## pi_pdf/__init__.py

[完整源码](__init__.py)

此入口只包含导入、常量或顶层调用。

## pi_pdf/plot_pi_pdf.py

[完整源码](plot_pi_pdf.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jhtdb_pipeline.config import FILTER_TYPES, load_config
from jhtdb_pipeline.store import open_complete_result, spatial_slices
from jhtdb_pipeline.validation import atomic_json
```

模块常量/配置：

```python
ANALYSIS_VERSION = 1
```

### `sigma_text`

[实现：第 25 行](plot_pi_pdf.py#L25)

```python
def sigma_text(sigma: float) -> str
```

调用：`float`, `format`

### `_parse_sigmas`

[实现：第 29 行](plot_pi_pdf.py#L29)

```python
def _parse_sigmas(text: str) -> list[float]
```

调用：`any`, `argparse.ArgumentTypeError`, `float`, `item.strip`, `len`, `set`, `text.split`

显式异常：

```python
argparse.ArgumentTypeError('sigmas must be unique positive comma-separated values')
```

### `PiReferenceStatistics`

[实现：第 37 行](plot_pi_pdf.py#L37)

```python
class PiReferenceStatistics()
```

字段/默认值：

```python
sigma: float
point_count: int
pi_les_mean: float
pi_rms: float
abs_pi_p99: float
abs_pi_max: float
forward_count: int
backscatter_count: int
zero_count: int
source_path: Path
```

### `load_reference_statistics`

[实现：第 50 行](plot_pi_pdf.py#L50)

```python
def load_reference_statistics(result_path: Path, sigma: float) -> PiReferenceStatistics
```

调用：`PiReferenceStatistics`, `RuntimeError`, `float`, `int`, `json.loads`, `path.read_text`, `payload.get`

显式异常：

```python
RuntimeError(f'weak-asymmetry reference is not a passed full-domain result: {path}')
```

### `common_edges`

[实现：第 70 行](plot_pi_pdf.py#L70)

```python
def common_edges(references: Sequence[PiReferenceStatistics], *, central_bins: int, tail_bins: int, tail_minimum: float) -> dict[str, np.ndarray]
```

调用：`ValueError`, `math.ceil`, `max`, `np.array`, `np.concatenate`, `np.geomspace`, `np.linspace`, `np.nextafter`

显式异常：

```python
ValueError('central and tail bins must each be at least 16')
ValueError('tail_minimum must be positive')
```

### `_histogram`

[实现：第 102 行](plot_pi_pdf.py#L102)

```python
def _histogram(values: np.ndarray, edges: np.ndarray) -> np.ndarray
```

调用：`np.histogram`, `np.histogram(values, bins=edges)[0].astype`

### `analyze_pi_array`

[实现：第 106 行](plot_pi_pdf.py#L106)

```python
def analyze_pi_array(array: Any, reference: PiReferenceStatistics, edges: dict[str, np.ndarray], *, chunk_limit: int | None=None) -> dict[str, Any]
```

调用：`RuntimeError`, `ValueError`, `_histogram`, `absolute_count.sum`, `enumerate`, `float`, `int`, `len`, `math.isclose`, `math.sqrt`, `normalized_count.sum`, `np.abs`, `np.all`, `np.asarray`, `np.asarray(array[key], dtype=np.float32).reshape`, `np.count_nonzero`, `np.diff`, `np.dot`, `np.histogram`, `np.isfinite`, `np.sum`, `np.zeros`, `np.zeros_like`, `pi_les.astype`, `raw_count.sum`, `spatial_slices`, `tuple`

显式异常：

```python
RuntimeError('Pi RMS disagrees with weak-asymmetry reference')
RuntimeError('Pi sign counts do not close')
RuntimeError('Pi_LES sign counts disagree with weak-asymmetry reference')
RuntimeError('absolute-tail histogram does not cover every Pi point')
RuntimeError('normalized central histogram count closure failed')
RuntimeError('raw central histogram count closure failed')
RuntimeError(f'Pi point closure failed: {point_count} != {expected}')
ValueError(f'Pi contains NaN or Inf in chunk {index}: {key}')
```

### `_centers`

[实现：第 233 行](plot_pi_pdf.py#L233)

```python
def _centers(edges: np.ndarray) -> np.ndarray
```

### `_positive_or_nan`

[实现：第 237 行](plot_pi_pdf.py#L237)

```python
def _positive_or_nan(values: np.ndarray) -> np.ndarray
```

调用：`np.asarray`, `np.asarray(values, dtype=np.float64).copy`

### `central_pdf_figure`

[实现：第 243 行](plot_pi_pdf.py#L243)

```python
def central_pdf_figure(analyses: dict[float, dict[str, Any]], edges: np.ndarray, *, normalized: bool) -> go.Figure
```

调用：`_centers`, `_positive_or_nan`, `figure.add_trace`, `figure.update_layout`, `go.Figure`, `go.Scatter`, `sigma_text`, `sorted`

### `signed_tail_figure`

[实现：第 281 行](plot_pi_pdf.py#L281)

```python
def signed_tail_figure(analyses: dict[float, dict[str, Any]], edges: np.ndarray) -> go.Figure
```

调用：`_centers`, `_positive_or_nan`, `divmod`, `enumerate`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `go.Scatter`, `make_subplots`, `sigma_text`, `sorted`

### `ccdf_figure`

[实现：第 322 行](plot_pi_pdf.py#L322)

```python
def ccdf_figure(analyses: dict[float, dict[str, Any]], edges: np.ndarray) -> go.Figure
```

调用：`figure.add_trace`, `figure.update_layout`, `go.Figure`, `go.Scatter`, `np.cumsum`, `sigma_text`, `sorted`

### `contribution_figure`

[实现：第 342 行](plot_pi_pdf.py#L342)

```python
def contribution_figure(analyses: dict[float, dict[str, Any]], edges: np.ndarray) -> go.Figure
```

调用：`_positive_or_nan`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `float`, `go.Scatter`, `make_subplots`, `np.cumsum`, `np.gradient`, `np.sum`, `sigma_text`, `sorted`

### `_atomic_npz`

[实现：第 441 行](plot_pi_pdf.py#L441)

```python
def _atomic_npz(path: Path, **arrays: Any) -> None
```

调用：`np.savez_compressed`, `path.with_suffix`, `temporary.open`, `temporary.replace`

### `write_outputs`

[实现：第 448 行](plot_pi_pdf.py#L448)

```python
def write_outputs(output_dir: Path, references: dict[float, PiReferenceStatistics], analyses: dict[float, dict[str, Any]], edges: dict[str, np.ndarray], *, time_index: int, chunk_limit: int | None, filter_type: str='gaussian', sharp_edge_width_fraction: float | None=None) -> list[Path]
```

调用：`'\n'.join`, `_atomic_npz`, `all`, `analyses.values`, `atomic_json`, `ccdf_figure`, `central_pdf_figure`, `contribution_figure`, `csv.writer`, `csv_path.open`, `directory.mkdir`, `edges['absolute_normalized'][[0, -1]].tolist`, `edges['normalized'][[0, -1]].tolist`, `edges['raw'][[0, -1]].tolist`, `figure.write_html`, `figures.items`, `math.isclose`, `output_dir.mkdir`, `paths.append`, `paths.extend`, `report_path.write_text`, `sigma_text`, `sigma_text(sigma).replace`, `signed_tail_figure`, `sorted`, `str`, `writer.writerow`

### `build_parser`

[实现：第 583 行](plot_pi_pdf.py#L583)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`argparse.ArgumentParser`, `parser.add_argument`

### `run`

[实现：第 598 行](plot_pi_pdf.py#L598)

```python
def run(args: argparse.Namespace) -> Path
```

调用：`Path`, `ValueError`, `analyze_pi_array`, `cfg.result_id`, `cfg.result_id(args.time_index, 0).rsplit`, `cfg.result_path`, `cfg.with_filter`, `cfg.with_sharp_edge_width_fraction`, `common_edges`, `list`, `load_config`, `load_reference_statistics`, `open_complete_result`, `output_dir.resolve`, `print`, `references.values`, `sigma_text`, `write_outputs`

显式异常：

```python
ValueError('--smoke-chunks must be positive')
```

### `main`

[实现：第 639 行](plot_pi_pdf.py#L639)

```python
def main(argv: Sequence[str] | None=None) -> int
```

调用：`build_parser`, `build_parser().parse_args`, `print`, `run`, `time.monotonic`

## pi_pdf/validate_log_pi_gaussian.py

[完整源码](validate_log_pi_gaussian.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jhtdb_pipeline.config import FILTER_TYPES, load_config
from jhtdb_pipeline.store import open_complete_result, spatial_slices
from jhtdb_pipeline.validation import atomic_json
```

模块常量/配置：

```python
BRANCHES = ('forward', 'backscatter')
```

### `sigma_text`

[实现：第 23 行](validate_log_pi_gaussian.py#L23)

```python
def sigma_text(sigma: float) -> str
```

调用：`float`, `format`

### `_parse_sigmas`

[实现：第 27 行](validate_log_pi_gaussian.py#L27)

```python
def _parse_sigmas(text: str) -> list[float]
```

调用：`any`, `argparse.ArgumentTypeError`, `float`, `item.strip`, `len`, `set`, `text.split`

显式异常：

```python
argparse.ArgumentTypeError('sigmas must be unique positive values')
```

### `_normal_pdf`

[实现：第 34 行](validate_log_pi_gaussian.py#L34)

```python
def _normal_pdf(y: np.ndarray, mean: float, standard_deviation: float) -> np.ndarray
```

调用：`float`, `math.sqrt`, `max`, `np.exp`, `np.finfo`, `np.square`

### `_normal_cdf`

[实现：第 39 行](validate_log_pi_gaussian.py#L39)

```python
def _normal_cdf(y: np.ndarray, mean: float, standard_deviation: float) -> np.ndarray
```

调用：`float`, `math.sqrt`, `max`, `np.finfo`, `np.vectorize`, `np.vectorize(math.erf)`

### `_r2`

[实现：第 44 行](validate_log_pi_gaussian.py#L44)

```python
def _r2(observed: np.ndarray, predicted: np.ndarray) -> float | None
```

调用：`float`, `np.mean`, `np.square`, `np.sum`

### `_weighted_quantiles_from_hist`

[实现：第 51 行](validate_log_pi_gaussian.py#L51)

```python
def _weighted_quantiles_from_hist(edges: np.ndarray, weights: np.ndarray, probabilities: Sequence[float]) -> np.ndarray
```

调用：`float`, `len`, `np.asarray`, `np.clip`, `np.cumsum`, `np.full`, `np.searchsorted`

### `_branch_metrics`

[实现：第 64 行](validate_log_pi_gaussian.py#L64)

```python
def _branch_metrics(y_edges: np.ndarray, contribution: np.ndarray, *, weighted_moments: tuple[float, float, float, float, float], point_count: int) -> dict[str, Any]
```

调用：`_normal_cdf`, `_normal_pdf`, `_r2`, `_weighted_quantiles_from_hist`, `abs`, `float`, `int`, `len`, `math.sqrt`, `max`, `np.abs`, `np.any`, `np.array`, `np.count_nonzero`, `np.cumsum`, `np.diff`, `np.finfo`, `np.full`, `np.log`, `np.max`, `np.mean`, `np.polyfit`, `np.polyval`, `np.sqrt`, `np.square`, `np.zeros`

### `analyze_pi_root`

[实现：第 172 行](validate_log_pi_gaussian.py#L172)

```python
def analyze_pi_root(root: Any, *, rms: float, point_count_expected: int, y_edges: np.ndarray, chunk_limit: int | None=None) -> dict[str, Any]
```

调用：`RuntimeError`, `ValueError`, `_branch_metrics`, `enumerate`, `int`, `len`, `np.abs`, `np.all`, `np.array`, `np.asarray`, `np.asarray(root[key], dtype=np.float32).reshape`, `np.asarray(root[key], dtype=np.float32).reshape(-1).astype`, `np.count_nonzero`, `np.dot`, `np.histogram`, `np.isfinite`, `np.log10`, `np.sum`, `np.zeros`, `spatial_slices`, `tuple`

显式异常：

```python
RuntimeError(f'Pi point closure failed: {point_count} != {expected}')
ValueError(f'Pi contains NaN or Inf in chunk {index}: {key}')
```

### `_figure_cdf`

[实现：第 226 行](validate_log_pi_gaussian.py#L226)

```python
def _figure_cdf(results: dict[float, dict[str, Any]]) -> go.Figure
```

调用：`divmod`, `enumerate`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `go.Scatter`, `make_subplots`, `sigma_text`, `sorted`

### `_figure_pdf`

[实现：第 242 行](validate_log_pi_gaussian.py#L242)

```python
def _figure_pdf(results: dict[float, dict[str, Any]]) -> go.Figure
```

调用：`divmod`, `enumerate`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `go.Scatter`, `make_subplots`, `np.where`, `sigma_text`, `sorted`

### `_figure_curvature`

[实现：第 259 行](validate_log_pi_gaussian.py#L259)

```python
def _figure_curvature(results: dict[float, dict[str, Any]]) -> go.Figure
```

调用：`figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `go.Scatter`, `len`, `make_subplots`, `np.gradient`, `np.log`, `sigma_text`, `sorted`

### `_figure_qq`

[实现：第 284 行](validate_log_pi_gaussian.py#L284)

```python
def _figure_qq(results: dict[float, dict[str, Any]]) -> go.Figure
```

调用：`enumerate`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `go.Scatter`, `make_subplots`, `sigma_text`, `sorted`

### `_json_metrics`

[实现：第 298 行](validate_log_pi_gaussian.py#L298)

```python
def _json_metrics(results: dict[float, dict[str, Any]], *, time_index: int, chunk_limit: int | None) -> dict[str, Any]
```

调用：`item.items`, `results.items`, `sigma_text`, `sorted`

### `write_outputs`

[实现：第 324 行](validate_log_pi_gaussian.py#L324)

```python
def write_outputs(output_dir: Path, results: dict[float, dict[str, Any]], *, time_index: int, chunk_limit: int | None, filter_type: str='gaussian', sharp_edge_width_fraction: float | None=None) -> None
```

调用：`'\n'.join`, `(output_dir / 'LOG_PI_GAUSSIAN_REPORT_CN.md').write_text`, `(output_dir / 'log_pi_gaussian_parameters.csv').open`, `_figure_cdf`, `_figure_curvature`, `_figure_pdf`, `_figure_qq`, `_json_metrics`, `atomic_json`, `csv.writer`, `figure.write_html`, `figures.items`, `output_dir.mkdir`, `results.items`, `sorted`, `str`, `writer.writerow`

### `build_parser`

[实现：第 362 行](validate_log_pi_gaussian.py#L362)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`argparse.ArgumentParser`, `parser.add_argument`

### `run`

[实现：第 377 行](validate_log_pi_gaussian.py#L377)

```python
def run(args: argparse.Namespace) -> Path
```

调用：`(result_dir / 'weak_asymmetry.json').read_text`, `Path`, `ValueError`, `analyze_pi_root`, `cfg.result_id`, `cfg.result_id(args.time_index, 0).rsplit`, `cfg.result_path`, `cfg.with_filter`, `cfg.with_sharp_edge_width_fraction`, `float`, `int`, `json.loads`, `list`, `load_config`, `math.log10`, `max`, `np.linspace`, `np.nextafter`, `open_complete_result`, `output_dir.resolve`, `print`, `sigma_text`, `write_outputs`

显式异常：

```python
ValueError('y-max must exceed y-min')
```

### `main`

[实现：第 418 行](validate_log_pi_gaussian.py#L418)

```python
def main(argv: Sequence[str] | None=None) -> int
```

调用：`build_parser`, `build_parser().parse_args`, `print`, `run`

