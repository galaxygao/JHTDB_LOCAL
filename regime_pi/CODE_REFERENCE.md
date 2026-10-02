# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## regime_pi/__init__.py

[完整源码](__init__.py)

此入口只包含导入、常量或顶层调用。

## regime_pi/statistics.py

[完整源码](statistics.py)

依赖：

```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import numpy as np
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from jhtdb_pipeline.config import PipelineConfig, result_zarr_name
from jhtdb_pipeline.cq import REGIME_KEYS
from jhtdb_pipeline.store import spatial_slices
from jhtdb_pipeline.validation import atomic_json
```

模块常量/配置：

```python
REGIME_PI_REPORT_VERSION = 1
DEFAULT_REGIME_PI_OUTPUT_ROOT = Path('regime_pi/output')
__all__ = ['DEFAULT_REGIME_PI_OUTPUT_ROOT', 'REGIME_PI_REPORT_VERSION', 'compute_regime_pi_statistics', 'regime_pi_output_dir', 'regime_pi_report_is_current', 'run_regime_pi_statistics']
```

### `_chunk_count`

[实现：第 23 行](statistics.py#L23)

```python
def _chunk_count(shape: tuple[int, ...], chunks: tuple[int, ...]) -> int
```

调用：`int`, `np.prod`, `zip`

### `_regime_masks`

[实现：第 32 行](statistics.py#L32)

```python
def _regime_masks(full: np.ndarray, resolved: np.ndarray) -> tuple[np.ndarray, ...]
```

### `compute_regime_pi_statistics`

[实现：第 48 行](statistics.py#L48)

```python
def compute_regime_pi_statistics(root: Any, cfg: PipelineConfig) -> dict[str, Any]
```

Split stored Pi into backscatter/forward parts inside every Cq regime.

调用：`BarColumn`, `Console`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `_chunk_count`, `_regime_masks`, `abs`, `any`, `bool`, `enumerate`, `float`, `int`, `list`, `max`, `np.all`, `np.asarray`, `np.count_nonzero`, `np.dtype`, `np.isfinite`, `np.prod`, `np.zeros`, `progress.add_task`, `progress.advance`, `regime_counts.sum`, `selected.sum`, `selected[negative].sum`, `selected[positive].sum`, `spatial_slices`, `tuple`, `values.astype`

显式异常：

```python
RuntimeError('regime Pi statistics require float32 fields')
RuntimeError('regime Pi statistics require full-domain fields')
ValueError('Pi or work field contains NaN or Inf')
```

### `regime_pi_output_dir`

[实现：第 196 行](statistics.py#L196)

```python
def regime_pi_output_dir(result_dir: Path | str, output_root: Path | str=DEFAULT_REGIME_PI_OUTPUT_ROOT) -> Path
```

调用：`Path`

### `regime_pi_report_is_current`

[实现：第 203 行](statistics.py#L203)

```python
def regime_pi_report_is_current(path: Path, result_manifest_hash: str | None) -> bool
```

调用：`bool`, `json.loads`, `path.is_file`, `path.read_text`, `report.get`

### `run_regime_pi_statistics`

[实现：第 217 行](statistics.py#L217)

```python
def run_regime_pi_statistics(cfg: PipelineConfig, time_index: int, sigma_grid: float, *, output_root: Path | str=DEFAULT_REGIME_PI_OUTPUT_ROOT, overwrite: bool=False) -> Path
```

调用：`(result_dir / 'COMPLETE').is_file`, `FileLock`, `RuntimeError`, `atomic_json`, `cfg.physical_time`, `cfg.result_path`, `compute_regime_pi_statistics`, `destination.mkdir`, `float`, `regime_pi_output_dir`, `regime_pi_report_is_current`, `report.update`, `result_dir.resolve`, `result_zarr_name`, `root.attrs.get`, `str`, `zarr.open_group`

显式异常：

```python
RuntimeError(f'complete result is missing: {result_dir}')
```

