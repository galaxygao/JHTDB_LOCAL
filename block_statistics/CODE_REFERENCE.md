# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## block_statistics/__init__.py

[完整源码](__init__.py)

依赖：

```python
from .compute_block_statistics import block_moments, compute_block_statistics, strain_contraction_block_sums
from .plot_vs_strain import visualize_block_statistics
from .regime_pair_asymmetry import compute_regime_pair_asymmetry, pair_asymmetry, run_regime_pair_asymmetry
```

模块常量/配置：

```python
__all__ = ['block_moments', 'compute_block_statistics', 'strain_contraction_block_sums', 'visualize_block_statistics', 'compute_regime_pair_asymmetry', 'pair_asymmetry', 'run_regime_pair_asymmetry']
```

此入口只包含导入、常量或顶层调用。

## block_statistics/compute_block_statistics.py

[完整源码](compute_block_statistics.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable
import numpy as np
from filelock import FileLock
from jhtdb_pipeline.config import FILTER_TYPES, PipelineConfig, load_config
from jhtdb_pipeline.store import open_complete_result
from block_statistics.strain import STRAIN_CACHE_VERSION, ensure_strain_cache
```

模块常量/配置：

```python
FIELD_NAMES = ('work_resolved', 'work_full', 'pi')
REPORT_VERSION = 3
__all__ = ['block_moments', 'compute_block_statistics', 'strain_contraction_block_sums']
```

### `_divisions3`

[实现：第 23 行](compute_block_statistics.py#L23)

```python
def _divisions3(divisions: int | Iterable[int]) -> tuple[int, int, int]
```

调用：`ValueError`, `any`, `int`, `isinstance`, `len`, `tuple`

显式异常：

```python
ValueError('divisions must contain three positive integers')
```

### `_block_shape`

[实现：第 33 行](compute_block_statistics.py#L33)

```python
def _block_shape(shape_zyx: tuple[int, int, int], divisions_zyx: tuple[int, int, int]) -> tuple[int, int, int]
```

调用：`ValueError`, `any`, `tuple`, `zip`

显式异常：

```python
ValueError('every spatial dimension must be divisible by its block count')
```

### `_block_keys`

[实现：第 41 行](compute_block_statistics.py#L41)

```python
def _block_keys(shape_zyx: tuple[int, int, int], divisions_zyx: tuple[int, int, int])
```

调用：`_block_shape`, `range`, `slice`, `tuple`, `zip`

### `block_moments`

[实现：第 55 行](compute_block_statistics.py#L55)

```python
def block_moments(field: Any, divisions: int | Iterable[int]=16) -> dict[str, np.ndarray | int | tuple[int, int, int]]
```

Return exact per-block moments without sampling any grid points.

Spatial array order is ``(z, y, x)``. Sums and squared sums accumulate in
float64 even when the stored field is float32.

调用：`ValueError`, `_block_keys`, `_block_shape`, `_divisions3`, `float`, `int`, `len`, `np.all`, `np.asarray`, `np.empty`, `np.isfinite`, `np.maximum`, `np.prod`, `np.sqrt`, `np.square`, `np.square(values, dtype=np.float64).sum`, `tuple`, `values.max`, `values.min`, `values.sum`

显式异常：

```python
ValueError('field contains NaN or Inf')
ValueError('field must be a three-dimensional scalar array')
```

### `strain_contraction_block_sums`

[实现：第 95 行](compute_block_statistics.py#L95)

```python
def strain_contraction_block_sums(gradient: Any, divisions: int | Iterable[int]=16) -> np.ndarray
```

Compute block sums of S_ij S_ij from ``gradient[i,j]=d_j u_i``.

The contraction includes all nine tensor positions, so every off-diagonal
symmetric component contributes twice.

调用：`(0.5 * np.square(left + right, dtype=np.float64)).sum`, `ValueError`, `_block_keys`, `_block_shape`, `_divisions3`, `float`, `int`, `len`, `np.asarray`, `np.square`, `np.square(diagonal, dtype=np.float64).sum`, `np.zeros`, `range`, `tuple`

显式异常：

```python
ValueError('gradient must have shape (3, 3, z, y, x)')
```

### `_validate_filter_metadata`

[实现：第 126 行](compute_block_statistics.py#L126)

```python
def _validate_filter_metadata(cfg: PipelineConfig, sigma: float, attrs: Any) -> None
```

调用：`ValueError`, `attrs.get`, `float`, `np.isclose`, `str`

显式异常：

```python
ValueError('result and configuration use different smooth-sharp width fractions')
ValueError(f'result filter is {actual_type}, but configuration selects {cfg.filter_type}')
```

### `_sha256`

[实现：第 145 行](compute_block_statistics.py#L145)

```python
def _sha256(path: Path) -> str
```

调用：`digest.hexdigest`, `digest.update`, `hashlib.sha256`, `iter`, `path.open`, `stream.read`

### `_write_csv`

[实现：第 153 行](compute_block_statistics.py#L153)

```python
def _write_csv(path: Path, cfg: PipelineConfig, divisions_zyx: tuple[int, int, int], strain_sums: np.ndarray, moments: dict[str, dict[str, Any]]) -> None
```

调用：`_block_keys`, `_block_shape`, `columns.extend`, `csv.DictWriter`, `int`, `np.prod`, `path.with_suffix`, `temporary.open`, `temporary.replace`, `writer.writeheader`, `writer.writerow`

### `compute_block_statistics`

[实现：第 202 行](compute_block_statistics.py#L202)

```python
def compute_block_statistics(cfg: PipelineConfig, time_index: int, sigma_grid: float, *, blocks_per_axis: int=16, output_root: Path | str=Path('block_statistics/output'), scratch_root: Path | str=Path('block_statistics/.scratch'), overwrite: bool=False) -> Path
```

Compute block means for raw-velocity strain, Wres, Wfull and Pi.

调用：`FileLock`, `Path`, `RuntimeError`, `ValueError`, `_block_shape`, `_divisions3`, `_sha256`, `_validate_filter_metadata`, `_write_csv`, `block_moments`, `cfg.physical_time`, `cfg.result_path`, `cfg.strain_store_path`, `cfg.strain_store_path(time_index).resolve`, `csv_path.is_file`, `csv_path.resolve`, `ensure_strain_cache`, `float`, `int`, `json.dumps`, `json.loads`, `list`, `math.isfinite`, `metadata.get`, `metadata_path.is_file`, `metadata_path.read_text`, `metadata_path.with_suffix`, `np.asarray`, `np.asarray(moments[name]['sum']).sum`, `np.prod`, `open_complete_result`, `output_dir.mkdir`, `result.attrs.get`, `result_dir.resolve`, `str`, `strain_sums.sum`, `temporary.replace`, `temporary.write_text`, `tuple`

显式异常：

```python
RuntimeError('result is missing its input manifest hash')
ValueError('block statistics require a full-domain result')
ValueError('sigma_grid must be finite and positive')
```

### `build_parser`

[实现：第 305 行](compute_block_statistics.py#L305)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`Path`, `argparse.ArgumentParser`, `parser.add_argument`

### `main`

[实现：第 324 行](compute_block_statistics.py#L324)

```python
def main(argv: list[str] | None=None) -> int
```

调用：`build_parser`, `build_parser().parse_args`, `cfg.with_filter`, `cfg.with_sharp_edge_width_fraction`, `compute_block_statistics`, `load_config`, `output.resolve`, `print`

## block_statistics/plot_vs_strain.py

[完整源码](plot_vs_strain.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from typing import Any
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
```

模块常量/配置：

```python
PLOT_VERSION = 1
X_COLUMN = 'sij_sij_mean'
Y_FIELDS = (('work_resolved_mean', 'W_res', '#1f77b4'), ('work_full_mean', 'W_full', '#ff7f0e'), ('pi_mean', 'Pi', '#2ca02c'))
REQUIRED_COLUMNS = {'block_id', 'block_x', 'block_y', 'block_z', X_COLUMN, *(name for name, _, _ in Y_FIELDS)}
```

### `resolve_input_csv`

[实现：第 31 行](plot_vs_strain.py#L31)

```python
def resolve_input_csv(path: Path | str) -> Path
```

Accept either a block-statistics CSV or its containing result directory.

调用：`FileNotFoundError`, `Path`, `ValueError`, `len`, `preferred.is_file`, `sorted`, `source.glob`, `source.is_dir`, `source.is_file`

显式异常：

```python
FileNotFoundError(f'block-statistics CSV does not exist: {source}')
FileNotFoundError(f'no block-statistics CSV found in {source}; run compute_block_statistics.py for this result first')
ValueError(f'multiple block-statistics CSV files found in {source}; pass the desired CSV path explicitly')
```

### `load_and_sort_blocks`

[实现：第 60 行](plot_vs_strain.py#L60)

```python
def load_and_sort_blocks(csv_path: Path | str) -> tuple[list[dict[str, str]], list[str]]
```

Load all blocks and return them in ascending block-mean S_ij S_ij order.

调用：`', '.join`, `ValueError`, `csv.DictReader`, `enumerate`, `float`, `int`, `list`, `np.all`, `np.isfinite`, `path.open`, `resolve_input_csv`, `rows.sort`, `set`, `sorted`, `str`

显式异常：

```python
ValueError('block CSV contains NaN or Inf')
ValueError('block CSV contains no rows')
ValueError(f"block CSV is missing columns: {', '.join(missing)}")
```

### `write_sorted_blocks`

[实现：第 82 行](plot_vs_strain.py#L82)

```python
def write_sorted_blocks(rows: list[dict[str, str]], original_columns: list[str], output_path: Path | str) -> Path
```

调用：`Path`, `csv.DictWriter`, `path.parent.mkdir`, `path.with_suffix`, `temporary.open`, `temporary.replace`, `writer.writeheader`, `writer.writerows`

### `_custom_data`

[实现：第 97 行](plot_vs_strain.py#L97)

```python
def _custom_data(rows: list[dict[str, str]]) -> np.ndarray
```

调用：`int`, `np.asarray`

### `build_figure`

[实现：第 113 行](plot_vs_strain.py#L113)

```python
def build_figure(rows: list[dict[str, str]], title: str) -> go.Figure
```

调用：`_custom_data`, `enumerate`, `figure.add_hline`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `float`, `go.Scattergl`, `make_subplots`, `np.asarray`

### `visualize_block_statistics`

[实现：第 170 行](plot_vs_strain.py#L170)

```python
def visualize_block_statistics(csv_path: Path | str, *, output_dir: Path | str | None=None) -> dict[str, Path]
```

Sort blocks by mean strain contraction and plot all block-level pairs.

调用：`Path`, `build_figure`, `destination.mkdir`, `figure.write_html`, `html_path.resolve`, `json.dumps`, `len`, `load_and_sort_blocks`, `metadata_path.with_suffix`, `resolve_input_csv`, `sorted_path.resolve`, `source.resolve`, `str`, `temporary.replace`, `temporary.write_text`, `write_sorted_blocks`

### `build_parser`

[实现：第 213 行](plot_vs_strain.py#L213)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`argparse.ArgumentParser`, `parser.add_argument`

### `main`

[实现：第 229 行](plot_vs_strain.py#L229)

```python
def main(argv: list[str] | None=None) -> int
```

调用：`build_parser`, `build_parser().parse_args`, `json.dumps`, `outputs.items`, `path.resolve`, `print`, `str`, `visualize_block_statistics`

## block_statistics/regime_pair_asymmetry.py

[完整源码](regime_pair_asymmetry.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from jhtdb_pipeline.config import FILTER_TYPES, PipelineConfig, load_config
from jhtdb_pipeline.store import open_complete_result
```

模块常量/配置：

```python
REPORT_VERSION = 1
PAIR_SPECS = {'1_4': ((1, 2), (5, 6)), '2_3': ((3,), (4,))}
DIRECTIONS = ('backscatter', 'forward', 'total')
```

### `normalized_difference`

[实现：第 37 行](regime_pair_asymmetry.py#L37)

```python
def normalized_difference(left: float, right: float) -> float
```

Return (left-right)/(left+right), or NaN when both are zero.

### `pair_asymmetry`

[实现：第 43 行](regime_pair_asymmetry.py#L43)

```python
def pair_asymmetry(left_backscatter: float, left_forward: float, right_backscatter: float, right_forward: float) -> dict[str, float]
```

Return bounded directional and signed-total asymmetry for one pair.

调用：`normalized_difference`

### `_directional_sums`

[实现：第 63 行](regime_pair_asymmetry.py#L63)

```python
def _directional_sums(pi: np.ndarray, regime: np.ndarray, codes: Iterable[int]) -> tuple[float, float, int]
```

调用：`float`, `int`, `mask.sum`, `np.isin`, `tuple`, `values[values < 0.0].sum`, `values[values > 0.0].sum`

### `compute_regime_pair_asymmetry`

[实现：第 73 行](regime_pair_asymmetry.py#L73)

```python
def compute_regime_pair_asymmetry(pi_field: Any, regime_field: Any, strain_rows: list[dict[str, str]], divisions: int | Iterable[int]=16) -> list[dict[str, Any]]
```

Compute exact blockwise Q1/Q4 and Q2/Q3 Pi asymmetries.

调用：`PAIR_SPECS.items`, `ValueError`, `_block_keys`, `_block_shape`, `_directional_sums`, `_divisions3`, `enumerate`, `float`, `int`, `len`, `np.all`, `np.asarray`, `np.isfinite`, `np.prod`, `output.append`, `pair_asymmetry`, `rows_by_id.get`, `tuple`

显式异常：

```python
ValueError('pi and regime must be same-shape three-dimensional fields')
ValueError('pi contains NaN or Inf')
ValueError('strain CSV block_id values are not unique and complete')
ValueError(f'strain CSV coordinates disagree for block_id {block_id}')
ValueError(f'strain CSV has {len(strain_rows)} rows; expected {expected}')
ValueError(f'strain CSV is missing block_id {block_id}')
```

### `_read_strain_csv`

[实现：第 125 行](regime_pair_asymmetry.py#L125)

```python
def _read_strain_csv(path: Path) -> list[dict[str, str]]
```

调用：`', '.join`, `ValueError`, `csv.DictReader`, `list`, `path.open`, `required.difference`, `sorted`

显式异常：

```python
ValueError(f"strain CSV is missing columns: {', '.join(sorted(missing))}")
```

### `_write_csv`

[实现：第 135 行](regime_pair_asymmetry.py#L135)

```python
def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None
```

调用：`csv.DictWriter`, `list`, `path.with_suffix`, `temporary.open`, `temporary.replace`, `writer.writeheader`, `writer.writerows`

### `_write_figure`

[实现：第 144 行](regime_pair_asymmetry.py#L144)

```python
def _write_figure(path: Path, rows: list[dict[str, Any]], title: str) -> None
```

调用：`divmod`, `enumerate`, `figure.add_hline`, `figure.add_trace`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `figure.write_html`, `go.Scattergl`, `make_subplots`, `np.asarray`, `np.isfinite`

### `run_regime_pair_asymmetry`

[实现：第 193 行](regime_pair_asymmetry.py#L193)

```python
def run_regime_pair_asymmetry(cfg: PipelineConfig, time_index: int, sigma_grid: float, *, blocks_per_axis: int=16, output_root: Path | str=Path('block_statistics/output'), overwrite: bool=False) -> Path
```

调用：`FileNotFoundError`, `Path`, `RuntimeError`, `_read_strain_csv`, `_sha256`, `_validate_filter_metadata`, `_write_csv`, `_write_figure`, `cfg.result_path`, `compute_regime_pair_asymmetry`, `csv_path.is_file`, `csv_path.resolve`, `float`, `html_path.is_file`, `html_path.resolve`, `json.dumps`, `json.loads`, `len`, `metadata.get`, `metadata_path.is_file`, `metadata_path.read_text`, `metadata_path.with_suffix`, `open_complete_result`, `root.attrs.get`, `str`, `strain_path.is_file`, `strain_path.resolve`, `temporary.replace`, `temporary.write_text`, `tuple`

显式异常：

```python
FileNotFoundError(f'run compute_block_statistics first: {strain_path}')
RuntimeError(f'block regime asymmetry requires full-domain {name}')
```

### `build_parser`

[实现：第 263 行](regime_pair_asymmetry.py#L263)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`Path`, `argparse.ArgumentParser`, `parser.add_argument`

### `main`

[实现：第 278 行](regime_pair_asymmetry.py#L278)

```python
def main(argv: list[str] | None=None) -> int
```

调用：`build_parser`, `build_parser().parse_args`, `cfg.with_filter`, `cfg.with_sharp_edge_width_fraction`, `load_config`, `output.resolve`, `print`, `run_regime_pair_asymmetry`

## block_statistics/strain.py

[完整源码](strain.py)

依赖：

```python
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Any
import numpy as np
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from jhtdb_pipeline.config import PipelineConfig
from jhtdb_pipeline.physics import ComponentView, close_memmap, derivative_field, memmap
from jhtdb_pipeline.store import compressor, spatial_slices
```

模块常量/配置：

```python
STRAIN_CACHE_VERSION = 1
__all__ = ['STRAIN_CACHE_VERSION', 'ensure_strain_cache']
```

### `_cache_is_current`

[实现：第 22 行](strain.py#L22)

```python
def _cache_is_current(cfg: PipelineConfig, time_index: int, input_hash: str) -> bool
```

调用：`cfg.strain_store_path`, `np.dtype`, `path.is_dir`, `root.attrs.get`, `str`, `tuple`, `zarr.open_group`

### `_accumulate`

[实现：第 40 行](strain.py#L40)

```python
def _accumulate(destination: Any, contribution: Any, *, pair: Any | None=None) -> None
```

调用：`np.asarray`, `np.float32`, `np.square`, `spatial_slices`

### `_build_cache`

[实现：第 51 行](strain.py#L51)

```python
def _build_cache(cfg: PipelineConfig, time_index: int, input_hash: str) -> Path
```

调用：`BarColumn`, `ComponentView`, `Console`, `Path`, `Path(__file__).resolve`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `_accumulate`, `_cache_is_current`, `cfg.physical_time`, `cfg.raw_store_path`, `cfg.raw_store_path(time_index).resolve`, `cfg.strain_store_path`, `close_memmap`, `compressor`, `derivative_field`, `final.exists`, `final.with_name`, `memmap`, `min`, `np.dtype`, `os.replace`, `progress.add_task`, `progress.advance`, `range`, `raw_root.attrs.get`, `root.attrs.update`, `root.create_dataset`, `scratch.exists`, `scratch.mkdir`, `shutil.rmtree`, `staging.exists`, `staging.parent.mkdir`, `str`, `temp_a.flush`, `temp_b.flush`, `tuple`, `zarr.open_group`

显式异常：

```python
RuntimeError('raw velocity cache manifest changed while building strain cache')
ValueError('validated velocity cache has an unexpected schema')
```

### `ensure_strain_cache`

[实现：第 136 行](strain.py#L136)

```python
def ensure_strain_cache(cfg: PipelineConfig, time_index: int, input_hash: str) -> Any
```

Return the shared full-domain raw-velocity S_ij S_ij array.

调用：`FileLock`, `_build_cache`, `_cache_is_current`, `cfg.lock_path.mkdir`, `cfg.strain_store_path`, `str`, `zarr.open_group`

