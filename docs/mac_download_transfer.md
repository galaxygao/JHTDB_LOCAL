# Mac 下载，Windows 计算

> 本页仅用于独立的服务端 `fd4noint` 梯度路径。当前 deploy 默认使用标量压力下载 + 本地 FD4，见 [部署说明](deployment.md)。通用跨机步骤见 [系统迁移](system_migration.md)。

此流程只下载 isotropic1024coarse 第 1 帧（t=0）的压力梯度，方法仍为
fd4noint。请求块仍是 128×128×64，串行下载。不会在 Mac 执行压力功率或多 sigma 计算。

## Mac 启动

将下载工具包解压到 Mac，打开终端，进入解压目录。需要已安装 Python 3.9 或更高版本。
不要复制 Windows 的虚拟环境；脚本会新建 `.venv-mac`，并安装项目依赖。

```bash
cd /你的路径/JHTDB_MAC_DOWNLOAD
bash scripts/download_pressure_mac.sh
```

按提示粘贴自己的 JHTDB token（输入不回显，不保存到文件）。数据默认放在
`$HOME/JHTDB_DOWNLOAD/state`。若放到外置盘，在启动前指定绝对路径：

```bash
export JHTDB_MAC_ROOT="/Volumes/你的磁盘/JHTDB_DOWNLOAD"
bash scripts/download_pressure_mac.sh
```

下载启动检查要求至少约 36 GiB 可用空间（12 GiB 未压缩梯度加 24 GiB 预留）。
打包还需要额外容纳一份缓存。此门槛仅针对下载，不是完整计算所需空间。
保持网络连接和电脑开盖；脚本用 caffeinate 防止空闲睡眠。
中断后使用相同数据路径重新运行即可续传。退出码非零或报错不代表下载完成；
只有看到 `Download and validation completed` 才进入打包步骤。

## 下载完成后打包

确认所有使用此 Mac 数据目录的下载程序已退出，不要在打包时重新启动下载。
以下命令在工具包根目录运行。若用了外置盘，保持上面的 JHTDB_MAC_ROOT 设置。
SQLite 使用 backup API 导出，避免遗漏 WAL 中的记录。

```bash
export JHTDB_MAC_ROOT="${JHTDB_MAC_ROOT:-$HOME/JHTDB_DOWNLOAD}"
.venv-mac/bin/python - <<'PY'
import os, sqlite3
from pathlib import Path
root = Path(os.environ['JHTDB_MAC_ROOT'])
out = root / 'transfer_metadata'
out.mkdir(exist_ok=True)
source = sqlite3.connect((root / 'state/pressure_gradient_catalog.sqlite').as_uri() + '?mode=ro', uri=True)
row = source.execute('SELECT status FROM snapshots WHERE dataset=? AND time_index=1', ('isotropic1024coarse',)).fetchone()
if row != ('validated',):
    raise SystemExit('Frame 1 has not passed validation; do not transfer yet.')
destination = sqlite3.connect(out / 'pressure_gradient_catalog.sqlite')
source.backup(destination)
destination.close()
source.close()
PY
# 仅在上面命令成功后执行：
tar -cf "$JHTDB_MAC_ROOT/pressure_gradient_t000001.tar" \
  -C "$JHTDB_MAC_ROOT/state" \
  inputs/t000001/pressure_gradient_cache.zarr \
  manifests/pressure_gradient/input_t000001.json \
  qa/pressure_gradient/input_t000001.json \
  -C "$JHTDB_MAC_ROOT/transfer_metadata" pressure_gradient_catalog.sqlite
```

将 `pressure_gradient_t000001.tar` 复制到 Windows。归档不包含 token、虚拟环境或速度缓存。

## Windows 整合

先解压到独立暂存目录，不直接覆盖现有 state。停止所有读写压力梯度缓存的任务。
备份 Windows 现有压力梯度缓存、数据库及存在的 `-wal` / `-shm` 文件；
移走旧数据库时同步移走其 sidecar，不能把旧 WAL 留给新数据库。

把归档中的四项按相对路径放入 `C:/Xingqun_Gao/persistent/state/`：

- `inputs/t000001/pressure_gradient_cache.zarr/` 整个目录
- `pressure_gradient_catalog.sqlite`
- `manifests/pressure_gradient/input_t000001.json`
- `qa/pressure_gradient/input_t000001.json`

只替换上述压力梯度项目，保留 Windows 的 velocity_cache.zarr、catalog.sqlite 和其他结果。
不要把新旧 Zarr 目录混合。此流程假设压力梯度数据库只有当前第 1 帧；
若 Windows 后续又下载了其他帧，应先单独合并目录和数据库记录，不能整库覆盖。

在 Windows 工程根目录运行纯本地校验，不会发起下载：

```cmd
.venv\Scripts\python.exe -m jhtdb_pipeline validate-input --field pressure_gradient --time-index 1 --config configs/pipeline.yaml
```

校验成功后，检查速度与压力梯度是否已满足计算要求：

```cmd
.venv\Scripts\python.exe qpower_analysis\qpower_analysis.py --config qpower_analysis\config.example.json --preflight-only
```

preflight 成功后，去掉 `--preflight-only` 才会启动压力功率计算。
此工具包已在 Windows 验证配置和现有相关测试；尚未在真实 macOS 上安装或实测下载。
