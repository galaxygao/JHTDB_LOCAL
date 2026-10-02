# 逐函数代码参考

由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。

## dashboard.py

[完整源码](../dashboard.py)

依赖：

```python
from jhtdb_pipeline.dashboard import main
```

此入口只包含导入、常量或顶层调用。

## deploy.py

[完整源码](../deploy.py)

依赖：

```python
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import venv
```

模块常量/配置：

```python
PROJECT = Path(__file__).resolve().parent
```

### `environment_python`

[实现：第 16 行](../deploy.py#L16)

```python
def environment_python(system: str) -> Path
```

调用：`{'win32': 'windows', 'darwin': 'mac'}.get`

### `run`

[实现：第 22 行](../deploy.py#L22)

```python
def run(command, *, keep_awake=False)
```

调用：`str`, `subprocess.run`

### `prepare_config`

[实现：第 29 行](../deploy.py#L29)

```python
def prepare_config(python: Path, data_root: Path, token_file: Path) -> Path
```

Derive a local config without editing the shared production YAML.

调用：`config.parent.mkdir`, `run`

### `pipeline_commands`

[实现：第 47 行](../deploy.py#L47)

```python
def pipeline_commands(python: Path, config: Path, time_index: int, stage: str)
```

调用：`commands.append`, `str`

### `main`

[实现：第 60 行](../deploy.py#L60)

```python
def main(argv=None)
```

调用：`(PROJECT / 'qpower_analysis/config.example.json').read_text`, `(root / 'deploy.log').open`, `(root / 'deploy.pid').write_text`, `Path.home`, `argparse.ArgumentParser`, `args.data_root.expanduser`, `args.data_root.expanduser().resolve`, `child.append`, `environment_python`, `frame.update`, `json.dumps`, `json.loads`, `local_token.is_file`, `os.environ.get`, `os.environ.setdefault`, `parser.add_argument`, `parser.error`, `parser.parse_args`, `pipeline_commands`, `prepare_config`, `print`, `python.is_file`, `root.mkdir`, `run`, `str`, `subprocess.Popen`, `token.expanduser`, `token.expanduser().resolve`, `venv.EnvBuilder`, `venv.EnvBuilder(with_pip=True).create`

## scripts/rebuild_v7.py

[完整源码](../scripts/rebuild_v7.py)

依赖：

```python
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
from jhtdb_pipeline.config import load_config, RESULT_SCHEMA_VERSION
from jhtdb_pipeline.processing import process_batch, resource_plan
from jhtdb_pipeline.validation import validate_snapshot
```

### `main`

[实现：第 12 行](../scripts/rebuild_v7.py#L12)

```python
def main(argv=None)
```

调用：`(source / 'COMPLETE').is_file`, `(source / 'manifest.json').read_text`, `argparse.ArgumentParser`, `args.result_root.resolve`, `args.source_result.resolve`, `cfg.result_path`, `cfg.with_filter`, `cfg.with_sharp_edge_width_fraction`, `float`, `int`, `json.dumps`, `json.loads`, `load_config`, `parser.add_argument`, `parser.error`, `parser.parse_args`, `payload.get`, `print`, `process_batch`, `replace`, `resource_plan`, `str`, `validate_snapshot`

## scripts/update_docs.py

[完整源码](../scripts/update_docs.py)

依赖：

```python
from __future__ import annotations
import argparse
import ast
import os
from pathlib import Path
import re
```

模块常量/配置：

```python
ROOT = Path(__file__).resolve().parents[1]
SUBPROJECTS = ('block_statistics', 'qpower_analysis', 'pi_pdf', 'pi_slices', 'scatter', 'regime_pi', 'flux_plateau')
```

### `sources`

[实现：第 13 行](../scripts/update_docs.py#L13)

```python
def sources()
```

调用：`(ROOT / folder).rglob`, `any`, `p.relative_to`, `paths.extend`, `set`, `sorted`

### `link`

[实现：第 21 行](../scripts/update_docs.py#L21)

```python
def link(path, destination, line=None)
```

调用：`Path`, `Path(os.path.relpath(path, destination.parent)).as_posix`, `os.path.relpath`

### `text`

[实现：第 26 行](../scripts/update_docs.py#L26)

```python
def text(value)
```

调用：`str`, `str(value).replace`, `str(value).replace('|', '\\|').replace`

### `symbols`

[实现：第 30 行](../scripts/update_docs.py#L30)

```python
def symbols(tree)
```

调用：`ast.iter_child_nodes`, `isinstance`, `list`, `walk`

### `symbols.walk`

[实现：第 31 行](../scripts/update_docs.py#L31)

```python
def symbols.walk(node, prefix='')
```

调用：`ast.iter_child_nodes`, `isinstance`, `walk`

### `reference`

[实现：第 42 行](../scripts/update_docs.py#L42)

```python
def reference(paths, destination)
```

调用：`', '.join`, `'\n'.join`, `ast.get_docstring`, `ast.parse`, `ast.unparse`, `ast.walk`, `isinstance`, `link`, `path.read_text`, `path.relative_to`, `sorted`, `symbols`

### `cli_reference`

[实现：第 81 行](../scripts/update_docs.py#L81)

```python
def cli_reference(paths)
```

调用：`'\n'.join`, `ast.get_source_segment`, `ast.parse`, `ast.walk`, `isinstance`, `link`, `out.extend`, `path.read_text`, `path.relative_to`, `sorted`

### `check_links`

[实现：第 94 行](../scripts/update_docs.py#L94)

```python
def check_links()
```

调用：`(ROOT / 'docs').glob`, `(ROOT / folder).glob`, `(path.parent / target).exists`, `path.read_text`, `path.relative_to`, `paths.extend`, `problems.append`, `raw.split`, `re.findall`, `re.sub`, `target.startswith`

### `main`

[实现：第 109 行](../scripts/update_docs.py#L109)

```python
def main(argv=None)
```

调用：`'\n'.join`, `argparse.ArgumentParser`, `bool`, `check_links`, `cli_reference`, `errors.append`, `generated.items`, `int`, `len`, `p.relative_to`, `parser.add_argument`, `parser.parse_args`, `path.exists`, `path.read_text`, `path.relative_to`, `path.write_text`, `print`, `reference`, `sources`

## src/jhtdb_pipeline/__init__.py

[完整源码](../src/jhtdb_pipeline/__init__.py)

模块常量/配置：

```python
__version__ = '0.7.1'
```

此入口只包含导入、常量或顶层调用。

## src/jhtdb_pipeline/__main__.py

[完整源码](../src/jhtdb_pipeline/__main__.py)

依赖：

```python
from .cli import main
```

此入口只包含导入、常量或顶层调用。

## src/jhtdb_pipeline/auth.py

[完整源码](../src/jhtdb_pipeline/auth.py)

依赖：

```python
from __future__ import annotations
import os
import stat
from .config import PipelineConfig
```

### `token_source`

[实现：第 9 行](../src/jhtdb_pipeline/auth.py#L9)

```python
def token_source(cfg: PipelineConfig) -> str | None
```

调用：`cfg.token_file.is_file`, `cfg.token_file.stat`, `os.environ.get`, `os.environ.get('JHTDB_TOKEN', '').strip`

### `has_token`

[实现：第 21 行](../src/jhtdb_pipeline/auth.py#L21)

```python
def has_token(cfg: PipelineConfig) -> bool
```

调用：`token_source`

### `get_token`

[实现：第 25 行](../src/jhtdb_pipeline/auth.py#L25)

```python
def get_token(cfg: PipelineConfig) -> str
```

调用：`PermissionError`, `RuntimeError`, `cfg.token_file.is_file`, `cfg.token_file.read_text`, `cfg.token_file.read_text(encoding='utf-8').strip`, `cfg.token_file.stat`, `os.environ.get`, `os.environ.get('JHTDB_TOKEN', '').strip`, `stat.S_IMODE`

显式异常：

```python
PermissionError(f'token file permissions must be 0600 or stricter: {cfg.token_file}')
RuntimeError('JHTDB token is not configured; set JHTDB_TOKEN for this process or create the protected token file configured by auth.token_file')
RuntimeError('configured JHTDB token file is empty')
```

## src/jhtdb_pipeline/catalog.py

[完整源码](../src/jhtdb_pipeline/catalog.py)

依赖：

```python
from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from .planning import Tile
```

### `_now`

[实现：第 11 行](../src/jhtdb_pipeline/catalog.py#L11)

```python
def _now() -> str
```

调用：`datetime.now`, `datetime.now(timezone.utc).isoformat`

### `Catalog`

[实现：第 15 行](../src/jhtdb_pipeline/catalog.py#L15)

```python
class Catalog()
```

Small persistent ledger for resumable JHTDB tile acquisition.

### `Catalog.__init__`

[实现：第 18 行](../src/jhtdb_pipeline/catalog.py#L18)

```python
def Catalog.__init__(self, path: Path)
```

调用：`path.parent.mkdir`, `self.connection.commit`, `self.connection.execute`, `self.connection.executescript`, `sqlite3.connect`

### `Catalog.close`

[实现：第 62 行](../src/jhtdb_pipeline/catalog.py#L62)

```python
def Catalog.close(self) -> None
```

调用：`self.connection.close`

### `Catalog.__enter__`

[实现：第 65 行](../src/jhtdb_pipeline/catalog.py#L65)

```python
def Catalog.__enter__(self) -> 'Catalog'
```

### `Catalog.__exit__`

[实现：第 68 行](../src/jhtdb_pipeline/catalog.py#L68)

```python
def Catalog.__exit__(self, *_: object) -> None
```

调用：`self.close`

### `Catalog.plan_snapshot`

[实现：第 71 行](../src/jhtdb_pipeline/catalog.py#L71)

```python
def Catalog.plan_snapshot(self, dataset: str, time_index: int, physical_time: float, tiles: Iterable[Tile]) -> None
```

调用：`_now`, `len`, `list`, `self.connection.execute`

### `Catalog.tile`

[实现：第 103 行](../src/jhtdb_pipeline/catalog.py#L103)

```python
def Catalog.tile(self, dataset: str, time_index: int, key: str) -> sqlite3.Row | None
```

调用：`self.connection.execute`, `self.connection.execute('SELECT * FROM tiles WHERE dataset=? AND time_index=? AND tile_key=?', (dataset, time_index, key)).fetchone`

### `Catalog.mark_attempt`

[实现：第 109 行](../src/jhtdb_pipeline/catalog.py#L109)

```python
def Catalog.mark_attempt(self, dataset: str, time_index: int, key: str) -> None
```

调用：`_now`, `self.connection.execute`

### `Catalog.mark_verified`

[实现：第 118 行](../src/jhtdb_pipeline/catalog.py#L118)

```python
def Catalog.mark_verified(self, dataset: str, time_index: int, key: str, sha256: str, byte_count: int) -> None
```

调用：`_now`, `self.connection.execute`

### `Catalog.set_snapshot_status`

[实现：第 134 行](../src/jhtdb_pipeline/catalog.py#L134)

```python
def Catalog.set_snapshot_status(self, dataset: str, time_index: int, status: str, manifest_hash: str | None=None) -> None
```

调用：`_now`, `self.connection.execute`

### `Catalog.snapshot`

[实现：第 149 行](../src/jhtdb_pipeline/catalog.py#L149)

```python
def Catalog.snapshot(self, dataset: str, time_index: int) -> sqlite3.Row | None
```

调用：`self.connection.execute`, `self.connection.execute('SELECT * FROM snapshots WHERE dataset=? AND time_index=?', (dataset, time_index)).fetchone`

### `Catalog.snapshots`

[实现：第 155 行](../src/jhtdb_pipeline/catalog.py#L155)

```python
def Catalog.snapshots(self, dataset: str) -> list[sqlite3.Row]
```

调用：`list`, `self.connection.execute`, `self.connection.execute('SELECT * FROM snapshots WHERE dataset=? ORDER BY time_index', (dataset,)).fetchall`

### `Catalog.tiles`

[实现：第 162 行](../src/jhtdb_pipeline/catalog.py#L162)

```python
def Catalog.tiles(self, dataset: str, time_index: int) -> list[sqlite3.Row]
```

调用：`list`, `self.connection.execute`, `self.connection.execute('SELECT * FROM tiles\n                   WHERE dataset=? AND time_index=? ORDER BY z0,y0,x0', (dataset, time_index)).fetchall`

### `Catalog.tile_progress`

[实现：第 171 行](../src/jhtdb_pipeline/catalog.py#L171)

```python
def Catalog.tile_progress(self, dataset: str, time_index: int) -> dict[str, int]
```

调用：`counts.values`, `int`, `self.connection.execute`, `self.connection.execute('SELECT status, COUNT(*) AS count FROM tiles\n               WHERE dataset=? AND time_index=? GROUP BY status', (dataset, time_index)).fetchall`, `str`, `sum`

## src/jhtdb_pipeline/cli.py

[完整源码](../src/jhtdb_pipeline/cli.py)

依赖：

```python
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from .auth import has_token, token_source
from .catalog import Catalog
from .config import FILTER_TYPES, load_config
from .cq import run_cq
from .doctor import doctor
from .jhtdb import fetch_snapshot, smoke
from .input_fields import field_config
from .planning import plan
from .regime_pi import run_regime_pi_statistics
from .processing import finalize_result, process_batch, process_full, resource_plan, reuse_complete_result
from .sbar_qa import run_sbar_qa
from .validation import validate_snapshot
from .weak_asymmetry import run_weak_asymmetry
```

模块常量/配置：

```python
DEFAULT_CONFIG = 'configs/pipeline.yaml'
```

### `_config`

[实现：第 34 行](../src/jhtdb_pipeline/cli.py#L34)

```python
def _config(parser: argparse.ArgumentParser) -> None
```

调用：`parser.add_argument`

### `_frame`

[实现：第 38 行](../src/jhtdb_pipeline/cli.py#L38)

```python
def _frame(parser: argparse.ArgumentParser) -> None
```

调用：`_config`, `parser.add_argument`

### `_sigma`

[实现：第 43 行](../src/jhtdb_pipeline/cli.py#L43)

```python
def _sigma(parser: argparse.ArgumentParser) -> None
```

调用：`parser.add_argument`

### `build_parser`

[实现：第 57 行](../src/jhtdb_pipeline/cli.py#L57)

```python
def build_parser() -> argparse.ArgumentParser
```

调用：`_config`, `_frame`, `_sigma`, `argparse.ArgumentParser`, `auth_parser.add_argument`, `command.add_argument`, `commands.add_parser`, `doctor_parser.add_argument`, `gui.add_argument`, `parser.add_subparsers`

### `_status`

[实现：第 116 行](../src/jhtdb_pipeline/cli.py#L116)

```python
def _status(cfg) -> dict[str, object]
```

调用：`(path / 'COMPLETE').is_file`, `Catalog`, `catalog.snapshots`, `catalog.tile_progress`, `cfg.catalog_path.exists`, `cfg.result_root.exists`, `cfg.result_root.glob`, `cfg.result_root.iterdir`, `dict`, `field_config`, `filter_batches.append`, `inputs.append`, `item.update`, `json.loads`, `manifest.get`, `manifest_path.is_file`, `manifest_path.read_text`, `path.is_dir`, `path.name.endswith`, `path.name.startswith`, `path.read_text`, `pressure_cfg.catalog_path.exists`, `pressure_inputs.append`, `results.append`, `sorted`, `str`

### `_selected_sigmas`

[实现：第 176 行](../src/jhtdb_pipeline/cli.py#L176)

```python
def _selected_sigmas(cfg, sigma_grid: float | None) -> tuple[float, ...]
```

调用：`float`

### `_run_single_frame`

[实现：第 180 行](../src/jhtdb_pipeline/cli.py#L180)

```python
def _run_single_frame(cfg, time_index: int, sigma_grid: float | None, sigma_grids: list[float] | None=None) -> list[Path]
```

调用：`RuntimeError`, `ValueError`, `_selected_sigmas`, `doctor`, `fetch_snapshot`, `float`, `json.dumps`, `pending.append`, `process_batch`, `reuse_complete_result`, `tuple`, `validate_snapshot`

显式异常：

```python
RuntimeError(f"local doctor failed: {json.dumps(report['checks'])}")
ValueError('use only one of --sigma-grid and --sigma-grids')
```

### `_print_paths`

[实现：第 212 行](../src/jhtdb_pipeline/cli.py#L212)

```python
def _print_paths(paths: list[Path]) -> None
```

调用：`json.dumps`, `len`, `print`, `str`

### `main`

[实现：第 219 行](../src/jhtdb_pipeline/cli.py#L219)

```python
def main(argv: list[str] | None=None) -> int
```

调用：`Path`, `Path(__file__).with_name`, `Path(args.config).resolve`, `ValueError`, `_print_paths`, `_run_single_frame`, `_selected_sigmas`, `_status`, `all`, `build_parser`, `build_parser().parse_args`, `cfg.with_filter`, `cfg.with_sharp_edge_width_fraction`, `doctor`, `fetch_snapshot`, `field_config`, `finalize_result`, `float`, `getattr`, `has_token`, `json.dumps`, `len`, `load_config`, `os.environ.copy`, `plan`, `print`, `process_batch`, `process_full`, `reconfigure`, `resource_plan`, `run_cq`, `run_regime_pi_statistics`, `run_sbar_qa`, `run_weak_asymmetry`, `smoke`, `str`, `subprocess.run`, `token_source`, `tuple`, `validate_snapshot`

显式异常：

```python
ValueError('use only one of --sigma-grid and --sigma-grids')
```

## src/jhtdb_pipeline/config.py

[完整源码](../src/jhtdb_pipeline/config.py)

依赖：

```python
from __future__ import annotations
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import yaml
```

模块常量/配置：

```python
RESULT_SCHEMA_VERSION = 7
FILTER_TYPES = ('gaussian', 'smooth_sharp')
```

### `_tuple3`

[实现：第 16 行](../src/jhtdb_pipeline/config.py#L16)

```python
def _tuple3(value: Any, name: str) -> tuple[int, int, int]
```

调用：`ValueError`, `any`, `int`, `isinstance`, `len`, `tuple`

显式异常：

```python
ValueError(f'{name} must contain exactly three integers')
ValueError(f'{name} values must be positive')
```

### `_path`

[实现：第 25 行](../src/jhtdb_pipeline/config.py#L25)

```python
def _path(value: Any, name: str) -> Path
```

调用：`Path`, `ValueError`, `os.path.expandvars`, `os.path.expandvars(str(value)).strip`, `str`

显式异常：

```python
ValueError(f'{name} must be configured')
```

### `_mapping`

[实现：第 32 行](../src/jhtdb_pipeline/config.py#L32)

```python
def _mapping(value: Any, name: str) -> Mapping[str, Any]
```

调用：`ValueError`, `isinstance`

显式异常：

```python
ValueError(f'{name} must be a mapping')
```

### `_reject_unknown`

[实现：第 40 行](../src/jhtdb_pipeline/config.py#L40)

```python
def _reject_unknown(mapping: Mapping[str, Any], allowed: set[str], name: str) -> None
```

调用：`', '.join`, `ValueError`, `set`, `sorted`

显式异常：

```python
ValueError(f"unknown {name} fields: {', '.join(unknown)}")
```

### `sigma_tag`

[实现：第 46 行](../src/jhtdb_pipeline/config.py#L46)

```python
def sigma_tag(value: float) -> str
```

调用：`float`, `format`, `format(float(value), '.8g').replace`, `format(float(value), '.8g').replace('-', 'm').replace`

### `result_zarr_name`

[实现：第 50 行](../src/jhtdb_pipeline/config.py#L50)

```python
def result_zarr_name(sigma_grid: float) -> str
```

调用：`sigma_tag`

### `_sigma_values`

[实现：第 54 行](../src/jhtdb_pipeline/config.py#L54)

```python
def _sigma_values(value: Any) -> tuple[float, ...]
```

调用：`ValueError`, `any`, `float`, `isinstance`, `len`, `math.isfinite`, `set`, `sigma_tag`, `tuple`

显式异常：

```python
ValueError('physics.sigma_grid must contain at least one value')
ValueError('physics.sigma_grid values must be finite and positive')
ValueError('physics.sigma_grid values must be unique')
ValueError('physics.sigma_grid values must have unique result tags')
```

### `PipelineConfig`

[实现：第 69 行](../src/jhtdb_pipeline/config.py#L69)

```python
class PipelineConfig()
```

字段/默认值：

```python
dataset: str
variable: str
grid_shape: tuple[int, int, int]
domain_length: float
stored_time_step: float
state_root: Path
run_root: Path
result_root: Path
token_file: Path | None
request_shape: tuple[int, int, int]
tile_shape: tuple[int, int, int]
retries: int
backoff_seconds: float
request_cooldown_seconds: float
compression_level: int
compression_threads: int
persistent_safety_reserve_gib: float
scratch_safety_reserve_gib: float
divergence_relative_rms_max: float
divergence_relative_max_max: float
energy_identity_relative_rms_max: float
s_bar_vs_pi_net_max: float
cq_partition_relative_max: float
sigma_grid: float
epsilon_abs: float
epsilon_rel: float
fft_workers: int
fft_slab_width: int
cleanup_scratch_on_success: bool
sigma_grids: tuple[float, ...]
filter_type: str
sharp_edge_width_fraction: float
fft_cache_mode: str = 'memory'
```

### `PipelineConfig.sharp_edge_tag`

[实现：第 105 行](../src/jhtdb_pipeline/config.py#L105)

```python
def PipelineConfig.sharp_edge_tag(self) -> str
```

调用：`sigma_tag`

### `PipelineConfig.catalog_path`

[实现：第 109 行](../src/jhtdb_pipeline/config.py#L109)

```python
def PipelineConfig.catalog_path(self) -> Path
```

### `PipelineConfig.manifest_path`

[实现：第 113 行](../src/jhtdb_pipeline/config.py#L113)

```python
def PipelineConfig.manifest_path(self) -> Path
```

### `PipelineConfig.qa_path`

[实现：第 117 行](../src/jhtdb_pipeline/config.py#L117)

```python
def PipelineConfig.qa_path(self) -> Path
```

### `PipelineConfig.lock_path`

[实现：第 121 行](../src/jhtdb_pipeline/config.py#L121)

```python
def PipelineConfig.lock_path(self) -> Path
```

### `PipelineConfig.run_path`

[实现：第 124 行](../src/jhtdb_pipeline/config.py#L124)

```python
def PipelineConfig.run_path(self, time_index: int) -> Path
```

调用：`self.physical_time`

### `PipelineConfig.persistent_input_path`

[实现：第 128 行](../src/jhtdb_pipeline/config.py#L128)

```python
def PipelineConfig.persistent_input_path(self, time_index: int) -> Path
```

调用：`self.physical_time`

### `PipelineConfig.persistent_raw_store_path`

[实现：第 132 行](../src/jhtdb_pipeline/config.py#L132)

```python
def PipelineConfig.persistent_raw_store_path(self, time_index: int) -> Path
```

调用：`self.persistent_input_path`

### `PipelineConfig.raw_store_path`

[实现：第 135 行](../src/jhtdb_pipeline/config.py#L135)

```python
def PipelineConfig.raw_store_path(self, time_index: int) -> Path
```

调用：`self.persistent_raw_store_path`

### `PipelineConfig.strain_store_path`

[实现：第 138 行](../src/jhtdb_pipeline/config.py#L138)

```python
def PipelineConfig.strain_store_path(self, time_index: int) -> Path
```

Per-frame, filter-independent full-domain S_ij S_ij cache.

调用：`Path`, `Path(__file__).resolve`

### `PipelineConfig.workspace_path`

[实现：第 142 行](../src/jhtdb_pipeline/config.py#L142)

```python
def PipelineConfig.workspace_path(self, time_index: int, sigma_grid: float | None=None) -> Path
```

调用：`self.run_path`, `sigma_tag`

### `PipelineConfig.result_id`

[实现：第 151 行](../src/jhtdb_pipeline/config.py#L151)

```python
def PipelineConfig.result_id(self, time_index: int, sigma_grid: float | None=None) -> str
```

调用：`sigma_tag`

### `PipelineConfig.staging_result_path`

[实现：第 160 行](../src/jhtdb_pipeline/config.py#L160)

```python
def PipelineConfig.staging_result_path(self, time_index: int, sigma_grid: float | None=None) -> Path
```

调用：`self.result_id`

### `PipelineConfig.result_path`

[实现：第 163 行](../src/jhtdb_pipeline/config.py#L163)

```python
def PipelineConfig.result_path(self, time_index: int, sigma_grid: float | None=None) -> Path
```

调用：`self.result_id`

### `PipelineConfig.batch_manifest_path`

[实现：第 166 行](../src/jhtdb_pipeline/config.py#L166)

```python
def PipelineConfig.batch_manifest_path(self, time_index: int) -> Path
```

调用：`self.physical_time`

### `PipelineConfig.shared_result_path`

[实现：第 177 行](../src/jhtdb_pipeline/config.py#L177)

```python
def PipelineConfig.shared_result_path(self, time_index: int) -> Path
```

调用：`self.physical_time`

### `PipelineConfig.shared_staging_result_path`

[实现：第 181 行](../src/jhtdb_pipeline/config.py#L181)

```python
def PipelineConfig.shared_staging_result_path(self, time_index: int) -> Path
```

调用：`self.physical_time`

### `PipelineConfig.shared_gradient_store_path`

[实现：第 185 行](../src/jhtdb_pipeline/config.py#L185)

```python
def PipelineConfig.shared_gradient_store_path(self, time_index: int) -> Path
```

调用：`self.shared_result_path`

### `PipelineConfig.full_shape_zyx`

[实现：第 189 行](../src/jhtdb_pipeline/config.py#L189)

```python
def PipelineConfig.full_shape_zyx(self) -> tuple[int, int, int]
```

### `PipelineConfig.bytes_per_snapshot`

[实现：第 194 行](../src/jhtdb_pipeline/config.py#L194)

```python
def PipelineConfig.bytes_per_snapshot(self) -> int
```

### `PipelineConfig.result_uncompressed_bytes`

[实现：第 199 行](../src/jhtdb_pipeline/config.py#L199)

```python
def PipelineConfig.result_uncompressed_bytes(self) -> int
```

调用：`math.prod`

### `PipelineConfig.shared_gradient_uncompressed_bytes`

[实现：第 205 行](../src/jhtdb_pipeline/config.py#L205)

```python
def PipelineConfig.shared_gradient_uncompressed_bytes(self) -> int
```

调用：`math.prod`

### `PipelineConfig.physical_time`

[实现：第 208 行](../src/jhtdb_pipeline/config.py#L208)

```python
def PipelineConfig.physical_time(self, time_index: int) -> float
```

调用：`ValueError`

显式异常：

```python
ValueError('JHTDB cutout time_index must be >= 1')
```

### `PipelineConfig.with_sigma`

[实现：第 213 行](../src/jhtdb_pipeline/config.py#L213)

```python
def PipelineConfig.with_sigma(self, sigma_grid: float) -> 'PipelineConfig'
```

调用：`ValueError`, `float`, `math.isfinite`, `replace`

显式异常：

```python
ValueError('sigma_grid must be positive')
```

### `PipelineConfig.with_filter`

[实现：第 221 行](../src/jhtdb_pipeline/config.py#L221)

```python
def PipelineConfig.with_filter(self, filter_type: str) -> 'PipelineConfig'
```

调用：`', '.join`, `ValueError`, `replace`, `str`, `str(filter_type).strip`, `str(filter_type).strip().lower`, `str(filter_type).strip().lower().replace`

显式异常：

```python
ValueError(f"filter_type must be one of: {', '.join(FILTER_TYPES)}")
```

### `PipelineConfig.with_sharp_edge_width_fraction`

[实现：第 229 行](../src/jhtdb_pipeline/config.py#L229)

```python
def PipelineConfig.with_sharp_edge_width_fraction(self, fraction: float) -> 'PipelineConfig'
```

调用：`ValueError`, `float`, `math.isfinite`, `replace`

显式异常：

```python
ValueError('sharp edge width fraction must be finite and positive')
```

### `PipelineConfig.validate`

[实现：第 237 行](../src/jhtdb_pipeline/config.py#L237)

```python
def PipelineConfig.validate(self) -> None
```

调用：`', '.join`, `ValueError`, `any`, `len`, `math.isfinite`, `math.prod`, `set`, `sigma_tag`, `zip`

显式异常：

```python
ValueError('JHTDB retry settings are invalid')
ValueError('compression_level must be between 0 and 9')
ValueError('compression_threads must be positive')
ValueError('divergence tolerances must be positive')
ValueError('energy QA tolerances must be positive')
ValueError('fft_cache_mode must be memory or memmap')
ValueError('fft_workers and fft_slab_width must be positive')
ValueError('isotropic1024coarse must use the complete 1024^3 grid')
ValueError('local request blocks must contain at most 100 MiB of velocity data')
ValueError('only isotropic1024coarse is supported')
ValueError('only velocity may be fetched')
ValueError('physics parameters are invalid')
ValueError('request_shape must be an integer multiple of tile_shape')
ValueError('request_shape must divide grid_shape exactly')
ValueError('sharp_edge_width_fraction must be finite and positive')
ValueError('storage safety reserves cannot be negative')
ValueError('the local store requires 128^3 checksum tiles')
ValueError('tile_shape must divide grid_shape exactly')
ValueError(f"filter_type must be one of: {', '.join(FILTER_TYPES)}")
```

### `load_config`

[实现：第 296 行](../src/jhtdb_pipeline/config.py#L296)

```python
def load_config(path: str | Path) -> PipelineConfig
```

调用：`Path`, `PipelineConfig`, `ValueError`, `_mapping`, `_path`, `_reject_unknown`, `_sigma_values`, `_tuple3`, `auth.get`, `bool`, `cfg.validate`, `config_path.open`, `data.get`, `float`, `int`, `isinstance`, `jhtdb.get`, `physics.get`, `platform.get`, `storage.get`, `str`, `str(physics.get('filter_type', 'gaussian')).strip`, `str(physics.get('filter_type', 'gaussian')).strip().lower`, `str(physics.get('filter_type', 'gaussian')).strip().lower().replace`, `validation.get`, `yaml.safe_load`

显式异常：

```python
ValueError('configuration root must be a mapping')
```

## src/jhtdb_pipeline/cq.py

[完整源码](../src/jhtdb_pipeline/cq.py)

依赖：

```python
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import numpy as np
import plotly.graph_objects as go
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from .config import RESULT_SCHEMA_VERSION, PipelineConfig, result_zarr_name
from .store import spatial_slices
from .validation import atomic_json
from .weak_asymmetry import AbsPiPercentileAccumulator, build_weak_asymmetry_report, ensure_weak_asymmetry_result, write_weak_asymmetry_artifacts
```

模块常量/配置：

```python
CQ_REPORT_VERSION = 4
REGIME_CODES = (1, 2, 3, 4, 5, 6)
REGIME_KEYS = ('1+', '1-', '2', '3', '4+', '4-')
LEGACY_REGIME_KEYS = ('Q1', 'Q2', 'Q3', 'Q4')
REGIME_FIELD_SPECS = (('pi', 'mean Π', '#1f77b4'), ('s_bar', 'mean S̄', '#ff7f0e'), ('work_full', 'mean W_full', '#2ca02c'), ('work_resolved', 'mean W_res', '#d62728'), ('delta_w', 'mean ΔW', '#9467bd'))
```

### `_chunk_count`

[实现：第 40 行](../src/jhtdb_pipeline/cq.py#L40)

```python
def _chunk_count(shape: tuple[int, ...], chunks: tuple[int, ...]) -> int
```

调用：`int`, `np.prod`, `zip`

### `compute_cq`

[实现：第 49 行](../src/jhtdb_pipeline/cq.py#L49)

```python
def compute_cq(root: Any, cfg: PipelineConfig, *, scope: str='full_domain') -> dict[str, Any]
```

调用：`(full - resolved).astype`, `AbsPiPercentileAccumulator`, `BarColumn`, `Console`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `_chunk_count`, `abs`, `absolute_values.sum`, `all`, `any`, `bool`, `build_weak_asymmetry_report`, `counts.sum`, `enumerate`, `field.sum`, `field[mask].sum`, `field_partition_checks.values`, `field_sums[field_index].sum`, `float`, `full.astype`, `int`, `len`, `list`, `np.abs`, `np.abs(field).sum`, `np.all`, `np.any`, `np.asarray`, `np.count_nonzero`, `np.dtype`, `np.isfinite`, `np.prod`, `np.square`, `np.square(values64).sum`, `np.zeros`, `progress.add_task`, `progress.advance`, `resolved.astype`, `spatial_slices`, `stored_sums.sum`, `sum`, `tail.add`, `tail.result`, `transport.astype`, `tuple`, `values.astype`, `values64.sum`, `values64[negative].sum`, `values64[positive].sum`, `zip`

显式异常：

```python
RuntimeError('C_q point coverage is incomplete')
RuntimeError('C_q requires float32 pi and work fields')
RuntimeError('C_q requires full-domain pi and work fields with identical shapes')
ValueError('C_q is defined here only for the full periodic domain')
ValueError('pi or work fields contain NaN or Inf')
```

### `write_cq_artifacts`

[实现：第 343 行](../src/jhtdb_pipeline/cq.py#L343)

```python
def write_cq_artifacts(result_dir: Path, report: dict[str, Any]) -> str
```

调用：`atomic_json`, `figure.add_bar`, `figure.update_layout`, `figure.write_html`, `go.Figure`, `list`, `os.replace`, `output.with_suffix`, `str`

### `_report_hash`

[实现：第 390 行](../src/jhtdb_pipeline/cq.py#L390)

```python
def _report_hash(path: Path) -> str
```

调用：`hashlib.sha256`, `hashlib.sha256(path.read_bytes()).hexdigest`, `path.read_bytes`

### `cq_report_is_current`

[实现：第 394 行](../src/jhtdb_pipeline/cq.py#L394)

```python
def cq_report_is_current(result_dir: Path, root: Any) -> bool
```

调用：`(result_dir / 'cq.html').is_file`, `_report_hash`, `complete.get`, `complete_path.is_file`, `complete_path.read_text`, `json.loads`, `manifest.get`, `manifest_path.is_file`, `manifest_path.read_text`, `path.is_file`, `path.read_text`, `report.get`, `root.attrs.get`

### `run_cq`

[实现：第 425 行](../src/jhtdb_pipeline/cq.py#L425)

```python
def run_cq(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> dict[str, Any]
```

调用：`(result_dir / 'COMPLETE').is_file`, `FileLock`, `RuntimeError`, `atomic_json`, `cfg.lock_path.mkdir`, `cfg.result_id`, `cfg.result_path`, `compute_cq`, `float`, `json.loads`, `manifest.update`, `manifest_path.read_text`, `qa_path.read_text`, `result_zarr_name`, `root.attrs.get`, `root.attrs.update`, `str`, `write_cq_artifacts`, `write_weak_asymmetry_artifacts`, `zarr.open_group`

显式异常：

```python
RuntimeError('complete result is missing')
RuntimeError('current full-domain result schema is required')
```

### `ensure_cq_result`

[实现：第 498 行](../src/jhtdb_pipeline/cq.py#L498)

```python
def ensure_cq_result(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> Path
```

调用：`(result_dir / 'COMPLETE').is_file`, `RuntimeError`, `cfg.result_path`, `cq_report_is_current`, `ensure_weak_asymmetry_result`, `float`, `result_zarr_name`, `run_cq`, `str`, `zarr.open_group`

显式异常：

```python
RuntimeError('complete result is missing')
```

## src/jhtdb_pipeline/dashboard.py

[完整源码](../src/jhtdb_pipeline/dashboard.py)

依赖：

```python
from __future__ import annotations
import json
import os
from pathlib import Path
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from jhtdb_pipeline.config import RESULT_SCHEMA_VERSION, load_config
from jhtdb_pipeline.cq import CQ_REPORT_VERSION, REGIME_FIELD_SPECS
from jhtdb_pipeline.regime_pi import DEFAULT_REGIME_PI_OUTPUT_ROOT, regime_pi_output_dir, regime_pi_report_is_current
from jhtdb_pipeline.store import open_complete_result
```

模块常量/配置：

```python
REGIME_LABELS = ('uncertain', '1+', '1-', '2', '3', '4+', '4-')
REGIME_COLORS = [[0.0, '#9e9e9e'], [1 / 7, '#9e9e9e'], [1 / 7, '#1f77b4'], [2 / 7, '#1f77b4'], [2 / 7, '#17becf'], [3 / 7, '#17becf'], [3 / 7, '#ff7f0e'], [4 / 7, '#ff7f0e'], [4 / 7, '#2ca02c'], [5 / 7, '#2ca02c'], [5 / 7, '#d62728'], [6 / 7, '#d62728'], [6 / 7, '#9467bd'], [1.0, '#9467bd']]
GLOBAL_TOTAL_ORDER = ('s_bar', 'pi', 'work_resolved', 'work_full')
GLOBAL_TOTAL_LABELS = ('ΣS̄', 'ΣΠ', 'ΣW_res', 'ΣW_full')
SBAR_METRIC_SPECS = (('identity_relative_residual_rms', '能量等式相对残差 RMS'), ('s_bar_vs_pi_net', '|ΣS̄| / |ΣΠ|'))
CQ_REGIME_ORDER = ('1+', '1-', '2', '3', '4+', '4-')
CQ_REGIME_CRITERIA = {'1+': 'W_full ≥ 0，W_resolved ≥ 0，ΔW ≥ 0', '1-': 'W_full ≥ 0，W_resolved ≥ 0，ΔW < 0', '2': 'W_full ≥ 0，W_resolved < 0', '3': 'W_full < 0，W_resolved ≥ 0', '4+': 'W_full < 0，W_resolved < 0，ΔW ≥ 0', '4-': 'W_full < 0，W_resolved < 0，ΔW < 0'}
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REGIME_PI_OUTPUT_ROOT = PROJECT_ROOT / DEFAULT_REGIME_PI_OUTPUT_ROOT
```

### `complete_result_paths`

[实现：第 52 行](../src/jhtdb_pipeline/dashboard.py#L52)

```python
def complete_result_paths(result_root: Path) -> list[Path]
```

调用：`(path / 'COMPLETE').is_file`, `path.is_dir`, `path.name.endswith`, `path.name.startswith`, `result_root.is_dir`, `result_root.iterdir`, `sorted`

### `extract_slice`

[实现：第 67 行](../src/jhtdb_pipeline/dashboard.py#L67)

```python
def extract_slice(array, component: int, axis: str, index: int) -> np.ndarray
```

调用：`ValueError`, `np.asarray`

显式异常：

```python
ValueError(f'unknown axis {axis}')
```

### `extract_scalar_slice`

[实现：第 77 行](../src/jhtdb_pipeline/dashboard.py#L77)

```python
def extract_scalar_slice(array, axis: str, index: int) -> np.ndarray
```

调用：`ValueError`, `np.asarray`

显式异常：

```python
ValueError(f'unknown axis {axis}')
```

### `extract_gradient_slice`

[实现：第 87 行](../src/jhtdb_pipeline/dashboard.py#L87)

```python
def extract_gradient_slice(array, velocity_component: int, derivative_component: int, axis: str, index: int) -> np.ndarray
```

调用：`ValueError`, `np.asarray`

显式异常：

```python
ValueError(f'unknown axis {axis}')
```

### `spatial_axis_length`

[实现：第 99 行](../src/jhtdb_pipeline/dashboard.py#L99)

```python
def spatial_axis_length(array, axis: str) -> int
```

调用：`int`

### `_global_totals_figure`

[实现：第 103 行](../src/jhtdb_pipeline/dashboard.py#L103)

```python
def _global_totals_figure(report: dict)
```

调用：`go.Bar`, `go.Figure`, `go.Figure(go.Bar(x=list(GLOBAL_TOTAL_LABELS), y=[totals[name] for name in GLOBAL_TOTAL_ORDER], customdata=[totals[name] for name in GLOBAL_TOTAL_ORDER], hovertemplate='%{x}: %{customdata:.8e}<extra></extra>')).update_layout`, `list`

### `_scientific_text`

[实现：第 115 行](../src/jhtdb_pipeline/dashboard.py#L115)

```python
def _scientific_text(value) -> str
```

调用：`float`

### `sbar_metric_rows`

[实现：第 121 行](../src/jhtdb_pipeline/dashboard.py#L121)

```python
def sbar_metric_rows(report: dict) -> list[dict[str, str]]
```

调用：`_scientific_text`, `metric.get`, `metrics.get`, `report.get`, `rows.append`

### `energy_identity_residual`

[实现：第 147 行](../src/jhtdb_pipeline/dashboard.py#L147)

```python
def energy_identity_residual(work_full: np.ndarray, work_resolved: np.ndarray, pi: np.ndarray, s_bar: np.ndarray) -> np.ndarray
```

### `_cq_figure`

[实现：第 156 行](../src/jhtdb_pipeline/dashboard.py#L156)

```python
def _cq_figure(report: dict)
```

调用：`figure.add_bar`, `figure.update_layout`, `go.Figure`, `list`, `tuple`

### `result_selection_metadata`

[实现：第 198 行](../src/jhtdb_pipeline/dashboard.py#L198)

```python
def result_selection_metadata(path: Path) -> dict | None
```

Read only the small manifest needed to populate result selectors.

调用：`float`, `int`, `json.loads`, `manifest.get`, `manifest_path.is_file`, `manifest_path.read_text`, `str`

### `result_selection_catalog`

[实现：第 237 行](../src/jhtdb_pipeline/dashboard.py#L237)

```python
def result_selection_catalog(paths: list[Path]) -> list[dict]
```

调用：`result_selection_metadata`

### `_time_selection_label`

[实现：第 245 行](../src/jhtdb_pipeline/dashboard.py#L245)

```python
def _time_selection_label(time_index: int, catalog: list[dict]) -> str
```

调用：`iter`, `len`, `next`

### `cq_rows`

[实现：第 256 行](../src/jhtdb_pipeline/dashboard.py#L256)

```python
def cq_rows(report: dict, field_name: str='pi') -> list[dict[str, str]]
```

调用：`ValueError`, `_scientific_text`, `int`, `rows.append`, `tuple`

显式异常：

```python
ValueError(f'unknown regime field {field_name!r}')
```

### `_weak_asymmetry_figure`

[实现：第 278 行](../src/jhtdb_pipeline/dashboard.py#L278)

```python
def _weak_asymmetry_figure(report: dict)
```

调用：`go.Bar`, `go.Figure`, `go.Figure(go.Bar(x=['positive/backscatter', 'negative/forward', 'net'], y=[report['positive_backscatter']['sum'], report['negative_forward']['sum'], report['global']['pi_sum']])).update_layout`

### `weak_asymmetry_rows`

[实现：第 294 行](../src/jhtdb_pipeline/dashboard.py#L294)

```python
def weak_asymmetry_rows(report: dict) -> list[dict[str, str]]
```

调用：`_scientific_text`

### `_symmetric_color_limit`

[实现：第 320 行](../src/jhtdb_pipeline/dashboard.py#L320)

```python
def _symmetric_color_limit(values: np.ndarray, percentile: float=100.0) -> float
```

调用：`ValueError`, `float`, `np.abs`, `np.isfinite`, `np.max`, `np.percentile`

显式异常：

```python
ValueError('percentile must be in (0, 100]')
```

### `_symlog_transform`

[实现：第 332 行](../src/jhtdb_pipeline/dashboard.py#L332)

```python
def _symlog_transform(values: np.ndarray, linear_threshold: float) -> np.ndarray
```

调用：`ValueError`, `np.abs`, `np.asarray`, `np.log1p`, `np.sign`

显式异常：

```python
ValueError('linear_threshold must be positive')
```

### `_continuous_figure`

[实现：第 339 行](../src/jhtdb_pipeline/dashboard.py#L339)

```python
def _continuous_figure(values: np.ndarray, title: str, *, signed: bool=True, color_percentile: float=100.0, scale_mode: str='linear', color_limit: float | None=None)
```

调用：`ValueError`, `_symlog_transform`, `_symmetric_color_limit`, `figure.update_coloraxes`, `figure.update_layout`, `figure.update_traces`, `figure.update_xaxes`, `figure.update_yaxes`, `float`, `int`, `max`, `np.arange`, `np.asarray`, `np.ceil`, `np.isfinite`, `px.imshow`, `transformed_ticks.tolist`

显式异常：

```python
ValueError("scale_mode must be 'linear' or 'symlog'")
ValueError('color_limit must be finite and positive')
ValueError('symlog color scaling requires signed=True')
```

### `_regime_figure`

[实现：第 414 行](../src/jhtdb_pipeline/dashboard.py#L414)

```python
def _regime_figure(values: np.ndarray, title: str)
```

调用：`figure.update_layout`, `figure.update_yaxes`, `go.Figure`, `go.Heatmap`, `list`, `np.asarray`, `range`

### `regime_pi_rows`

[实现：第 431 行](../src/jhtdb_pipeline/dashboard.py#L431)

```python
def regime_pi_rows(report: dict) -> list[dict[str, str]]
```

调用：`_scientific_text`, `int`, `report.get`, `rows.append`

### `_regime_pi_figure`

[实现：第 451 行](../src/jhtdb_pipeline/dashboard.py#L451)

```python
def _regime_pi_figure(report: dict)
```

调用：`enumerate`, `figure.add_bar`, `figure.update_layout`, `figure.update_xaxes`, `figure.update_yaxes`, `list`, `make_subplots`, `np.asarray`, `report.get`

### `main`

[实现：第 509 行](../src/jhtdb_pipeline/dashboard.py#L509)

```python
def main() -> None
```

调用：`_continuous_figure`, `_cq_figure`, `_global_totals_figure`, `_regime_figure`, `_regime_pi_figure`, `_scientific_text`, `_symmetric_color_limit`, `_time_selection_label`, `_weak_asymmetry_figure`, `column.caption`, `column.metric`, `complete_result_paths`, `cq_path.is_file`, `cq_path.read_text`, `cq_rows`, `dict`, `energy_identity_residual`, `extract_gradient_slice`, `extract_scalar_slice`, `extract_slice`, `float`, `global_values.get`, `json.loads`, `left.metric`, `left.plotly_chart`, `len`, `load_config`, `max_column.metric`, `metric.get`, `middle.metric`, `np.stack`, `open_complete_result`, `os.environ.get`, `p99_column.metric`, `path.is_file`, `path.read_text`, `regime_pi_output_dir`, `regime_pi_path.is_file`, `regime_pi_path.read_text`, `regime_pi_report.get`, `regime_pi_report_is_current`, `regime_pi_rows`, `report.get`, `report.get('metrics', {}).get`, `report_path.is_file`, `report_path.read_text`, `result.attrs.get`, `result_selection_catalog`, `right.metric`, `right.plotly_chart`, `s_bar_qa.is_file`, `s_bar_qa.read_text`, `sbar_metric_rows`, `selected.resolve`, `sorted`, `spatial_axis_length`, `st.caption`, `st.code`, `st.columns`, `st.dataframe`, `st.divider`, `st.error`, `st.expander`, `st.header`, `st.info`, `st.json`, `st.plotly_chart`, `st.session_state.get`, `st.session_state.pop`, `st.set_page_config`, `st.sidebar.button`, `st.sidebar.radio`, `st.sidebar.selectbox`, `st.sidebar.slider`, `st.spinner`, `st.subheader`, `st.success`, `st.title`, `st.warning`, `str`, `weak_asymmetry_rows`, `zip`

## src/jhtdb_pipeline/disk_fft.py

[完整源码](../src/jhtdb_pipeline/disk_fft.py)

依赖：

```python
from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
from scipy import fft
from .physics import axis_batches, smooth_sharp_radial_weights, release_pages
```

### `mapped_array`

[实现：第 13 行](../src/jhtdb_pipeline/disk_fft.py#L13)

```python
def mapped_array(path: Path, shape: tuple[int, ...], dtype: str) -> np.memmap
```

调用：`np.memmap`, `path.parent.mkdir`

### `build_spectrum`

[实现：第 18 行](../src/jhtdb_pipeline/disk_fft.py#L18)

```python
def build_spectrum(source: Any, path: Path, slab: int, *, workers: int, full: bool) -> np.memmap
```

调用：`axis_batches`, `fft.fft`, `fft.rfft`, `mapped_array`, `np.array`, `np.asarray`, `release_pages`, `spectrum._mmap.close`, `tuple`

### `filter_spectrum`

[实现：第 40 行](../src/jhtdb_pipeline/disk_fft.py#L40)

```python
def filter_spectrum(spectrum: Any, destination: Any, scratch_path: Path, sigma: float, domain_length: float, alpha: float, slab: int, *, workers: int) -> None
```

Apply the radial filter, then invert each axis in full-length FFT slabs.

调用：`ValueError`, `axis_batches`, `fft.fftfreq`, `fft.ifft`, `fft.irfft`, `fft.rfftfreq`, `filtered._mmap.close`, `len`, `mapped_array`, `np.array`, `np.sqrt`, `release_pages`, `scratch_path.unlink`, `set`, `smooth_sharp_radial_weights`, `tuple`

显式异常：

```python
ValueError('invalid spectral filter parameters')
ValueError('smooth-sharp requires a full cubic field and matching spectrum')
```

## src/jhtdb_pipeline/doctor.py

[完整源码](../src/jhtdb_pipeline/doctor.py)

依赖：

```python
from __future__ import annotations
import importlib.metadata
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .auth import token_source
from .config import PipelineConfig
from .validation import atomic_json
```

### `_utcnow`

[实现：第 16 行](../src/jhtdb_pipeline/doctor.py#L16)

```python
def _utcnow() -> datetime
```

调用：`datetime.now`

### `ensure_run_record`

[实现：第 20 行](../src/jhtdb_pipeline/doctor.py#L20)

```python
def ensure_run_record(cfg: PipelineConfig, time_index: int) -> dict[str, Any]
```

Create a durable local run record; local caches do not expire.

调用：`_utcnow`, `_utcnow().isoformat`, `atomic_json`, `cfg.run_path`, `json.loads`, `path.exists`, `path.read_text`

### `_space`

[实现：第 35 行](../src/jhtdb_pipeline/doctor.py#L35)

```python
def _space(path: Path) -> dict[str, float]
```

调用：`path.mkdir`, `shutil.disk_usage`

### `_writable`

[实现：第 45 行](../src/jhtdb_pipeline/doctor.py#L45)

```python
def _writable(path: Path) -> bool
```

调用：`handle.fileno`, `handle.flush`, `handle.write`, `os.fsync`, `os.getpid`, `path.mkdir`, `probe.open`, `probe.read_text`, `probe.unlink`

### `_version`

[实现：第 63 行](../src/jhtdb_pipeline/doctor.py#L63)

```python
def _version(distribution: str) -> str | None
```

调用：`importlib.metadata.version`

### `_givernylocal_runtime_check`

[实现：第 70 行](../src/jhtdb_pipeline/doctor.py#L70)

```python
def _givernylocal_runtime_check() -> tuple[bool, str | None]
```

调用：`str`

### `doctor`

[实现：第 79 行](../src/jhtdb_pipeline/doctor.py#L79)

```python
def doctor(cfg: PipelineConfig, time_index: int | None=None) -> dict[str, Any]
```

调用：`_givernylocal_runtime_check`, `_space`, `_version`, `_writable`, `all`, `cfg.run_path`, `checks.values`, `json.loads`, `record_path.exists`, `record_path.read_text`, `str`, `token_source`

## src/jhtdb_pipeline/input_fields.py

[完整源码](../src/jhtdb_pipeline/input_fields.py)

依赖：

```python
import zarr
```

### `PressureGradientConfig`

[实现：第 5 行](../src/jhtdb_pipeline/input_fields.py#L5)

```python
class PressureGradientConfig()
```

字段/默认值：

```python
variable = 'pressure_gradient'
components = ['dPdx', 'dPdy', 'dPdz']
acquisition_metadata = {'source': 'JHTDB getData', 'source_variable': 'pressure', 'spatial_operator': 'gradient', 'spatial_method': 'fd4noint', 'temporal_method': 'none', 'pressure_definition': 'JHTDB kinematic pressure P=p/rho'}
```

### `PressureGradientConfig.__init__`

[实现：第 14 行](../src/jhtdb_pipeline/input_fields.py#L14)

```python
def PressureGradientConfig.__init__(self, base)
```

调用：`ValueError`, `any`, `min`, `tuple`, `zip`

显式异常：

```python
ValueError('pressure-gradient grid must be divisible by tile dimensions')
```

### `PressureGradientConfig.__getattr__`

[实现：第 23 行](../src/jhtdb_pipeline/input_fields.py#L23)

```python
def PressureGradientConfig.__getattr__(self, name)
```

调用：`getattr`

### `PressureGradientConfig.catalog_path`

[实现：第 27 行](../src/jhtdb_pipeline/input_fields.py#L27)

```python
def PressureGradientConfig.catalog_path(self)
```

### `PressureGradientConfig.manifest_path`

[实现：第 31 行](../src/jhtdb_pipeline/input_fields.py#L31)

```python
def PressureGradientConfig.manifest_path(self)
```

### `PressureGradientConfig.qa_path`

[实现：第 35 行](../src/jhtdb_pipeline/input_fields.py#L35)

```python
def PressureGradientConfig.qa_path(self)
```

### `PressureGradientConfig.raw_store_path`

[实现：第 38 行](../src/jhtdb_pipeline/input_fields.py#L38)

```python
def PressureGradientConfig.raw_store_path(self, time_index)
```

调用：`self.base.persistent_input_path`

### `field_config`

[实现：第 42 行](../src/jhtdb_pipeline/input_fields.py#L42)

```python
def field_config(cfg, field)
```

调用：`PressureGradientConfig`, `ValueError`

显式异常：

```python
ValueError(f'unsupported input field: {field}')
```

### `open_frame_fields`

[实现：第 50 行](../src/jhtdb_pipeline/input_fields.py#L50)

```python
def open_frame_fields(cfg, time_index)
```

Open aligned validated full-domain fields lazily, without loading arrays.

调用：`ValueError`, `any`, `cfg.physical_time`, `expected.items`, `field_config`, `list`, `root.attrs.get`, `str`, `view.raw_store_path`, `zarr.open_group`

显式异常：

```python
ValueError(f'{name}: unexpected shape {array.shape}')
ValueError(f'{name}: unvalidated or mismatched frame metadata')
```

## src/jhtdb_pipeline/jhtdb.py

[完整源码](../src/jhtdb_pipeline/jhtdb.py)

依赖：

```python
from __future__ import annotations
import json
import shutil
import time
from pathlib import Path
import numpy as np
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn
from .auth import get_token
from .catalog import Catalog
from .config import PipelineConfig
from .doctor import ensure_run_record
from .planning import Tile, requests_for, tiles_for, tiles_in_request
from .store import VelocityStore, array_sha256
```

### `LocalJHTDB`

[实现：第 28 行](../src/jhtdb_pipeline/jhtdb.py#L28)

```python
class LocalJHTDB()
```

Strictly serial wrapper around the official local Giverny client.

### `LocalJHTDB.__init__`

[实现：第 31 行](../src/jhtdb_pipeline/jhtdb.py#L31)

```python
def LocalJHTDB.__init__(self, cfg: PipelineConfig, token: str, time_index: int)
```

调用：`RuntimeError`, `cfg.run_path`, `int`, `output.mkdir`, `str`, `turb_dataset`

显式异常：

```python
RuntimeError(f'The local Giverny runtime cannot be imported; install this project with givernylocal>=3.6.2. Underlying import error: {exc}')
```

### `LocalJHTDB.fetch_tile`

[实现：第 50 行](../src/jhtdb_pipeline/jhtdb.py#L50)

```python
def LocalJHTDB.fetch_tile(self, tile: Tile, time_index: int) -> np.ndarray
```

调用：`RuntimeError`, `callable`, `canonicalize_cutout`, `close`, `getattr`, `len`, `list`, `np.asarray`, `np.ones`, `self._get_cutout`, `self.fetch_pressure_gradient`

显式异常：

```python
RuntimeError(f'expected one velocity variable, got {names}')
```

### `LocalJHTDB.fetch_pressure_gradient`

[实现：第 75 行](../src/jhtdb_pipeline/jhtdb.py#L75)

```python
def LocalJHTDB.fetch_pressure_gradient(self, tile: Tile, time_index: int) -> np.ndarray
```

Query server derivatives at the exact velocity grid locations.

调用：`RuntimeError`, `ValueError`, `canonicalize_cutout`, `len`, `np.arange`, `np.asarray`, `np.column_stack`, `np.isfinite`, `np.isfinite(values).all`, `np.unravel_index`, `self._get_data`, `self.cfg.physical_time`, `values.reshape`

显式异常：

```python
RuntimeError('expected exactly one pressure-gradient time frame')
RuntimeError('invalid pressure-gradient response shape or non-finite values')
ValueError(f'pressure request has {count} points; server limit is {self._max_data_points}')
```

### `canonicalize_cutout`

[实现：第 95 行](../src/jhtdb_pipeline/jhtdb.py#L95)

```python
def canonicalize_cutout(values: np.ndarray, tile: Tile) -> np.ndarray
```

Convert Giverny ``(z,y,x,component)`` to ``(component,z,y,x)``.

调用：`RuntimeError`, `np.all`, `np.ascontiguousarray`, `np.isfinite`, `np.moveaxis`

显式异常：

```python
RuntimeError('GetCutout returned NaN or Inf')
RuntimeError(f'GetCutout shape {values.shape}, expected {expected}')
```

### `chunk_from_request`

[实现：第 106 行](../src/jhtdb_pipeline/jhtdb.py#L106)

```python
def chunk_from_request(values: np.ndarray, request: Tile, tile: Tile) -> np.ndarray
```

Copy one canonical checksum tile from a larger canonical request block.

调用：`ValueError`, `np.ascontiguousarray`, `slice`

显式异常：

```python
ValueError(f'request array shape {values.shape}, expected {expected_request}')
ValueError(f'tile {tile.key} is not contained in request {request.key}')
```

### `scratch_space`

[实现：第 128 行](../src/jhtdb_pipeline/jhtdb.py#L128)

```python
def scratch_space(cfg: PipelineConfig, time_index: int) -> dict[str, float]
```

调用：`RuntimeError`, `cfg.raw_store_path`, `int`, `path.mkdir`, `shutil.disk_usage`

显式异常：

```python
RuntimeError(f'insufficient scratch space: {usage.free / 1024 ** 3:.2f} GiB free, need {required / 1024 ** 3:.2f} GiB before fetching frame {time_index}')
```

### `smoke`

[实现：第 146 行](../src/jhtdb_pipeline/jhtdb.py#L146)

```python
def smoke(cfg: PipelineConfig, time_index: int) -> dict[str, object]
```

调用：`FileLock`, `LocalJHTDB`, `LocalJHTDB(cfg, token, time_index).fetch_tile`, `Tile`, `bool`, `cfg.lock_path.mkdir`, `cfg.physical_time`, `float`, `get_token`, `list`, `np.all`, `np.isfinite`, `str`, `values.max`, `values.min`

### `fetch_snapshot`

[实现：第 167 行](../src/jhtdb_pipeline/jhtdb.py#L167)

```python
def fetch_snapshot(cfg: PipelineConfig, time_index: int) -> Path
```

调用：`BarColumn`, `Catalog`, `Console`, `FileLock`, `LocalJHTDB`, `MofNCompleteColumn`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeRemainingColumn`, `VelocityStore`, `array_sha256`, `catalog.mark_attempt`, `catalog.mark_verified`, `catalog.plan_snapshot`, `catalog.set_snapshot_status`, `catalog.tile`, `cfg.lock_path.mkdir`, `cfg.physical_time`, `cfg.raw_store_path`, `cfg.run_path`, `cfg.run_path(time_index).mkdir`, `cfg.state_root.mkdir`, `chunk_from_request`, `client.fetch_tile`, `console.print`, `ensure_run_record`, `enumerate`, `get_token`, `json.dumps`, `len`, `np.ascontiguousarray`, `pending.append`, `pressure_tiles.setdefault`, `pressure_tiles.setdefault(origin, []).append`, `progress.add_task`, `progress.update`, `range`, `requests_for`, `scratch_space`, `store.ensure_array`, `store.write_tile`, `str`, `str(exc).replace`, `str(last_error).replace`, `tiles_for`, `tiles_in_request`, `time.sleep`, `validate_snapshot`

显式异常：

```python
RuntimeError(str(last_error).replace(token, '<redacted>'))
```

## src/jhtdb_pipeline/physics.py

[完整源码](../src/jhtdb_pipeline/physics.py)

依赖：

```python
from __future__ import annotations
import mmap
from pathlib import Path
from typing import Any, Iterator
import numpy as np
from scipy import fft
from scipy.special import erfc
```

模块常量/配置：

```python
ARRAY_AXIS_FOR_DERIVATIVE = (2, 1, 0)
REGIME_LABELS = ('uncertain', '1+', '1-', '2', '3', '4+', '4-')
```

### `spectral_derivative`

[实现：第 16 行](../src/jhtdb_pipeline/physics.py#L16)

```python
def spectral_derivative(values: np.ndarray, axis: int, domain_length: float) -> np.ndarray
```

调用：`(1j * wave_number).reshape`, `fft.irfft`, `fft.irfft(spectrum, n=n, axis=axis, workers=1).astype`, `fft.rfft`, `fft.rfftfreq`, `len`, `np.asarray`

### `spectral_gaussian`

[实现：第 27 行](../src/jhtdb_pipeline/physics.py#L27)

```python
def spectral_gaussian(values: np.ndarray, sigma_grid: float, *, workers: int=1) -> np.ndarray
```

调用：`ValueError`, `fft.irfft`, `fft.irfft(spectrum, n=n, axis=axis, workers=workers).astype`, `fft.rfft`, `fft.rfftfreq`, `len`, `np.asarray`, `np.exp`, `np.exp(-0.5 * np.square(sigma_grid * theta)).astype`, `np.square`, `range`, `transfer.reshape`

显式异常：

```python
ValueError('sigma_grid must be positive')
ValueError('workers must be positive')
```

### `regime_codes`

[实现：第 47 行](../src/jhtdb_pipeline/physics.py#L47)

```python
def regime_codes(work_full: np.ndarray, work_resolved: np.ndarray, epsilon_abs: float, epsilon_rel: float) -> tuple[np.ndarray, float, float]
```

调用：`float`, `max`, `np.mean`, `np.sqrt`, `np.square`, `regime_codes_from_thresholds`

### `regime_codes_from_thresholds`

[实现：第 65 行](../src/jhtdb_pipeline/physics.py#L65)

```python
def regime_codes_from_thresholds(work_full: np.ndarray, work_resolved: np.ndarray, epsilon_full: float, epsilon_resolved: float) -> np.ndarray
```

Return v6 codes: uncertain, 1+, 1-, 2, 3, 4+, 4-.

调用：`ValueError`, `np.asarray`, `np.zeros`

显式异常：

```python
ValueError('work fields must have identical shapes')
```

### `ComponentView`

[实现：第 92 行](../src/jhtdb_pipeline/physics.py#L92)

```python
class ComponentView()
```

### `ComponentView.__init__`

[实现：第 93 行](../src/jhtdb_pipeline/physics.py#L93)

```python
def ComponentView.__init__(self, parent: Any, component: int)
```

调用：`tuple`

### `ComponentView.__getitem__`

[实现：第 98 行](../src/jhtdb_pipeline/physics.py#L98)

```python
def ComponentView.__getitem__(self, key: Any) -> np.ndarray
```

调用：`isinstance`

### `ComponentView.__setitem__`

[实现：第 103 行](../src/jhtdb_pipeline/physics.py#L103)

```python
def ComponentView.__setitem__(self, key: Any, value: np.ndarray) -> None
```

调用：`isinstance`

### `ProductView`

[实现：第 109 行](../src/jhtdb_pipeline/physics.py#L109)

```python
class ProductView()
```

Read-only slab view of the pointwise product of two full-domain fields.

### `ProductView.__init__`

[实现：第 112 行](../src/jhtdb_pipeline/physics.py#L112)

```python
def ProductView.__init__(self, left: Any, right: Any)
```

调用：`ValueError`, `tuple`

显式异常：

```python
ValueError('product fields must have identical shapes')
```

### `ProductView.__getitem__`

[实现：第 119 行](../src/jhtdb_pipeline/physics.py#L119)

```python
def ProductView.__getitem__(self, key: Any) -> np.ndarray
```

调用：`np.asarray`

### `axis_batches`

[实现：第 125 行](../src/jhtdb_pipeline/physics.py#L125)

```python
def axis_batches(shape: tuple[int, int, int], axis: int, slab: int) -> Iterator[tuple[slice, slice, slice]]
```

调用：`ValueError`, `min`, `range`, `slice`

显式异常：

```python
ValueError(f'invalid 3-D axis {axis}')
```

### `transform_axis`

[实现：第 138 行](../src/jhtdb_pipeline/physics.py#L138)

```python
def transform_axis(source: Any, destination: Any, axis: int, slab: int, *, workers: int=1, derivative_domain_length: float | None=None, gaussian_sigma_grid: float | None=None) -> None
```

调用：`ValueError`, `axis_batches`, `fft.irfft`, `fft.irfft(spectrum, n=n, axis=axis, workers=workers).astype`, `fft.rfft`, `fft.rfftfreq`, `float`, `len`, `multiplier.reshape`, `np.asarray`, `np.exp`, `np.exp(-0.5 * np.square(sigma * theta)).astype`, `np.square`, `release_pages`, `tuple`

显式异常：

```python
ValueError('gaussian_sigma_grid must be positive')
ValueError('select exactly one spectral operation')
```

### `axis2_spectrum`

[实现：第 176 行](../src/jhtdb_pipeline/physics.py#L176)

```python
def axis2_spectrum(source: Any, slab: int, *, workers: int=1) -> np.ndarray
```

Cache the first (x/array-axis-2) real FFT used by separable filtering.

调用：`ValueError`, `axis_batches`, `fft.rfft`, `int`, `len`, `np.asarray`, `np.empty`, `tuple`

显式异常：

```python
ValueError('axis2_spectrum requires a three-dimensional field')
```

### `full_spectrum`

[实现：第 195 行](../src/jhtdb_pipeline/physics.py#L195)

```python
def full_spectrum(source: Any, slab: int, *, workers: int=1) -> np.ndarray
```

Return the complete 3-D rFFT spectrum without spatial subsampling.

调用：`axis2_spectrum`, `fft.fft`, `np.asarray`

### `smooth_sharp_radial_weights`

[实现：第 208 行](../src/jhtdb_pipeline/physics.py#L208)

```python
def smooth_sharp_radial_weights(radial_wavenumber: np.ndarray, cutoff_wavenumber: float, edge_width_wavenumber: float) -> np.ndarray
```

Gaussian-smoothed Heaviside edge centered on the sharp cutoff.

调用：`ValueError`, `erfc`, `float`, `np.all`, `np.any`, `np.asarray`, `np.isfinite`, `np.sqrt`

显式异常：

```python
ValueError('cutoff_wavenumber must be finite and positive')
ValueError('edge_width_wavenumber must be finite and positive')
ValueError('radial_wavenumber must be finite and nonnegative')
```

### `filter_smooth_sharp_from_spectrum`

[实现：第 229 行](../src/jhtdb_pipeline/physics.py#L229)

```python
def filter_smooth_sharp_from_spectrum(spectrum: np.ndarray, destination: Any, sigma_grid: float, domain_length: float, edge_width_fraction: float, slab: int, *, workers: int=1) -> None
```

Apply an isotropic smooth sharp cutoff to a complete periodic spectrum.

调用：`ValueError`, `fft.fftfreq`, `fft.irfftn`, `fft.irfftn(filtered, s=shape, workers=workers, overwrite_x=True).astype`, `fft.rfftfreq`, `int`, `len`, `min`, `np.array`, `np.dtype`, `np.sqrt`, `np.square`, `range`, `set`, `smooth_sharp_radial_weights`, `tuple`

显式异常：

```python
ValueError('filter scale, domain length, and edge width must be positive')
ValueError('full spectrum has an unexpected schema')
ValueError('smooth sharp filtering currently requires a cubic grid')
```

### `filter_smooth_sharp_field`

[实现：第 278 行](../src/jhtdb_pipeline/physics.py#L278)

```python
def filter_smooth_sharp_field(source: Any, destination: Any, sigma_grid: float, domain_length: float, edge_width_fraction: float, slab: int, *, workers: int=1) -> None
```

Compute and filter a complete periodic 3-D field without downsampling.

调用：`filter_smooth_sharp_from_spectrum`, `full_spectrum`

### `filter_field_from_axis2_spectrum`

[实现：第 301 行](../src/jhtdb_pipeline/physics.py#L301)

```python
def filter_field_from_axis2_spectrum(spectrum: np.ndarray, destination: Any, temp_a: Any, temp_b: Any, sigma_grid: float, slab: int, *, workers: int=1) -> None
```

Continue the existing separable filter from a shared first-axis FFT.

调用：`ValueError`, `axis_batches`, `fft.irfft`, `fft.irfft(filtered_spectrum, n=shape[2], axis=2, workers=workers).astype`, `fft.rfftfreq`, `int`, `np.asarray`, `np.dtype`, `np.exp`, `np.exp(-0.5 * np.square(sigma_grid * theta)).astype`, `np.square`, `transfer.reshape`, `transform_axis`, `tuple`

显式异常：

```python
ValueError('cached first-axis spectrum has an unexpected schema')
ValueError('sigma_grid must be positive')
```

### `derivative_field`

[实现：第 341 行](../src/jhtdb_pipeline/physics.py#L341)

```python
def derivative_field(source: Any, destination: Any, derivative_component: int, domain_length: float, slab: int, workers: int=1) -> None
```

调用：`transform_axis`

### `filter_field`

[实现：第 359 行](../src/jhtdb_pipeline/physics.py#L359)

```python
def filter_field(source: Any, destination: Any, temp_a: Any, temp_b: Any, sigma_grid: float, slab: int, workers: int=1) -> None
```

调用：`transform_axis`

### `zero_field`

[实现：第 379 行](../src/jhtdb_pipeline/physics.py#L379)

```python
def zero_field(field: Any, slab: int) -> None
```

调用：`min`, `range`, `release_pages`

### `accumulate_product`

[实现：第 386 行](../src/jhtdb_pipeline/physics.py#L386)

```python
def accumulate_product(destination: Any, left: Any, right: Any, slab: int) -> None
```

调用：`min`, `np.asarray`, `range`, `release_pages`, `slice`

### `subtract_product`

[实现：第 405 行](../src/jhtdb_pipeline/physics.py#L405)

```python
def subtract_product(destination: Any, left: Any, right: Any, slab: int) -> None
```

调用：`min`, `np.asarray`, `range`, `release_pages`, `slice`

### `memmap`

[实现：第 424 行](../src/jhtdb_pipeline/physics.py#L424)

```python
def memmap(path: Path, shape: tuple[int, ...], mode: str='w+') -> np.memmap
```

调用：`np.memmap`, `path.parent.mkdir`

### `close_memmap`

[实现：第 429 行](../src/jhtdb_pipeline/physics.py#L429)

```python
def close_memmap(mapped: np.memmap) -> None
```

调用：`getattr`, `mapped.flush`, `memory_map.close`

### `release_pages`

[实现：第 436 行](../src/jhtdb_pipeline/physics.py#L436)

```python
def release_pages(array: Any) -> None
```

Release mapped working sets after a streaming pass; never discard dirty data.

调用：`array.flush`, `hasattr`, `isinstance`, `mapping.madvise`

## src/jhtdb_pipeline/planning.py

[完整源码](../src/jhtdb_pipeline/planning.py)

依赖：

```python
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from .config import PipelineConfig
```

### `Tile`

[实现：第 10 行](../src/jhtdb_pipeline/planning.py#L10)

```python
class Tile()
```

字段/默认值：

```python
x0: int
y0: int
z0: int
nx: int
ny: int
nz: int
```

### `Tile.key`

[实现：第 19 行](../src/jhtdb_pipeline/planning.py#L19)

```python
def Tile.key(self) -> str
```

### `Tile.api_ranges`

[实现：第 23 行](../src/jhtdb_pipeline/planning.py#L23)

```python
def Tile.api_ranges(self) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]
```

### `Tile.store_slices`

[实现：第 31 行](../src/jhtdb_pipeline/planning.py#L31)

```python
def Tile.store_slices(self) -> tuple[slice, slice, slice, slice]
```

调用：`slice`

### `_blocks_for`

[实现：第 40 行](../src/jhtdb_pipeline/planning.py#L40)

```python
def _blocks_for(grid_shape: tuple[int, int, int], block_shape: tuple[int, int, int]) -> list[Tile]
```

调用：`Tile`, `min`, `product`, `range`

### `tiles_for`

[实现：第 53 行](../src/jhtdb_pipeline/planning.py#L53)

```python
def tiles_for(cfg: PipelineConfig) -> list[Tile]
```

Return the 128^3 storage/checksum tiles.

调用：`_blocks_for`

### `requests_for`

[实现：第 58 行](../src/jhtdb_pipeline/planning.py#L58)

```python
def requests_for(cfg: PipelineConfig) -> list[Tile]
```

Return the configured strictly serial local GetCutout requests.

调用：`_blocks_for`

### `tiles_in_request`

[实现：第 63 行](../src/jhtdb_pipeline/planning.py#L63)

```python
def tiles_in_request(request: Tile, tiles: list[Tile]) -> list[Tile]
```

### `coordinate_for_index`

[实现：第 76 行](../src/jhtdb_pipeline/planning.py#L76)

```python
def coordinate_for_index(index: int, point_count: int, domain_length: float) -> float
```

调用：`IndexError`

显式异常：

```python
IndexError(f'grid index {index} is outside [0,{point_count})')
```

### `plan`

[实现：第 82 行](../src/jhtdb_pipeline/planning.py#L82)

```python
def plan(cfg: PipelineConfig, time_index: int) -> dict[str, object]
```

调用：`ValueError`, `cfg.physical_time`, `cfg.result_path`, `cfg.run_path`, `len`, `list`, `requests_for`, `round`, `str`, `tiles_for`

显式异常：

```python
ValueError('time_index must be >= 1')
```

## src/jhtdb_pipeline/pressure_local.py

[完整源码](../src/jhtdb_pipeline/pressure_local.py)

依赖：

```python
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import time
import numpy as np
import zarr
from filelock import FileLock
from .auth import get_token
from .config import load_config
from .jhtdb import LocalJHTDB
from .planning import requests_for
from .store import array_sha256, compressor, spatial_slices
from .validation import atomic_json
```

### `PressureConfig`

[实现：第 22 行](../src/jhtdb_pipeline/pressure_local.py#L22)

```python
class PressureConfig()
```

字段/默认值：

```python
variable = 'pressure'
```

### `PressureConfig.__init__`

[实现：第 25 行](../src/jhtdb_pipeline/pressure_local.py#L25)

```python
def PressureConfig.__init__(self, base)
```

### `PressureConfig.__getattr__`

[实现：第 28 行](../src/jhtdb_pipeline/pressure_local.py#L28)

```python
def PressureConfig.__getattr__(self, key)
```

调用：`getattr`

### `PressureClient`

[实现：第 32 行](../src/jhtdb_pipeline/pressure_local.py#L32)

```python
class PressureClient(LocalJHTDB)
```

### `PressureClient.fetch_tile`

[实现：第 33 行](../src/jhtdb_pipeline/pressure_local.py#L33)

```python
def PressureClient.fetch_tile(self, tile, time_index)
```

调用：`ValueError`, `len`, `list`, `np.asarray`, `np.ascontiguousarray`, `np.ones`, `result.close`, `self._get_cutout`

显式异常：

```python
ValueError('Expected one scalar pressure field')
ValueError(f'Unexpected pressure shape: {values.shape}')
```

### `identity`

[实现：第 49 行](../src/jhtdb_pipeline/pressure_local.py#L49)

```python
def identity(cfg, frame)
```

调用：`cfg.physical_time`, `dict`, `list`

### `manifest`

[实现：第 54 行](../src/jhtdb_pipeline/pressure_local.py#L54)

```python
def manifest(path, expected)
```

调用：`ValueError`, `json.loads`, `path.exists`, `path.read_text`

显式异常：

```python
ValueError(f'Cache provenance mismatch: {path}')
```

### `download_pressure`

[实现：第 63 行](../src/jhtdb_pipeline/pressure_local.py#L63)

```python
def download_pressure(cfg, frame, client_factory=PressureClient)
```

调用：`IOError`, `PressureConfig`, `RuntimeError`, `ValueError`, `any`, `array_sha256`, `atomic_json`, `cfg.persistent_input_path`, `client.fetch_tile`, `client_factory`, `compressor`, `enumerate`, `expected.items`, `folder.mkdir`, `get_token`, `identity`, `len`, `list`, `manifest`, `np.asarray`, `np.isfinite`, `np.isfinite(values).all`, `np.prod`, `print`, `range`, `requests_for`, `reversed`, `root.attrs.get`, `root.attrs.update`, `root.require_dataset`, `shutil.disk_usage`, `state['checksums'].get`, `str`, `str(exc).replace`, `time.sleep`, `tuple`, `zarr.open_group`

显式异常：

```python
IOError('Pressure write/read checksum mismatch')
RuntimeError('Insufficient disk space for scalar pressure and safety reserve')
RuntimeError('Pressure download failed; verified blocks retained')
ValueError('Invalid pressure response')
ValueError('Pressure store metadata mismatch')
```

### `fd4_block`

[实现：第 118 行](../src/jhtdb_pipeline/pressure_local.py#L118)

```python
def fd4_block(pressure, slices, lengths_xyz)
```

Two-cell halo wraps the FULL periodic grid, including across chunk seams.

调用：`enumerate`, `hasattr`, `np.arange`, `np.asarray`, `np.empty`, `np.ix_`, `np.zeros`, `slice`, `tuple`, `zip`

### `required_pressure_blocks`

[实现：第 135 行](../src/jhtdb_pipeline/pressure_local.py#L135)

```python
def required_pressure_blocks(cfg, slices)
```

All published request blocks intersecting this block's periodic halo.

调用：`(indices // width * width).tolist`, `np.arange`, `origins.append`, `product`, `reversed`, `set`, `sorted`, `zip`

### `compute_gradient`

[实现：第 145 行](../src/jhtdb_pipeline/pressure_local.py#L145)

```python
def compute_gradient(cfg, frame, block_size=64, *, follow=False, stop_event=None)
```

调用：`FileLock`, `_compute_gradient`, `cfg.lock_path.mkdir`, `str`

### `_compute_gradient`

[实现：第 151 行](../src/jhtdb_pipeline/pressure_local.py#L151)

```python
def _compute_gradient(cfg, frame, block_size, *, follow, stop_event)
```

调用：`','.join`, `IOError`, `RuntimeError`, `ValueError`, `any`, `array_sha256`, `atomic_json`, `attrs.get`, `cfg.persistent_input_path`, `checked_outputs.get`, `checked_sources.get`, `compressor`, `expected.items`, `fd4_block`, `hashlib.sha256`, `hashlib.sha256(encoded).hexdigest`, `hashlib.sha256(json.dumps(dependencies, sort_keys=True).encode()).hexdigest`, `identity`, `identity(cfg, frame).items`, `json.dumps`, `json.dumps(dependencies, sort_keys=True).encode`, `json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode`, `json.loads`, `len`, `list`, `manifest`, `min`, `needed.issubset`, `np.isfinite`, `np.isfinite(values).all`, `np.prod`, `print`, `progress.setdefault`, `progress.update`, `progress['checksums'].get`, `progress['dependencies'].get`, `published.items`, `requests_for`, `required_pressure_blocks`, `root.attrs.get`, `root.attrs.update`, `root.require_dataset`, `shutil.disk_usage`, `slice`, `sorted`, `source.attrs.get`, `source_record.exists`, `source_record.read_text`, `spatial_slices`, `stop_event.is_set`, `str`, `time.monotonic`, `time.sleep`, `tuple`, `zarr.open_group`

显式异常：

```python
IOError('Gradient write/read checksum mismatch')
RuntimeError('Insufficient disk space for pressure gradient and safety reserve')
RuntimeError('Pressure download stopped or made no progress for 30 minutes; partial gradients retained')
RuntimeError('Pressure download stopped or timed out')
ValueError('Gradient provenance mismatch')
ValueError('Non-finite pressure gradient')
ValueError('Pressure frame metadata differs')
ValueError('Pressure input is missing')
ValueError('Pressure input is not fully validated; use --stage follow while downloading')
ValueError('Pressure manifest hash mismatch')
ValueError('block_size must be positive')
ValueError(f'Pressure source checksum mismatch: {name}')
```

### `main`

[实现：第 244 行](../src/jhtdb_pipeline/pressure_local.py#L244)

```python
def main()
```

调用：`Event`, `FileLock`, `ThreadPoolExecutor`, `argparse.ArgumentParser`, `cfg.lock_path.mkdir`, `cfg.physical_time`, `compute_gradient`, `download_pressure`, `executor.submit`, `load_config`, `parser.add_argument`, `parser.parse_args`, `print`, `stop.set`, `str`, `worker.result`

## src/jhtdb_pipeline/processing.py

[完整源码](../src/jhtdb_pipeline/processing.py)

依赖：

```python
from __future__ import annotations
import json
import os
import shutil
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any, Iterator
import numpy as np
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from .config import RESULT_SCHEMA_VERSION, PipelineConfig, result_zarr_name
from .disk_fft import build_spectrum, filter_spectrum, mapped_array, release_pages
from .cq import compute_cq, ensure_cq_result, write_cq_artifacts
from .physics import ComponentView, ProductView, accumulate_product, axis2_spectrum, close_memmap, derivative_field, filter_field, filter_field_from_axis2_spectrum, filter_smooth_sharp_field, filter_smooth_sharp_from_spectrum, full_spectrum, regime_codes_from_thresholds, memmap, subtract_product, zero_field
from .store import create_result_group, create_shared_gradient_group, hash_zarr_array, open_complete_result
from .sbar_qa import compute_sbar_qa, ensure_sbar_result, write_sbar_artifacts
from .validation import atomic_json, input_manifest_hash
from .weak_asymmetry import write_weak_asymmetry_artifacts
```

模块常量/配置：

```python
RESULT_FIELDS = {'velocity_bar': ('<f4', 4), 'gradient_bar': ('<f4', 5), 'work_full': ('<f4', 3), 'work_resolved': ('<f4', 3), 'pi': ('<f4', 3), 's_bar': ('<f4', 3), 'regime': ('u1', 3)}
```

### `_sharp_edge_metadata`

[实现：第 59 行](../src/jhtdb_pipeline/processing.py#L59)

```python
def _sharp_edge_metadata(cfg: PipelineConfig, sigma: float) -> dict[str, Any]
```

### `_filter_metadata_matches`

[实现：第 65 行](../src/jhtdb_pipeline/processing.py#L65)

```python
def _filter_metadata_matches(metadata: Any, cfg: PipelineConfig, sigma: float) -> bool
```

调用：`bool`, `float`, `metadata.get`, `np.isclose`, `str`

### `_filter_with_optional_spectrum`

[实现：第 83 行](../src/jhtdb_pipeline/processing.py#L83)

```python
def _filter_with_optional_spectrum(source: Any, destination: Any, temp_a: Any, temp_b: Any, sigma: float, cfg: PipelineConfig, spectra: dict[tuple[Any, ...], np.ndarray] | None, key: tuple[Any, ...]) -> None
```

调用：`Path`, `TemporaryDirectory`, `build_spectrum`, `close_memmap`, `filter_field`, `filter_field_from_axis2_spectrum`, `filter_smooth_sharp_field`, `filter_smooth_sharp_from_spectrum`, `filter_spectrum`, `release_pages`, `spectra.get`

### `_complete_result_schema`

[实现：第 156 行](../src/jhtdb_pipeline/processing.py#L156)

```python
def _complete_result_schema(path: Path, sigma_grid: float) -> int | None
```

调用：`(path / 'COMPLETE').is_file`, `any`, `int`, `result_zarr_name`, `root.attrs.get`, `str`, `zarr.open_group`, `zarr_path.is_dir`

### `_complete_result_is_current`

[实现：第 173 行](../src/jhtdb_pipeline/processing.py#L173)

```python
def _complete_result_is_current(cfg: PipelineConfig, path: Path, sigma_grid: float) -> bool
```

调用：`_complete_result_schema`, `_filter_metadata_matches`, `all`, `input_manifest_hash`, `int`, `open_complete_result`, `root.attrs.get`, `tuple`

### `_shared_result_is_current`

[实现：第 197 行](../src/jhtdb_pipeline/processing.py#L197)

```python
def _shared_result_is_current(cfg: PipelineConfig, time_index: int, manifest_hash: str) -> bool
```

调用：`cfg.shared_result_path`, `complete_path.is_file`, `json.loads`, `manifest.get`, `manifest_path.is_file`, `manifest_path.read_text`, `np.dtype`, `root.attrs.get`, `store_path.is_dir`, `str`, `tuple`, `zarr.open_group`

### `_prepare_shared_gradient`

[实现：第 223 行](../src/jhtdb_pipeline/processing.py#L223)

```python
def _prepare_shared_gradient(cfg: PipelineConfig, time_index: int, manifest_hash: str) -> tuple[Any, bool]
```

调用：`_safe_rmtree`, `_shared_result_is_current`, `cfg.shared_gradient_store_path`, `cfg.shared_staging_result_path`, `create_shared_gradient_group`, `str`, `zarr.open_group`

### `_finalize_shared_gradient`

[实现：第 240 行](../src/jhtdb_pipeline/processing.py#L240)

```python
def _finalize_shared_gradient(cfg: PipelineConfig, time_index: int, manifest_hash: str, root: Any) -> Path
```

调用：`(final / 'COMPLETE').is_file`, `RuntimeError`, `_safe_rmtree`, `_shared_result_is_current`, `atomic_json`, `cfg.physical_time`, `cfg.shared_result_path`, `cfg.shared_staging_result_path`, `final.exists`, `hash_zarr_array`, `list`, `np.dtype`, `os.replace`, `root.attrs.update`, `str`

显式异常：

```python
RuntimeError('refusing to replace a different complete shared result')
```

### `_shared_references`

[实现：第 292 行](../src/jhtdb_pipeline/processing.py#L292)

```python
def _shared_references(cfg: PipelineConfig, time_index: int, manifest_hash: str) -> dict[str, Any]
```

调用：`(cfg.shared_result_path(time_index) / 'COMPLETE').resolve`, `cfg.raw_store_path`, `cfg.raw_store_path(time_index).resolve`, `cfg.shared_gradient_store_path`, `cfg.shared_gradient_store_path(time_index).resolve`, `cfg.shared_result_path`, `str`

### `_safe_rmtree`

[实现：第 307 行](../src/jhtdb_pipeline/processing.py#L307)

```python
def _safe_rmtree(path: Path, required_parent: Path) -> None
```

调用：`RuntimeError`, `path.exists`, `path.resolve`, `required_parent.resolve`, `shutil.rmtree`

显式异常：

```python
RuntimeError(f'refusing to remove unexpected path: {resolved}')
```

### `_spatial_keys`

[实现：第 316 行](../src/jhtdb_pipeline/processing.py#L316)

```python
def _spatial_keys(shape: tuple[int, int, int], chunks: tuple[int, int, int]) -> Iterator[tuple[slice, slice, slice]]
```

调用：`min`, `range`, `slice`

### `_copy_field`

[实现：第 327 行](../src/jhtdb_pipeline/processing.py#L327)

```python
def _copy_field(cfg: PipelineConfig, source: Any, destination: Any, prefix: tuple[int, ...]=()) -> None
```

调用：`IOError`, `ValueError`, `_spatial_keys`, `int`, `np.all`, `np.array_equal`, `np.asarray`, `np.ascontiguousarray`, `np.isfinite`, `release_pages`, `tuple`

显式异常：

```python
IOError('persistent full field failed write/read verification')
ValueError('full field contains NaN or Inf')
```

### `_zero_zarr`

[实现：第 347 行](../src/jhtdb_pipeline/processing.py#L347)

```python
def _zero_zarr(array: Any) -> None
```

调用：`_spatial_keys`, `int`, `np.zeros`, `tuple`

### `_accumulate_zarr`

[实现：第 354 行](../src/jhtdb_pipeline/processing.py#L354)

```python
def _accumulate_zarr(destination: Any, source: Any) -> None
```

调用：`_spatial_keys`, `int`, `np.asarray`, `tuple`

### `_accumulate_zarr_product`

[实现：第 363 行](../src/jhtdb_pipeline/processing.py#L363)

```python
def _accumulate_zarr_product(destination: Any, left: Any, right: Any) -> None
```

调用：`_spatial_keys`, `int`, `np.asarray`, `tuple`

### `_copy_full`

[实现：第 373 行](../src/jhtdb_pipeline/processing.py#L373)

```python
def _copy_full(destination: Any, source: Any, slab: int) -> None
```

调用：`min`, `np.asarray`, `range`, `slice`

### `_accumulate_full`

[实现：第 383 行](../src/jhtdb_pipeline/processing.py#L383)

```python
def _accumulate_full(destination: Any, source: Any, slab: int) -> None
```

调用：`min`, `np.asarray`, `range`, `slice`

### `_field_statistics`

[实现：第 395 行](../src/jhtdb_pipeline/processing.py#L395)

```python
def _field_statistics(field: Any, slab: int) -> tuple[float, float, int]
```

调用：`ValueError`, `float`, `max`, `min`, `np.abs`, `np.all`, `np.asarray`, `np.isfinite`, `np.max`, `np.square`, `np.square(values, dtype=np.float64).sum`, `range`, `release_pages`

显式异常：

```python
ValueError('spectral workspace contains NaN or Inf')
```

### `_divergence_metrics`

[实现：第 413 行](../src/jhtdb_pipeline/processing.py#L413)

```python
def _divergence_metrics(cfg: PipelineConfig, divergence_sumsq: float, divergence_maximum: float, point_count: int, gradient_sumsq: float, gradient_maximum: float, gradient_count: int) -> dict[str, float | int | bool | str]
```

调用：`float`, `max`, `np.sqrt`

### `_reusable_filtered_velocity`

[实现：第 441 行](../src/jhtdb_pipeline/processing.py#L441)

```python
def _reusable_filtered_velocity(cfg: PipelineConfig, time_index: int, sigma: float, manifest_hash: str, expected_shape: tuple[int, ...]) -> np.memmap | None
```

调用：`ComponentView`, `_field_statistics`, `_filter_metadata_matches`, `cfg.workspace_path`, `close_memmap`, `float`, `int`, `json.loads`, `memmap`, `metadata.get`, `metadata_path.is_file`, `metadata_path.read_text`, `np.prod`, `path.is_file`, `path.stat`, `range`, `tuple`

### `_write_full_regime`

[实现：第 479 行](../src/jhtdb_pipeline/processing.py#L479)

```python
def _write_full_regime(work_full: Any, work_resolved: Any, regime: Any, cfg: PipelineConfig) -> dict[str, Any]
```

调用：`BarColumn`, `Console`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `_spatial_keys`, `codes.ravel`, `float`, `int`, `max`, `np.all`, `np.asarray`, `np.bincount`, `np.isfinite`, `np.prod`, `np.sqrt`, `np.square`, `np.square(full, dtype=np.float64).sum`, `np.square(resolved, dtype=np.float64).sum`, `np.zeros`, `progress.add_task`, `progress.advance`, `regime_codes_from_thresholds`, `tuple`, `zip`

显式异常：

```python
RuntimeError('full-domain regime inputs and output must share the full shape')
ValueError('work fields contain NaN or Inf')
```

### `resource_plan`

[实现：第 556 行](../src/jhtdb_pipeline/processing.py#L556)

```python
def resource_plan(cfg: PipelineConfig) -> dict[str, float | str]
```

调用：`_sharp_edge_metadata`, `int`, `len`, `max`, `np.prod`

### `_preflight_batch_space`

[实现：第 631 行](../src/jhtdb_pipeline/processing.py#L631)

```python
def _preflight_batch_space(cfg: PipelineConfig, time_index: int, count: int) -> None
```

调用：`RuntimeError`, `cfg.result_root.mkdir`, `cfg.result_root.stat`, `cfg.run_path`, `int`, `max`, `np.prod`, `run.mkdir`, `run.stat`, `shutil.disk_usage`

显式异常：

```python
RuntimeError(f'insufficient batch space on {path}: {free / 1024 ** 3:.2f} GiB free, need {required / 1024 ** 3:.2f} GiB including shared cache and reserve')
```

### `_preflight_result_space`

[实现：第 655 行](../src/jhtdb_pipeline/processing.py#L655)

```python
def _preflight_result_space(cfg: PipelineConfig) -> dict[str, float]
```

调用：`RuntimeError`, `cfg.result_root.mkdir`, `int`, `shutil.disk_usage`, `str`

显式异常：

```python
RuntimeError(f'insufficient result space: {usage.free / 1024 ** 3:.2f} GiB free, need {required / 1024 ** 3:.2f} GiB including reserve')
```

### `_preflight_workspace_space`

[实现：第 673 行](../src/jhtdb_pipeline/processing.py#L673)

```python
def _preflight_workspace_space(cfg: PipelineConfig, time_index: int) -> None
```

调用：`RuntimeError`, `cfg.run_path`, `int`, `np.prod`, `path.mkdir`, `shutil.disk_usage`

显式异常：

```python
RuntimeError(f'insufficient scratch workspace: {usage.free / 1024 ** 3:.2f} GiB free, need {required / 1024 ** 3:.2f} GiB in addition to the velocity cache')
```

### `process_full`

[实现：第 689 行](../src/jhtdb_pipeline/processing.py#L689)

```python
def process_full(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None, *, _raw_gradients: np.ndarray | None=None, _filter_spectra: dict[tuple[Any, ...], np.ndarray] | None=None, _acquire_lock: bool=True) -> Path
```

调用：`BarColumn`, `ComponentView`, `Console`, `FileLock`, `ProductView`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `_accumulate_full`, `_accumulate_zarr`, `_accumulate_zarr_product`, `_copy_field`, `_copy_full`, `_divergence_metrics`, `_field_statistics`, `_filter_with_optional_spectrum`, `_finalize_shared_gradient`, `_preflight_result_space`, `_preflight_workspace_space`, `_prepare_shared_gradient`, `_reusable_filtered_velocity`, `_safe_rmtree`, `_shared_references`, `_sharp_edge_metadata`, `_write_full_regime`, `_zero_zarr`, `accumulate_product`, `atomic_json`, `bool`, `cfg.lock_path.mkdir`, `cfg.raw_store_path`, `cfg.result_path`, `cfg.run_path`, `cfg.staging_result_path`, `cfg.workspace_path`, `close_memmap`, `compute_cq`, `compute_sbar_qa`, `create_result_group`, `derivative.flush`, `derivative_field`, `filtered_velocity.flush`, `float`, `input_manifest_hash`, `list`, `max`, `memmap`, `min`, `np.asarray`, `np.dtype`, `process_full`, `progress.add_task`, `progress.advance`, `range`, `raw_root.attrs.get`, `result.attrs.update`, `reuse_complete_result`, `sgs_transport.flush`, `slice`, `str`, `subtract_product`, `workspace.mkdir`, `write_cq_artifacts`, `write_sbar_artifacts`, `write_weak_asymmetry_artifacts`, `zarr.open_group`, `zero_field`

显式异常：

```python
RuntimeError('velocity cache and persistent input manifest disagree')
RuntimeError(f"full-domain divergence validation failed: unfiltered_relative_rms={unfiltered_divergence_report['relative_divergence_rms']:.3e}, unfiltered_relative_max={unfiltered_divergence_report['relative_maximum_divergence']:.3e}, filtered_relative_rms={filtered_divergence_report['relative_divergence_rms']:.3e}, filtered_relative_max={filtered_divergence_report['relative_maximum_divergence']:.3e}")
ValueError('sigma_grid must be positive')
ValueError('validated velocity cache has an unexpected schema')
```

### `finalize_result`

[实现：第 1195 行](../src/jhtdb_pipeline/processing.py#L1195)

```python
def finalize_result(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> Path
```

调用：`(final / 'COMPLETE').is_file`, `FileExistsError`, `RESULT_FIELDS.items`, `RuntimeError`, `_safe_rmtree`, `_sharp_edge_metadata`, `atomic_json`, `bool`, `cfg.physical_time`, `cfg.result_path`, `cfg.run_path`, `cfg.staging_result_path`, `cfg.workspace_path`, `complete.open`, `dict`, `fields.items`, `final.exists`, `final.parent.mkdir`, `float`, `handle.fileno`, `handle.flush`, `handle.write`, `hash_zarr_array`, `input_manifest_hash`, `json.dumps`, `len`, `list`, `np.dtype`, `os.fsync`, `os.replace`, `result_zarr_name`, `reuse_complete_result`, `root.attrs.get`, `root.attrs.update`, `staging.is_dir`, `str`, `tuple`, `zarr.open_group`

显式异常：

```python
FileExistsError(f'refusing to replace incomplete result: {final}')
RuntimeError('persistent result staging directory is missing')
RuntimeError('persistent result staging has not completed processing')
RuntimeError(f'result field has invalid dtype: {name}={array.dtype}')
RuntimeError(f'result field has invalid shape: {name}={array.shape}')
RuntimeError(f'result field is missing: {name}')
```

### `_build_batch_reuse`

[实现：第 1303 行](../src/jhtdb_pipeline/processing.py#L1303)

```python
def _build_batch_reuse(cfg: PipelineConfig, raw: Any, cache_dir: Path | None=None) -> tuple[np.ndarray, dict[tuple[Any, ...], np.ndarray]]
```

Build shared gradients and twelve spectra once, in RAM or mapped files.

调用：`(cache_dir / 'acceleration.f32').unlink`, `BarColumn`, `ComponentView`, `Console`, `ProductView`, `Progress`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `acceleration.fill`, `accumulate_product`, `array._mmap.close`, `build_spectrum`, `close_memmap`, `derivative_field`, `isinstance`, `locals`, `locals().get`, `mapped_array`, `np.empty`, `progress.add_task`, `progress.advance`, `range`, `release_pages`, `spectra.values`, `spectrum_builder`

显式异常：

```python
ValueError('memmap cache requires a workspace directory')
```

### `_build_batch_reuse.spectrum_builder`

[实现：第 1347 行](../src/jhtdb_pipeline/processing.py#L1347)

```python
def _build_batch_reuse.spectrum_builder(source, slab, *, workers)
```

调用：`build_spectrum`

### `_write_filter_batch_manifest`

[实现：第 1402 行](../src/jhtdb_pipeline/processing.py#L1402)

```python
def _write_filter_batch_manifest(cfg: PipelineConfig, time_index: int, sigmas: tuple[float, ...], results: dict[float, Path], status: str) -> None
```

调用：`_complete_result_is_current`, `_filter_metadata_matches`, `all_sigmas.add`, `atomic_json`, `cfg.batch_manifest_path`, `cfg.physical_time`, `cfg.result_id`, `cfg.result_id(time_index, 1.0).rsplit`, `cfg.result_path`, `cfg.result_path(time_index, sigma).resolve`, `cfg.result_root.glob`, `cfg.result_root.mkdir`, `float`, `int`, `json.loads`, `list`, `manifest.get`, `manifest_path.is_file`, `manifest_path.read_text`, `path.is_dir`, `set`, `sorted`, `str`, `tuple`

### `process_batch`

[实现：第 1455 行](../src/jhtdb_pipeline/processing.py#L1455)

```python
def process_batch(cfg: PipelineConfig, time_index: int, sigma_grids: tuple[float, ...] | None=None) -> list[Path]
```

Process missing sigmas with shared raw gradients and filter spectra.

调用：`FileLock`, `Path`, `RuntimeError`, `TemporaryDirectory`, `ValueError`, `_build_batch_reuse`, `_preflight_batch_space`, `_write_filter_batch_manifest`, `any`, `cfg.lock_path.mkdir`, `cfg.raw_store_path`, `cfg.run_path`, `close_memmap`, `finalize_result`, `float`, `input_manifest_hash`, `isinstance`, `len`, `np.dtype`, `np.isfinite`, `pending.append`, `print`, `process_full`, `raw_root.attrs.get`, `reuse_complete_result`, `set`, `spectra.clear`, `spectra.values`, `str`, `tuple`, `zarr.open_group`

显式异常：

```python
RuntimeError('insufficient RAM for the multi-sigma cache; approximately 84 GiB is required')
RuntimeError('validated velocity cache has an unexpected schema')
RuntimeError('velocity cache and persistent input manifest disagree')
ValueError('at least one sigma is required')
ValueError('sigma values must be finite and positive')
ValueError('sigma values must be unique')
```

### `reuse_complete_result`

[实现：第 1542 行](../src/jhtdb_pipeline/processing.py#L1542)

```python
def reuse_complete_result(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> Path | None
```

调用：`_complete_result_is_current`, `cfg.result_path`, `ensure_cq_result`, `ensure_sbar_result`, `float`

## src/jhtdb_pipeline/regime_pi.py

[完整源码](../src/jhtdb_pipeline/regime_pi.py)

依赖：

```python
from regime_pi.statistics import DEFAULT_REGIME_PI_OUTPUT_ROOT, REGIME_PI_REPORT_VERSION, compute_regime_pi_statistics, regime_pi_output_dir, regime_pi_report_is_current, run_regime_pi_statistics
```

此入口只包含导入、常量或顶层调用。

## src/jhtdb_pipeline/sbar_qa.py

[完整源码](../src/jhtdb_pipeline/sbar_qa.py)

依赖：

```python
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import numpy as np
import plotly.graph_objects as go
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from .config import RESULT_SCHEMA_VERSION, PipelineConfig, result_zarr_name
from .store import spatial_slices
from .validation import atomic_json
```

模块常量/配置：

```python
SBAR_REPORT_VERSION = 3
FIELD_ORDER = ('s_bar', 'pi', 'work_resolved', 'work_full')
FIELD_LABELS = {'s_bar': 'ΣS̄', 'pi': 'ΣΠ', 'work_resolved': 'ΣW_res', 'work_full': 'ΣW_full'}
```

### `_safe_ratio`

[实现：第 31 行](../src/jhtdb_pipeline/sbar_qa.py#L31)

```python
def _safe_ratio(numerator: float, denominator: float) -> tuple[float | None, str | None]
```

调用：`abs`

### `compute_sbar_qa`

[实现：第 39 行](../src/jhtdb_pipeline/sbar_qa.py#L39)

```python
def compute_sbar_qa(root: Any, cfg: PipelineConfig, *, scope: str) -> dict[str, Any]
```

调用：`BarColumn`, `Console`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `_safe_ratio`, `any`, `arrays.items`, `arrays.values`, `block.astype`, `block.sum`, `bool`, `field_sumsq.items`, `field_sumsq.values`, `float`, `int`, `len`, `max`, `np.abs`, `np.all`, `np.asarray`, `np.dtype`, `np.isfinite`, `np.max`, `np.prod`, `np.sqrt`, `np.square`, `np.square(block).sum`, `np.square(residual).sum`, `progress.add_task`, `progress.advance`, `shapes.pop`, `spatial_slices`, `sum`, `tuple`, `values.items`, `values.values`, `values64.items`, `zip`

显式异常：

```python
RuntimeError('the four energy fields do not have identical shapes')
RuntimeError('the four energy fields must be float32')
RuntimeError(f'S_bar QA scope {scope} expects {expected}, found {shape}')
ValueError('QA requires full_domain scope')
ValueError('the four energy fields contain NaN or Inf')
```

### `write_sbar_artifacts`

[实现：第 167 行](../src/jhtdb_pipeline/sbar_qa.py#L167)

```python
def write_sbar_artifacts(result_dir: Path, report: dict[str, Any]) -> str
```

调用：`atomic_json`, `figure.update_layout`, `figure.write_html`, `go.Bar`, `go.Figure`, `os.replace`, `output.with_suffix`, `str`

### `_report_hash`

[实现：第 193 行](../src/jhtdb_pipeline/sbar_qa.py#L193)

```python
def _report_hash(path: Path) -> str
```

调用：`hashlib.sha256`, `hashlib.sha256(path.read_bytes()).hexdigest`, `path.read_bytes`

### `_load_chained_report`

[实现：第 197 行](../src/jhtdb_pipeline/sbar_qa.py#L197)

```python
def _load_chained_report(result_dir: Path, root: Any) -> dict[str, Any] | None
```

调用：`(result_dir / 's_bar_global_totals.html').is_file`, `_report_hash`, `complete.get`, `complete_path.is_file`, `complete_path.read_text`, `json.loads`, `manifest.get`, `manifest_path.is_file`, `manifest_path.read_text`, `path.is_file`, `path.read_text`, `report.get`, `root.attrs.get`

### `_reclassify_report`

[实现：第 229 行](../src/jhtdb_pipeline/sbar_qa.py#L229)

```python
def _reclassify_report(report: dict[str, Any], cfg: PipelineConfig) -> dict[str, Any]
```

调用：`bool`, `float`, `identity.get`, `identity.update`, `metrics.get`, `report.get`, `vs_pi.get`, `vs_pi.update`

### `_can_reclassify`

[实现：第 261 行](../src/jhtdb_pipeline/sbar_qa.py#L261)

```python
def _can_reclassify(report: dict[str, Any]) -> bool
```

调用：`all`, `metrics.get`, `report.get`, `set`

### `_thresholds_are_current`

[实现：第 276 行](../src/jhtdb_pipeline/sbar_qa.py#L276)

```python
def _thresholds_are_current(report: dict[str, Any], cfg: PipelineConfig) -> bool
```

调用：`_can_reclassify`, `_reclassify_report`, `_reclassify_report(json.loads(json.dumps(report)), cfg).get`, `bool`, `float`, `identity.get`, `json.dumps`, `json.loads`, `metrics.get`, `report.get`, `vs_pi.get`

### `sbar_report_is_current`

[实现：第 303 行](../src/jhtdb_pipeline/sbar_qa.py#L303)

```python
def sbar_report_is_current(result_dir: Path, root: Any, cfg: PipelineConfig) -> bool
```

调用：`_load_chained_report`, `_thresholds_are_current`

### `_run_sbar_qa_locked`

[实现：第 310 行](../src/jhtdb_pipeline/sbar_qa.py#L310)

```python
def _run_sbar_qa_locked(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> dict[str, Any]
```

调用：`(result_dir / 'COMPLETE').is_file`, `RuntimeError`, `_can_reclassify`, `_load_chained_report`, `_reclassify_report`, `_thresholds_are_current`, `atomic_json`, `cfg.result_path`, `compute_sbar_qa`, `float`, `json.loads`, `manifest.update`, `manifest_path.read_text`, `qa_path.read_text`, `result_zarr_name`, `root.attrs.get`, `root.attrs.update`, `str`, `write_sbar_artifacts`, `zarr.open_group`

显式异常：

```python
RuntimeError('complete result is missing')
RuntimeError('current full-domain result schema is required')
```

### `run_sbar_qa`

[实现：第 366 行](../src/jhtdb_pipeline/sbar_qa.py#L366)

```python
def run_sbar_qa(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> dict[str, Any]
```

调用：`FileLock`, `_run_sbar_qa_locked`, `cfg.lock_path.mkdir`, `cfg.result_id`, `float`, `str`

### `ensure_sbar_result`

[实现：第 378 行](../src/jhtdb_pipeline/sbar_qa.py#L378)

```python
def ensure_sbar_result(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> Path
```

调用：`(result_dir / 'COMPLETE').is_file`, `RuntimeError`, `cfg.result_path`, `float`, `result_zarr_name`, `run_sbar_qa`, `sbar_report_is_current`, `str`, `zarr.open_group`

显式异常：

```python
RuntimeError('complete result is missing')
```

## src/jhtdb_pipeline/store.py

[完整源码](../src/jhtdb_pipeline/store.py)

依赖：

```python
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Iterator
import numpy as np
import zarr
from numcodecs import Blosc
from numcodecs import blosc
from .config import RESULT_SCHEMA_VERSION, PipelineConfig, result_zarr_name
from .planning import Tile
```

### `array_sha256`

[实现：第 17 行](../src/jhtdb_pipeline/store.py#L17)

```python
def array_sha256(values: np.ndarray) -> str
```

调用：`canonical.view`, `hashlib.sha256`, `hashlib.sha256(canonical.view(np.uint8)).hexdigest`, `np.ascontiguousarray`

### `compressor`

[实现：第 22 行](../src/jhtdb_pipeline/store.py#L22)

```python
def compressor(cfg: PipelineConfig) -> Blosc
```

调用：`Blosc`, `blosc.set_nthreads`

### `VelocityStore`

[实现：第 31 行](../src/jhtdb_pipeline/store.py#L31)

```python
class VelocityStore()
```

### `VelocityStore.__init__`

[实现：第 32 行](../src/jhtdb_pipeline/store.py#L32)

```python
def VelocityStore.__init__(self, cfg: PipelineConfig, time_index: int)
```

调用：`ValueError`, `any`, `cfg.physical_time`, `cfg.raw_store_path`, `expected.items`, `getattr`, `len`, `list`, `path.parent.mkdir`, `self.root.attrs.get`, `self.root.attrs.update`, `str`, `zarr.open_group`

显式异常：

```python
ValueError('pressure-gradient cache metadata differs from requested acquisition')
```

### `VelocityStore.ensure_array`

[实现：第 62 行](../src/jhtdb_pipeline/store.py#L62)

```python
def VelocityStore.ensure_array(self)
```

调用：`compressor`, `self.root.require_dataset`

### `VelocityStore.array`

[实现：第 76 行](../src/jhtdb_pipeline/store.py#L76)

```python
def VelocityStore.array(self)
```

### `VelocityStore.write_tile`

[实现：第 79 行](../src/jhtdb_pipeline/store.py#L79)

```python
def VelocityStore.write_tile(self, tile: Tile, values: np.ndarray) -> str
```

调用：`IOError`, `ValueError`, `array_sha256`, `np.all`, `np.ascontiguousarray`, `np.isfinite`

显式异常：

```python
IOError(f'tile {tile.key} failed write/read checksum')
ValueError(f'tile {tile.key} contains NaN or Inf')
ValueError(f'tile {tile.key} shape {canonical.shape}, expected {expected}')
```

### `VelocityStore.mark_validated`

[实现：第 93 行](../src/jhtdb_pipeline/store.py#L93)

```python
def VelocityStore.mark_validated(self, manifest_hash: str) -> None
```

调用：`self.root.attrs.update`

### `create_result_group`

[实现：第 97 行](../src/jhtdb_pipeline/store.py#L97)

```python
def create_result_group(cfg: PipelineConfig, time_index: int, sigma_grid: float, *, overwrite: bool)
```

调用：`cfg.physical_time`, `cfg.staging_result_path`, `compressor`, `float`, `list`, `min`, `result_zarr_name`, `root.attrs.update`, `root.require_dataset`, `staging.mkdir`, `str`, `zarr.open_group`

### `create_shared_gradient_group`

[实现：第 172 行](../src/jhtdb_pipeline/store.py#L172)

```python
def create_shared_gradient_group(cfg: PipelineConfig, time_index: int, *, staging: bool, overwrite: bool)
```

调用：`cfg.physical_time`, `cfg.shared_result_path`, `cfg.shared_staging_result_path`, `compressor`, `directory.mkdir`, `list`, `min`, `root.attrs.update`, `root.require_dataset`, `str`, `zarr.open_group`

### `CompositeResult`

[实现：第 213 行](../src/jhtdb_pipeline/store.py#L213)

```python
class CompositeResult()
```

Read-only logical result joining per-sigma and shared arrays.

### `CompositeResult.__init__`

[实现：第 216 行](../src/jhtdb_pipeline/store.py#L216)

```python
def CompositeResult.__init__(self, root: Any, shared: dict[str, Any])
```

### `CompositeResult.__contains__`

[实现：第 221 行](../src/jhtdb_pipeline/store.py#L221)

```python
def CompositeResult.__contains__(self, name: str) -> bool
```

### `CompositeResult.__getitem__`

[实现：第 224 行](../src/jhtdb_pipeline/store.py#L224)

```python
def CompositeResult.__getitem__(self, name: str) -> Any
```

### `CompositeResult.__iter__`

[实现：第 229 行](../src/jhtdb_pipeline/store.py#L229)

```python
def CompositeResult.__iter__(self)
```

调用：`dict.fromkeys`, `iter`, `self.root.array_keys`

### `CompositeResult.keys`

[实现：第 232 行](../src/jhtdb_pipeline/store.py#L232)

```python
def CompositeResult.keys(self)
```

调用：`iter`, `list`

### `CompositeResult.array_keys`

[实现：第 235 行](../src/jhtdb_pipeline/store.py#L235)

```python
def CompositeResult.array_keys(self)
```

调用：`iter`, `self.keys`

### `spatial_slices`

[实现：第 239 行](../src/jhtdb_pipeline/store.py#L239)

```python
def spatial_slices(shape: tuple[int, ...], chunk_shape: tuple[int, ...]) -> Iterator[tuple[slice, ...]]
```

调用：`ValueError`, `len`, `min`, `range`, `slice`, `walk`

显式异常：

```python
ValueError('shape and chunk_shape ranks differ')
```

### `spatial_slices.walk`

[实现：第 243 行](../src/jhtdb_pipeline/store.py#L243)

```python
def spatial_slices.walk(axis: int, prefix: tuple[slice, ...])
```

调用：`len`, `min`, `range`, `slice`, `walk`

### `hash_zarr_array`

[实现：第 254 行](../src/jhtdb_pipeline/store.py#L254)

```python
def hash_zarr_array(array: Any) -> tuple[str, int, float, float]
```

调用：`ValueError`, `float`, `hasher.hexdigest`, `hasher.update`, `hashlib.sha256`, `max`, `min`, `np.all`, `np.ascontiguousarray`, `np.isfinite`, `spatial_slices`, `tuple`, `values.max`, `values.min`, `values.view`

显式异常：

```python
ValueError('result array contains NaN or Inf')
```

### `open_complete_result`

[实现：第 270 行](../src/jhtdb_pipeline/store.py#L270)

```python
def open_complete_result(path: Path)
```

调用：`(path / 'COMPLETE').is_file`, `(path / 'manifest.json').read_text`, `(path / 'shared_refs.json').read_text`, `CompositeResult`, `Path`, `Path(references['shared_complete']).is_file`, `RuntimeError`, `float`, `json.loads`, `manifest.get`, `raw_root.attrs.get`, `references.get`, `result_zarr_name`, `reversed`, `root.attrs.get`, `shared_root.attrs.get`, `str`, `tuple`, `zarr.open_group`

显式异常：

```python
RuntimeError('result and shared inputs have different or incomplete metadata')
RuntimeError('result requires full-domain schema v7; rebuild from validated velocity')
RuntimeError(f'result field is missing: {name}')
RuntimeError(f'result field is not full-domain: {name}')
RuntimeError(f'result is not complete: {path}')
RuntimeError(f'result metadata is incomplete or outdated: {path}')
RuntimeError(f'shared full-domain data is not complete: {shared_path}')
```

## src/jhtdb_pipeline/strain.py

[完整源码](../src/jhtdb_pipeline/strain.py)

依赖：

```python
from block_statistics.strain import STRAIN_CACHE_VERSION, ensure_strain_cache, _accumulate, _cache_is_current, _build_cache
```

模块常量/配置：

```python
__all__ = ['STRAIN_CACHE_VERSION', 'ensure_strain_cache']
```

此入口只包含导入、常量或顶层调用。

## src/jhtdb_pipeline/validation.py

[完整源码](../src/jhtdb_pipeline/validation.py)

依赖：

```python
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import numpy as np
from .catalog import Catalog
from .config import PipelineConfig
from .planning import tiles_for
from .store import VelocityStore, array_sha256
```

### `atomic_json`

[实现：第 17 行](../src/jhtdb_pipeline/validation.py#L17)

```python
def atomic_json(path: Path, payload: dict[str, Any]) -> str
```

调用：`handle.fileno`, `handle.flush`, `handle.write`, `hashlib.sha256`, `hashlib.sha256(encoded).hexdigest`, `json.dumps`, `json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode`, `os.fsync`, `os.replace`, `path.parent.mkdir`, `path.with_suffix`, `temporary.open`

### `_seam_statistics`

[实现：第 32 行](../src/jhtdb_pipeline/validation.py#L32)

```python
def _seam_statistics(array: Any) -> dict[str, dict[str, float]]
```

调用：`axes.items`, `float`, `max`, `np.asarray`, `np.mean`, `np.sqrt`, `np.square`, `slice`

### `validate_snapshot`

[实现：第 65 行](../src/jhtdb_pipeline/validation.py#L65)

```python
def validate_snapshot(cfg: PipelineConfig, time_index: int) -> dict[str, Any]
```

调用：`Catalog`, `ValueError`, `VelocityStore`, `_seam_statistics`, `array_sha256`, `atomic_json`, `block.astype`, `catalog.set_snapshot_status`, `catalog.tiles`, `cfg.physical_time`, `float`, `getattr`, `len`, `list`, `manifest.update`, `max`, `min`, `np.all`, `np.ascontiguousarray`, `np.dtype`, `np.isfinite`, `np.sqrt`, `np.square`, `np.square(values64).sum`, `store.mark_validated`, `tile_manifest.append`, `tiles_for`, `values64.max`, `values64.min`, `values64.sum`

显式异常：

```python
ValueError('catalog coverage differs from the deterministic tile plan')
ValueError(f'tile {tile.key} checksum differs from catalog')
ValueError(f'tile {tile.key} contains NaN or Inf')
ValueError(f'tile {tile.key} has an invalid shape')
ValueError(f'tile {tile.key} is not verified')
ValueError(f'velocity cache schema mismatch: shape={array.shape}, dtype={array.dtype}')
```

### `input_manifest_hash`

[实现：第 166 行](../src/jhtdb_pipeline/validation.py#L166)

```python
def input_manifest_hash(cfg: PipelineConfig, time_index: int) -> str
```

调用：`Catalog`, `RuntimeError`, `catalog.snapshot`, `str`

显式异常：

```python
RuntimeError('the complete velocity cache has not passed validation')
```

## src/jhtdb_pipeline/weak_asymmetry.py

[完整源码](../src/jhtdb_pipeline/weak_asymmetry.py)

依赖：

```python
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any
import numpy as np
import plotly.graph_objects as go
import zarr
from filelock import FileLock
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from .config import RESULT_SCHEMA_VERSION, PipelineConfig, result_zarr_name
from .store import spatial_slices
from .validation import atomic_json
```

模块常量/配置：

```python
WEAK_ASYMMETRY_REPORT_VERSION = 2
```

### `AbsPiPercentileAccumulator`

[实现：第 24 行](../src/jhtdb_pipeline/weak_asymmetry.py#L24)

```python
class AbsPiPercentileAccumulator()
```

Compute exact linear p99/max from one stream of nonnegative float32 data.

### `AbsPiPercentileAccumulator.__init__`

[实现：第 27 行](../src/jhtdb_pipeline/weak_asymmetry.py#L27)

```python
def AbsPiPercentileAccumulator.__init__(self, point_count: int) -> None
```

调用：`ValueError`, `int`, `max`, `np.ceil`, `np.floor`

显式异常：

```python
ValueError('percentile point count must be positive')
```

### `AbsPiPercentileAccumulator.add`

[实现：第 40 行](../src/jhtdb_pipeline/weak_asymmetry.py#L40)

```python
def AbsPiPercentileAccumulator.add(self, absolute_values: np.ndarray) -> None
```

调用：`ValueError`, `int`, `np.all`, `np.any`, `np.asarray`, `np.asarray(absolute_values, dtype=np.float32).reshape`, `np.isfinite`, `self._consolidate`, `self.buffers.append`

显式异常：

```python
ValueError('absolute pi values must be finite and nonnegative')
```

### `AbsPiPercentileAccumulator._consolidate`

[实现：第 50 行](../src/jhtdb_pipeline/weak_asymmetry.py#L50)

```python
def AbsPiPercentileAccumulator._consolidate(self) -> None
```

调用：`combined.partition`, `combined[cutoff:].copy`, `int`, `np.concatenate`

### `AbsPiPercentileAccumulator.result`

[实现：第 64 行](../src/jhtdb_pipeline/weak_asymmetry.py#L64)

```python
def AbsPiPercentileAccumulator.result(self) -> tuple[float, float]
```

调用：`RuntimeError`, `float`, `np.max`, `self._consolidate`, `upper_tail.partition`

显式异常：

```python
RuntimeError('p99 point coverage is incomplete')
```

### `_chunk_count`

[实现：第 79 行](../src/jhtdb_pipeline/weak_asymmetry.py#L79)

```python
def _chunk_count(shape: tuple[int, ...], chunks: tuple[int, ...]) -> int
```

调用：`int`, `np.prod`, `zip`

### `build_weak_asymmetry_report`

[实现：第 91 行](../src/jhtdb_pipeline/weak_asymmetry.py#L91)

```python
def build_weak_asymmetry_report(*, point_count: int, pi_sum: float, abs_pi_sum: float, pi_sumsq: float, abs_pi_p99: float, abs_pi_max: float, positive_sum: float, negative_sum: float, positive_count: int, negative_count: int, zero_count: int, closure_relative_max: float) -> dict[str, Any]
```

调用：`ValueError`, `_safe_nonnegative_ratio`, `abs`, `float`, `np.sqrt`

显式异常：

```python
ValueError('weak-asymmetry point count must be positive')
```

### `_safe_nonnegative_ratio`

[实现：第 200 行](../src/jhtdb_pipeline/weak_asymmetry.py#L200)

```python
def _safe_nonnegative_ratio(numerator: float, denominator: float, denominator_name: str) -> tuple[float | None, str | None]
```

### `compute_weak_asymmetry`

[实现：第 210 行](../src/jhtdb_pipeline/weak_asymmetry.py#L210)

```python
def compute_weak_asymmetry(root: Any, cfg: PipelineConfig) -> dict[str, Any]
```

调用：`AbsPiPercentileAccumulator`, `BarColumn`, `Console`, `Progress`, `RuntimeError`, `SpinnerColumn`, `TextColumn`, `TimeElapsedColumn`, `ValueError`, `_chunk_count`, `absolute_values.sum`, `build_weak_asymmetry_report`, `float`, `int`, `np.abs`, `np.all`, `np.any`, `np.asarray`, `np.count_nonzero`, `np.dtype`, `np.isfinite`, `np.prod`, `np.square`, `np.square(values64).sum`, `progress.add_task`, `progress.advance`, `spatial_slices`, `tail.add`, `tail.result`, `tuple`, `values.astype`, `values64.sum`, `values64[negative].sum`, `values64[positive].sum`

显式异常：

```python
RuntimeError('weak asymmetry requires full-domain float32 pi')
ValueError('pi contains NaN or Inf')
```

### `write_weak_asymmetry_artifacts`

[实现：第 279 行](../src/jhtdb_pipeline/weak_asymmetry.py#L279)

```python
def write_weak_asymmetry_artifacts(result_dir: Path, report: dict[str, Any]) -> str
```

调用：`atomic_json`, `figure.update_layout`, `figure.write_html`, `go.Bar`, `go.Figure`, `os.replace`, `output.with_suffix`, `str`

### `_file_hash`

[实现：第 310 行](../src/jhtdb_pipeline/weak_asymmetry.py#L310)

```python
def _file_hash(path: Path) -> str
```

调用：`hashlib.sha256`, `hashlib.sha256(path.read_bytes()).hexdigest`, `path.read_bytes`

### `_load_chained_report`

[实现：第 314 行](../src/jhtdb_pipeline/weak_asymmetry.py#L314)

```python
def _load_chained_report(result_dir: Path, root: Any) -> dict[str, Any] | None
```

调用：`_file_hash`, `all`, `complete.get`, `complete_path.read_text`, `json.loads`, `manifest.get`, `manifest_path.read_text`, `path.is_file`, `report.get`, `report_path.read_text`, `root.attrs.get`

### `weak_asymmetry_report_is_current`

[实现：第 350 行](../src/jhtdb_pipeline/weak_asymmetry.py#L350)

```python
def weak_asymmetry_report_is_current(result_dir: Path, root: Any) -> bool
```

调用：`_load_chained_report`, `all`, `bool`, `report.get`

### `_persist_weak_asymmetry`

[实现：第 363 行](../src/jhtdb_pipeline/weak_asymmetry.py#L363)

```python
def _persist_weak_asymmetry(result_dir: Path, root: Any, report: dict[str, Any]) -> None
```

调用：`atomic_json`, `json.loads`, `manifest.update`, `manifest_path.read_text`, `qa_path.read_text`, `root.attrs.update`, `write_weak_asymmetry_artifacts`

### `run_weak_asymmetry`

[实现：第 401 行](../src/jhtdb_pipeline/weak_asymmetry.py#L401)

```python
def run_weak_asymmetry(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> dict[str, Any]
```

调用：`(result_dir / 'COMPLETE').is_file`, `FileLock`, `RuntimeError`, `_persist_weak_asymmetry`, `cfg.lock_path.mkdir`, `cfg.result_id`, `cfg.result_path`, `compute_weak_asymmetry`, `float`, `result_zarr_name`, `root.attrs.get`, `str`, `zarr.open_group`

显式异常：

```python
RuntimeError('complete result is missing')
RuntimeError('current full-domain result schema is required')
```

### `ensure_weak_asymmetry_result`

[实现：第 423 行](../src/jhtdb_pipeline/weak_asymmetry.py#L423)

```python
def ensure_weak_asymmetry_result(cfg: PipelineConfig, time_index: int, sigma_grid: float | None=None) -> Path
```

调用：`cfg.result_path`, `float`, `result_zarr_name`, `run_weak_asymmetry`, `str`, `weak_asymmetry_report_is_current`, `zarr.open_group`

