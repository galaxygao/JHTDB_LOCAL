# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## qpower_analysis/__init__.py

[完整源码](__init__.py)

此入口只包含导入、常量或顶层调用。

## qpower_analysis/angle_statistics.py

[完整源码](angle_statistics.py)

依赖：

```python
import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np
import zarr
from jhtdb_pipeline.store import spatial_slices
```

### `angle_degrees`

[实现：第 12 行](angle_statistics.py#L12)

```python
def angle_degrees(u, g)
```

调用：`np.arccos`, `np.clip`, `np.degrees`, `np.divide`, `np.einsum`, `np.full_like`, `np.sqrt`

### `run`

[实现：第 18 行](angle_statistics.py#L18)

```python
def run(folder, alpha=1.0, beta=1.0)
```

调用：`(folder / 'config_used.json').read_text`, `(folder / 'run_summary.csv').open`, `(out / 'summary.json').write_text`, `(out / f'angle_given_{name}.csv').open`, `angle_degrees`, `csv.DictReader`, `csv.DictWriter`, `dict`, `enumerate`, `float`, `frame.get`, `gb[:, mask].astype`, `int`, `json.dumps`, `json.loads`, `len`, `list`, `map`, `next`, `np.clip`, `np.column_stack`, `np.column_stack((theta, q[mask].astype('float64') / qr, u2[mask].astype('float64') / um)).astype`, `np.concatenate`, `np.corrcoef`, `np.cos`, `np.deg2rad`, `np.einsum`, `np.isfinite`, `np.isfinite(values).all`, `np.linspace`, `np.mean`, `np.prod`, `np.quantile`, `np.searchsorted`, `np.unique`, `out.mkdir`, `pieces.append`, `plot_saved`, `print`, `q[mask].astype`, `range`, `rows.append`, `slice`, `spatial_slices`, `sum`, `u2[mask].astype`, `ub[:, mask].astype`, `values[:, 0].astype`, `w.writeheader`, `w.writerows`, `x.max`, `x.min`, `zarr.open_group`, `zip`

### `plot_saved`

[实现：第 63 行](angle_statistics.py#L63)

```python
def plot_saved(out)
```

Plot equal-width central bins; report pooled tails separately.

调用：`'\n'.join`, `(out / 'summary.json').read_text`, `(out / f'angle_given_{name}.csv').open`, `Path`, `Path('.local/cache/matplotlib').resolve`, `abs`, `ax.grid`, `bottom.bar`, `bottom.set`, `cosine_axis.get_legend_handles_labels`, `cosine_axis.plot`, `cosine_axis.set_ylabel`, `cosine_axis.tick_params`, `csv.DictReader`, `dict`, `enumerate`, `fig.savefig`, `fig.suptitle`, `fig.supxlabel`, `float`, `json.loads`, `matplotlib.use`, `os.environ.setdefault`, `plt.close`, `plt.subplots`, `r.items`, `str`, `sum`, `tails.append`, `top.fill_between`, `top.get_legend_handles_labels`, `top.legend`, `top.plot`, `top.set`, `top.text`, `top.twinx`, `zip`

## qpower_analysis/conditional_ranges.py

[完整源码](conditional_ranges.py)

依赖：

```python
import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np
import zarr
from conditional_tails import fields, quantile_from_hist, plot
```

### `value_edges`

[实现：第 12 行](conditional_ranges.py#L12)

```python
def value_edges(name, minimum, maximum)
```

调用：`abs`, `max`, `min`, `np.concatenate`, `np.geomspace`

### `indices`

[实现：第 19 行](conditional_ranges.py#L19)

```python
def indices(values, edges)
```

调用：`ValueError`, `len`, `np.any`, `np.searchsorted`, `values.ravel`

显式异常：

```python
ValueError('Values outside histogram')
```

### `quantile_ranges`

[实现：第 27 行](conditional_ranges.py#L27)

```python
def quantile_ranges(hist, edges, exact, coverage=0.95)
```

调用：`ValueError`, `enumerate`, `float`, `h.sum`, `len`, `np.concatenate`, `np.quantile`, `output.append`, `quantile_from_hist`, `tuple`

显式异常：

```python
ValueError('Incomplete sparse-bin data')
```

### `run`

[实现：第 40 行](conditional_ranges.py#L40)

```python
def run(folder, coverage=0.5, from_histograms=False)
```

调用：`(folder / 'config_used.json').read_text`, `(folder / 'run_summary.csv').open`, `(out / f'frame_{number:06d}_metadata.json').read_text`, `(out / f'frame_{number:06d}_metadata.json').write_text`, `Path`, `Path('.local/cache/matplotlib').resolve`, `ValueError`, `arrays.append`, `csv.DictReader`, `csv.DictWriter`, `dict`, `enumerate`, `fields`, `float`, `hist.sum`, `indices`, `int`, `json.dumps`, `json.loads`, `len`, `list`, `np.array`, `np.array_equal`, `np.bincount`, `np.bincount(ix * ny + iy, minlength=plan['histogram'].size).reshape`, `np.load`, `np.savez_compressed`, `np.zeros`, `os.environ.setdefault`, `plan['exact'].items`, `plans.items`, `plans.values`, `plot`, `prefix.with_suffix`, `prefix.with_suffix('.csv').open`, `print`, `quantile_ranges`, `root.attrs.get`, `row.update`, `rows[0].keys`, `saved['counts'].copy`, `saved['y_edges'].copy`, `str`, `value_edges`, `values.copy`, `writer.writeheader`, `writer.writerows`, `y.ravel`, `zarr.open_group`, `zip`

显式异常：

```python
ValueError('Bin memberships differ from previous plot')
ValueError('Cached bin edges differ')
ValueError('Input shapes differ')
ValueError('Unvalidated or mismatched input')
ValueError('coverage must lie between 0 and 1')
```

## qpower_analysis/conditional_tails.py

[完整源码](conditional_tails.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np
import zarr
from jhtdb_pipeline.store import spatial_slices
```

### `quantile_from_hist`

[实现：第 13 行](conditional_tails.py#L13)

```python
def quantile_from_hist(counts, edges, probability)
```

调用：`float`, `int`, `len`, `min`, `np.cumsum`, `np.searchsorted`

### `tail_edges`

[实现：第 22 行](conditional_tails.py#L22)

```python
def tail_edges(lo, hi, n)
```

调用：`abs`, `np.geomspace`, `np.linspace`, `np.sign`

### `bin_statistics`

[实现：第 28 行](conditional_tails.py#L28)

```python
def bin_statistics(x, y, edges)
```

调用：`ValueError`, `len`, `np.any`, `np.bincount`, `np.searchsorted`, `x.ravel`, `y.ravel`

显式异常：

```python
ValueError('A data point lies outside the bins')
```

### `fields`

[实现：第 38 行](conditional_tails.py#L38)

```python
def fields(velocity, gradient, qr, um)
```

调用：`ValueError`, `enumerate`, `len`, `list`, `min`, `np.einsum`, `np.isfinite`, `np.isfinite(q).all`, `np.isfinite(u2).all`, `print`, `q.astype`, `slice`, `spatial_slices`, `tuple`, `u2.astype`

显式异常：

```python
ValueError('Nonfinite inputs')
```

### `plot`

[实现：第 51 行](conditional_tails.py#L51)

```python
def plot(rows, direction, destination, min_count, shape, frame_time)
```

调用：`FuncFormatter`, `NullFormatter`, `abs`, `ax.grid`, `ax.set_xlim`, `ax.set_xscale`, `ax.set_xticks`, `ax.tick_params`, `ax.xaxis.set_major_formatter`, `ax.xaxis.set_minor_formatter`, `bottom.bar`, `bottom.set_xlabel`, `bottom.set_ylabel`, `bottom.set_yscale`, `destination.with_suffix`, `enumerate`, `fig.savefig`, `fig.suptitle`, `fig.supxlabel`, `float`, `matplotlib.use`, `np.array`, `np.geomspace`, `np.sign`, `np.where`, `plt.close`, `plt.subplots`, `sparse.any`, `subset[0].get`, `top.axhline`, `top.fill_between`, `top.legend`, `top.plot`, `top.scatter`, `top.set_title`, `top.set_ylabel`, `volume.sum`

### `run`

[实现：第 102 行](conditional_tails.py#L102)

```python
def run(folder)
```

调用：`(folder / 'config_used.json').read_text`, `(folder / 'run_summary.csv').open`, `(out / f'frame_{number:06d}_metadata.json').write_text`, `Path`, `Path('.local/cache/matplotlib').resolve`, `ValueError`, `abs`, `bin_statistics`, `bool`, `counts[name].sum`, `csv.DictReader`, `csv.DictWriter`, `dict`, `enumerate`, `fields`, `float`, `frame.get`, `int`, `json.dumps`, `json.loads`, `max`, `min`, `np.concatenate`, `np.histogram`, `np.linspace`, `np.prod`, `np.sign`, `np.sqrt`, `np.zeros`, `os.environ.setdefault`, `out.mkdir`, `plan['count'].sum`, `plot`, `prefix.with_suffix`, `prefix.with_suffix('.csv').open`, `print`, `quantile_from_hist`, `root.attrs.get`, `rows.append`, `rows[0].keys`, `str`, `sum`, `tail_edges`, `writer.writeheader`, `writer.writerows`, `x.max`, `x.min`, `zarr.open_group`, `zip`

显式异常：

```python
ValueError('Conditional bins omitted data')
ValueError('Degenerate quantile ranges')
ValueError('Input shapes differ')
ValueError('Quantile histogram omitted data')
ValueError('Unvalidated or mismatched input')
```

## qpower_analysis/qpower_analysis.py

[完整源码](qpower_analysis.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import plotly.graph_objects as go
import zarr
```

模块常量/配置：

```python
PRESSURE_NAMES = ('pressure', 'p', 'P')
```

### `PreflightError`

[实现：第 24 行](qpower_analysis.py#L24)

```python
class PreflightError(RuntimeError)
```

### `ArrayRef`

[实现：第 29 行](qpower_analysis.py#L29)

```python
class ArrayRef()
```

字段/默认值：

```python
path: Path
key: str | None
shape: tuple[int, ...]
```

### `_store_keys`

[实现：第 35 行](qpower_analysis.py#L35)

```python
def _store_keys(path: Path) -> set[str]
```

调用：`np.load`, `path.suffix.lower`, `root.array_keys`, `set`, `str`, `zarr.open_group`

### `_shape`

[实现：第 45 行](qpower_analysis.py#L45)

```python
def _shape(path: Path, key: str | None) -> tuple[int, ...]
```

调用：`PreflightError`, `np.load`, `path.suffix.lower`, `str`, `tuple`, `zarr.open_group`

显式异常：

```python
PreflightError(f'array {key!r} is absent from {path}')
```

### `_ref`

[实现：第 59 行](qpower_analysis.py#L59)

```python
def _ref(path_value: Any, key: str | None, label: str) -> ArrayRef
```

调用：`ArrayRef`, `Path`, `Path(path_value).expanduser`, `Path(path_value).expanduser().resolve`, `PreflightError`, `_shape`, `_store_keys`, `path.exists`, `path.suffix.lower`, `sorted`

显式异常：

```python
PreflightError(f'{label} array {actual_key!r} is absent from {path}; available={sorted(keys)}')
PreflightError(f'{label} path does not exist: {path}')
PreflightError(f'{label} path is not configured')
```

### `_load`

[实现：第 76 行](qpower_analysis.py#L76)

```python
def _load(ref: ArrayRef) -> np.ndarray
```

调用：`np.asarray`, `np.load`, `ref.path.suffix.lower`, `str`, `zarr.open_group`

### `preflight_frame`

[实现：第 88 行](qpower_analysis.py#L88)

```python
def preflight_frame(frame: dict[str, Any]) -> dict[str, Any]
```

调用：`Path`, `PreflightError`, `_ref`, `any`, `attrs.get`, `frame.get`, `gradient_store.is_dir`, `len`, `str`, `zarr.open_group`

显式异常：

```python
PreflightError(f'{label} has velocity but no pressure_path or pressure_gradient_path; pressure data is required')
PreflightError(f'{label} managed pressure-gradient cache has not passed validation')
PreflightError(f'{label} pressure gradient must have shape {(3, *spatial)}, got {combined.shape}')
PreflightError(f'{label} pressure shape {pressure_ref.shape} != velocity shape {spatial}')
PreflightError(f'{label} pressure-gradient frame/time metadata mismatch')
PreflightError(f'{label} pressure-gradient shapes must equal {spatial}')
PreflightError(f'{label} pressure_gradient_keys must contain one or three names')
PreflightError(f'{label} velocity must have shape (3,z,y,x), got {velocity.shape}')
```

### `preflight`

[实现：第 131 行](qpower_analysis.py#L131)

```python
def preflight(config: dict[str, Any]) -> list[dict[str, Any]]
```

调用：`PreflightError`, `config.get`, `preflight_frame`, `tuple`

显式异常：

```python
PreflightError('config.frames is empty')
PreflightError('event_mode must be positive, negative, or absolute')
PreflightError('spectral pressure gradients require a periodic domain on all axes')
PreflightError('this implementation requires stored spatial axis order zyx')
```

### `pressure_gradient`

[实现：第 146 行](qpower_analysis.py#L146)

```python
def pressure_gradient(pressure: np.ndarray, lengths_xyz: Iterable[float], method: str) -> np.ndarray
```

调用：`ValueError`, `map`, `np.fft.fftfreq`, `np.fft.fftn`, `np.fft.ifftn`, `np.gradient`, `np.stack`

显式异常：

```python
ValueError(f'unknown gradient_method {method!r}')
```

### `core_fields`

[实现：第 168 行](qpower_analysis.py#L168)

```python
def core_fields(velocity: np.ndarray, gradient: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]
```

调用：`ValueError`, `float`, `np.einsum`, `np.mean`, `np.sqrt`

显式异常：

```python
ValueError('velocity and pressure gradient must share shape (3,z,y,x)')
```

### `random_overlap_baseline`

[实现：第 176 行](qpower_analysis.py#L176)

```python
def random_overlap_baseline(a_count: int, b_count: int, total: int, intersection: int) -> dict[str, float]
```

Analytic independent random subsets with the observed subset sizes.

调用：`ValueError`, `max`, `min`

显式异常：

```python
ValueError('Invalid domain or event counts')
ValueError('Invalid intersection count')
```

### `event_mask`

[实现：第 192 行](qpower_analysis.py#L192)

```python
def event_mask(q: np.ndarray, q_rms: float, alpha: float, mode: str) -> np.ndarray
```

调用：`np.abs`

### `_write_csv`

[实现：第 198 行](qpower_analysis.py#L198)

```python
def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None
```

调用：`csv.DictWriter`, `list`, `path.open`, `writer.writeheader`, `writer.writerows`

### `conditional_rows`

[实现：第 205 行](qpower_analysis.py#L205)

```python
def conditional_rows(q: np.ndarray, u2: np.ndarray, q_rms: float, u2_mean: float, edges: np.ndarray, min_count: int) -> list[dict[str, Any]]
```

调用：`float`, `int`, `len`, `mask.sum`, `np.searchsorted`, `q.ravel`, `range`, `rows.append`, `u2.ravel`, `values[mask].mean`

### `plot_slices`

[实现：第 227 行](qpower_analysis.py#L227)

```python
def plot_slices(q: np.ndarray, destination: Path, title: str) -> None
```

调用：`axis.imshow`, `axis.set_title`, `fig.colorbar`, `fig.savefig`, `fig.suptitle`, `fig.tight_layout`, `float`, `np.abs`, `np.isfinite`, `np.percentile`, `plt.close`, `plt.subplots`, `zip`

### `plot_conditional`

[实现：第 239 行](qpower_analysis.py#L239)

```python
def plot_conditional(rows: list[dict[str, Any]], destination: Path, title: str) -> None
```

调用：`axis.axhline`, `axis.plot`, `axis.set`, `fig.savefig`, `fig.tight_layout`, `np.array`, `plt.close`, `plt.subplots`

### `voxel_surface`

[实现：第 247 行](qpower_analysis.py#L247)

```python
def voxel_surface(mask: np.ndarray, stride: int, full_shape: tuple[int, ...])
```

Exposed cube faces; adjacent cells of the same class share no inner face.

调用：`faces.reshape`, `len`, `np.arange`, `np.argwhere`, `np.array`, `np.asarray`, `np.concatenate`, `np.empty`, `np.minimum`, `np.pad`, `np.zeros`, `points.reshape`, `range`, `slice`, `triangles.append`, `tuple`, `vertices.append`

### `region_html`

[实现：第 276 行](qpower_analysis.py#L276)

```python
def region_html(mask_a: np.ndarray, mask_b: np.ndarray | None, destination: Path, names: tuple[str, str]=('A', 'B'), stride: int=1) -> None
```

调用：`ValueError`, `dict`, `fig.add_trace`, `fig.update_layout`, `fig.write_html`, `go.Figure`, `go.Scatter3d`, `int`, `max`, `np.nonzero`

显式异常：

```python
ValueError('Overlay masks must have the same shape')
```

### `_gradient_from_refs`

[实现：第 303 行](qpower_analysis.py#L303)

```python
def _gradient_from_refs(info: dict[str, Any], config: dict[str, Any]) -> tuple[np.ndarray, str]
```

调用：`_load`, `config.get`, `len`, `np.stack`, `pressure_gradient`

### `run`

[实现：第 312 行](qpower_analysis.py#L312)

```python
def run(config: dict[str, Any], infos: list[dict[str, Any]]) -> Path
```

调用：`(frame_dir / 'alpha_events').mkdir`, `(frame_dir / 'beta_events').mkdir`, `(frame_dir / 'metadata.json').write_text`, `(frame_dir / 'overlays').mkdir`, `(root / 'aggregate').mkdir`, `(root / 'config_used.json').write_text`, `(root / 'run_metadata.json').write_text`, `Path`, `RuntimeError`, `_gradient_from_refs`, `_load`, `_write_csv`, `a_masks.items`, `aggregate.append`, `all_conditional.extend`, `am.sum`, `b_masks.items`, `bm.sum`, `conditional_rows`, `config.get`, `core_fields`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `datetime.now(timezone.utc).strftime`, `edges.tolist`, `event_mask`, `float`, `frame_dir.mkdir`, `int`, `inter.sum`, `json.dumps`, `len`, `list`, `mask.mean`, `mask.sum`, `max`, `np.einsum`, `np.isfinite`, `np.isfinite(gradient).all`, `np.isfinite(velocity).all`, `np.linspace`, `np.mean`, `np.percentile`, `np.std`, `np.sum`, `overlap_rows.append`, `overlap_rows[-1].update`, `percentiles.append`, `plot_conditional`, `plot_slices`, `q.max`, `q.mean`, `q.min`, `random_overlap_baseline`, `range`, `region_html`, `root.exists`, `root.mkdir`, `row.update`, `summary_rows.append`, `threshold_rows.append`, `u2.max`, `u2.mean`, `u2.min`, `zip`

显式异常：

```python
RuntimeError(f"frame {frame_cfg['frame']} contains NaN or Inf")
RuntimeError(f'refusing to overwrite {root}')
```

### `main`

[实现：第 367 行](qpower_analysis.py#L367)

```python
def main(argv: list[str] | None=None) -> int
```

调用：`argparse.ArgumentParser`, `args.config.read_text`, `json.loads`, `len`, `parser.add_argument`, `parser.parse_args`, `preflight`, `print`, `run`

## qpower_analysis/scripts/download_then_qpower.py

[完整源码](scripts/download_then_qpower.py)

依赖：

```python
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from filelock import FileLock
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.input_fields import field_config
from jhtdb_pipeline.validation import atomic_json
```

模块常量/配置：

```python
PROJECT = Path(__file__).resolve().parents[2]
```

### `main`

[实现：第 21 行](scripts/download_then_qpower.py#L21)

```python
def main()
```

调用：`(PROJECT / 'qpower_analysis/output').mkdir`, `(job / 'pipeline_config.yaml').write_text`, `(job / f'{stage}.log').open`, `FileLock`, `Path`, `Path(args.analysis_config).read_text`, `Path(args.pipeline_config).read_text`, `argparse.ArgumentParser`, `args.job_dir.resolve`, `atomic_json`, `cfg.physical_time`, `cfg.raw_store_path`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `field_config`, `field_config(cfg, 'pressure_gradient').raw_store_path`, `int`, `job.mkdir`, `json.dumps`, `json.loads`, `load_config`, `os.chdir`, `os.getpid`, `parser.add_argument`, `parser.parse_args`, `print`, `stages.append`, `stages.extend`, `status.update`, `status['completed_stages'].append`, `str`, `subprocess.run`, `type`, `update`

### `main.update`

[实现：第 33 行](scripts/download_then_qpower.py#L33)

```python
def main.update(**values)
```

调用：`atomic_json`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `json.dumps`, `print`, `status.update`

## qpower_analysis/scripts/quickstart_qpower_subset.py

[完整源码](scripts/quickstart_qpower_subset.py)

依赖：

```python
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import numpy as np
import zarr
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.input_fields import field_config
from jhtdb_pipeline.store import array_sha256
```

模块常量/配置：

```python
PROJECT = Path(__file__).resolve().parents[2]
```

### `main`

[实现：第 23 行](scripts/quickstart_qpower_subset.py#L23)

```python
def main()
```

调用：`(PROJECT / 'qpower_analysis/config.example.json').read_text`, `(job / 'subset_provenance.json').write_text`, `ValueError`, `analysis.update`, `any`, `argparse.ArgumentParser`, `array_sha256`, `arrays.items`, `cfg.physical_time`, `config_path.write_text`, `connection.close`, `connection.execute`, `connection.execute('SELECT x0,y0,z0,nx,ny,nz,status,sha256 FROM tiles WHERE dataset=? AND time_index=1 AND x0<? AND y0<? AND z0<?', (cfg.dataset, nx, ny, nz)).fetchall`, `datetime.now`, `datetime.now(timezone.utc).strftime`, `dict`, `expected.items`, `expected.update`, `field_config`, `job.mkdir`, `json.dumps`, `json.loads`, `len`, `list`, `load_config`, `np.ascontiguousarray`, `np.isfinite`, `np.isfinite(values).all`, `np.save`, `parser.add_argument`, `parser.parse_args`, `pressure_cfg.catalog_path.resolve`, `pressure_cfg.catalog_path.resolve().as_uri`, `print`, `range`, `reversed`, `root.attrs.get`, `sqlite3.connect`, `str`, `subprocess.run`, `view.raw_store_path`, `zarr.open_group`, `zip`

显式异常：

```python
ValueError('Crop dimensions must be positive multiples of 16 within the source grid')
ValueError('Subset contains an unverified pressure tile')
ValueError('Subset does not have complete catalog coverage')
ValueError(f'Pressure checksum mismatch at {(x, y, z)}')
ValueError(f'{field}: incomplete or non-finite subset; no download attempted')
ValueError(f'{field}: source metadata mismatch or unvalidated velocity')
ValueError(f'{field}: unexpected source shape')
```

## qpower_analysis/threshold_contributions.py

[完整源码](threshold_contributions.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import zarr
from jhtdb_pipeline.store import spatial_slices
```

### `histograms`

[实现：第 12 行](threshold_contributions.py#L12)

```python
def histograms(q, u2, q_rms, u2_mean, alphas, betas)
```

调用：`(ai.astype(np.int32) * (len(betas) + 1) + bi).ravel`, `ai.astype`, `len`, `np.bincount`, `np.bincount(index, minlength=size).reshape`, `np.bincount(index, weights=values.ravel(), minlength=size).reshape`, `np.maximum`, `np.square`, `np.zeros`, `values.ravel`, `weights.items`

### `run`

[实现：第 30 行](threshold_contributions.py#L30)

```python
def run(folder)
```

调用：`(folder / 'config_used.json').read_text`, `(folder / 'contribution_metadata.json').write_text`, `(folder / 'overlap_statistics.csv').open`, `(folder / 'run_summary.csv').open`, `ValueError`, `accumulated.items`, `config.get`, `csv.DictReader`, `csv.DictWriter`, `dict`, `enumerate`, `float`, `frame.get`, `histograms`, `histograms(q, u2, qr, um, alphas, betas).items`, `int`, `json.dumps`, `json.loads`, `len`, `list`, `min`, `np.einsum`, `np.isfinite`, `np.isfinite(q).all`, `np.isfinite(u2).all`, `path.with_suffix`, `print`, `root.attrs.get`, `rows.append`, `set`, `slice`, `sorted`, `spatial_slices`, `temp.open`, `temp.replace`, `totals.append`, `tuple`, `values.sum`, `values[ai:, bi:].sum`, `writer.writeheader`, `writer.writerows`, `zarr.open_group`

显式异常：

```python
ValueError('Input must be a validated matching frame')
ValueError('Input shapes differ')
ValueError('Nonfinite source field')
ValueError('This contribution report uses positive q events')
ValueError('Threshold membership differs from existing overlap statistics')
ValueError('Thresholds must be unique')
```

