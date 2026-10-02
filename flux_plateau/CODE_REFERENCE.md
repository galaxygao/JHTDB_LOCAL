# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## flux_plateau/__init__.py

[完整源码](__init__.py)

此入口只包含导入、常量或顶层调用。

## flux_plateau/plot_pi_epsilon_vs_k.py

[完整源码](plot_pi_epsilon_vs_k.py)

依赖：

```python
from __future__ import annotations
import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
import plotly.graph_objects as go
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.dashboard import complete_result_paths
from jhtdb_pipeline.validation import atomic_json
```

模块常量/配置：

```python
ANALYSIS_VERSION = 2
DEFAULT_VISCOSITY = 0.000185
DEFAULT_EPSILON_REFERENCE = 0.0928
DEFAULT_ETA_REFERENCE = 0.00287
HALF_GAIN_KR = math.sqrt(24.0 * math.log(2.0))
PAPER_R_OVER_ETA = (4.0, 8.0, 13.0, 17.0, 25.0, 40.0, 80.0, 120.0, 180.0, 250.0, 400.0, 700.0, 1300.0, 1600.0)
PAPER_FLUX_OVER_EPSILON = (0.012, 0.2, 0.55, 0.72, 0.95, 1.25, 1.35, 1.4, 1.4, 1.38, 1.3, 1.15, 0.75, 0.45)
```

### `FluxPoint`

[实现：第 33 行](plot_pi_epsilon_vs_k.py#L33)

```python
class FluxPoint()
```

字段/默认值：

```python
group_key: tuple[str, float]
group_label: str
sigma_grid: float
cutoff_wavenumber: float
cutoff_modes: float
stored_mean_pi: float
forward_mean_pi: float
pi_over_epsilon: float
source_path: Path
equivalent_r_over_eta: float
note: str = 'computed result'
```

### `_smooth_group`

[实现：第 47 行](plot_pi_epsilon_vs_k.py#L47)

```python
def _smooth_group(manifest: dict) -> tuple[tuple[str, float], str]
```

调用：`float`

### `_read_json`

[实现：第 52 行](plot_pi_epsilon_vs_k.py#L52)

```python
def _read_json(path: Path) -> dict
```

调用：`json.loads`, `path.read_text`

### `discover_flux_inputs`

[实现：第 56 行](plot_pi_epsilon_vs_k.py#L56)

```python
def discover_flux_inputs(result_root: Path, time_index: int) -> tuple[list[tuple[Path, dict, dict]], float]
```

调用：`RuntimeError`, `_read_json`, `any`, `complete_result_paths`, `cq_path.is_file`, `float`, `gradient_rms_values.append`, `int`, `manifest.get`, `manifest_path.is_file`, `math.isclose`, `qa_path.is_file`, `records.append`

显式异常：

```python
RuntimeError('results disagree on the full-domain raw-gradient RMS')
RuntimeError(f'no complete smooth-sharp results for frame {time_index}')
```

### `build_flux_points`

[实现：第 92 行](plot_pi_epsilon_vs_k.py#L92)

```python
def build_flux_points(records: list[tuple[Path, dict, dict]], *, grid_size: int, domain_length: float, epsilon_reference: float, eta_reference: float) -> list[FluxPoint]
```

调用：`FluxPoint`, `Path`, `_smooth_group`, `float`, `manifest.get`, `math.log`, `math.sqrt`, `points.append`, `zip`

### `make_figure`

[实现：第 151 行](plot_pi_epsilon_vs_k.py#L151)

```python
def make_figure(points: list[FluxPoint], epsilon_reference: float) -> go.Figure
```

调用：`figure.add_hline`, `figure.add_hrect`, `figure.add_trace`, `figure.update_layout`, `go.Figure`, `go.Scatter`, `math.isnan`, `sorted`

### `make_log_k_figure`

[实现：第 229 行](plot_pi_epsilon_vs_k.py#L229)

```python
def make_log_k_figure(points: list[FluxPoint], epsilon_reference: float) -> go.Figure
```

Plot the same flux data against the common half-gain wavenumber.

调用：`figure.add_hline`, `figure.add_hrect`, `figure.add_trace`, `figure.update_layout`, `go.Figure`, `go.Scatter`, `math.isnan`, `sorted`

### `write_outputs`

[实现：第 304 行](plot_pi_epsilon_vs_k.py#L304)

```python
def write_outputs(output_dir: Path, points: list[FluxPoint], *, epsilon_reference: float, viscosity: float, raw_gradient_rms: float, eta_reference: float, epsilon_instantaneous: float, eta_instantaneous: float, time_index: int) -> Path
```

调用：`atomic_json`, `csv.writer`, `csv_path.open`, `figure.write_html`, `len`, `make_figure`, `make_log_k_figure`, `make_log_k_figure(points, epsilon_reference).write_html`, `output_dir.mkdir`, `sorted`, `str`, `writer.writerow`

### `main`

[实现：第 392 行](plot_pi_epsilon_vs_k.py#L392)

```python
def main(argv: list[str] | None=None) -> int
```

调用：`Path`, `Path(__file__).resolve`, `ValueError`, `argparse.ArgumentParser`, `build_flux_points`, `discover_flux_inputs`, `getattr`, `load_config`, `math.isfinite`, `parser.add_argument`, `parser.parse_args`, `print`, `write_outputs`

显式异常：

```python
ValueError(f'{name} must be finite and positive')
```

