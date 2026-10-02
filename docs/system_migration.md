# 系统迁移与恢复

## 可迁移内容和本机内容

同步源码、配置模板、文档及需要的科学数据；每台机器重新建立 `.venv` / `.venv-mac` / `.venv-windows` / `.venv-linux`。`deploy.py` 会重新生成 `<data-root>/pipeline.yaml`，不能依赖上次手改该生成文件的计算参数。主计算应使用独立的本机配置。

Git ignore 不控制云盘同步。虚拟环境、token、大型工作区、活动 SQLite/Zarr 应在同步客户端单独排除；暂停写入后再迁移。完整结果依赖同帧速度缓存及共享梯度，scratch/FFT 缓存可重建。依赖只锁定范围，目标机安装可能解析出不同版本；迁移前后记录 `python -m pip freeze`、`python --version`、代码版本和本机配置以便复现，不把 token 写入记录。

## Token 录入

临时环境变量方式见 [根 README](../README.md)。持续使用单行 token 文件：

```bash
# macOS/Linux：隐藏输入，写入用户目录，并显式限制权限。
python3 - <<'PY'
import getpass, os
from pathlib import Path
p = Path.home() / '.secrets/jhtdb_token'
p.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.fchmod(fd, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(getpass.getpass('JHTDB token: ').strip() + '\n')
PY
```

Windows PowerShell：

```powershell
$TokenPath = Join-Path $HOME '.secrets\jhtdb_token'
New-Item -ItemType Directory -Force (Split-Path $TokenPath) | Out-Null
$Secret = Read-Host 'JHTDB token' -AsSecureString
[IO.File]::WriteAllText($TokenPath, [System.Net.NetworkCredential]::new('', $Secret).Password)
```

将 YAML `auth.token_file` 指向该文件，或 `deploy.py --token-file <路径>`。deploy 依次选择显式 token 文件、项目 `.secrets/jhtdb_token`、用户 `.secrets/jhtdb_token`，实际 auth 中环境变量仍最高优先。POSIX auth 会拒绝组/其他用户可读写的 token 文件。不要提交 token 文件。

## 输入数据迁移：Mac → Windows（反向相同）

1. 停止使用待迁移 state 的下载、差分、计算和 GUI；检查日志与进程，不能只看 PID 文件。
2. 将 **整个 state_root** 复制到新的空目标目录。包含 inputs、catalog、manifests、qa；不能只复制 Zarr，不能把两个 Zarr 树合并。SQLite 连接全部关闭后复制，或使用下面的 backup API；若复制数据库而保留了旧目标 WAL，会污染数据。
3. 本地压力使用 inputs 内的 pressure 与 FD4 manifest；服务端压力梯度还依赖自己的 catalog。选择整套来源，不能以重命名替换算法。
4. 目标机安装环境，设置本机 YAML 的 state/run/result/token 路径。`state_root` 指向迁入数据；run_root 可以是新空目录。Mac 24 GB 用 memmap。路径相对于命令的工作目录解析，统一从项目根目录执行。
5. 使用目标机解释器校验（以下 Windows 示例）：

```powershell
$Python = '.\.venv\Scripts\python.exe'
$Config = 'configs/pipeline.yaml'
& $Python -m jhtdb_pipeline doctor --time-index 1 --config $Config
& $Python -m jhtdb_pipeline validate-input --time-index 1 --config $Config
# 仅当迁移的是服务端梯度时：
& $Python -m jhtdb_pipeline validate-input --field pressure_gradient --time-index 1 --config $Config
# 本地 FD4：校验来源并复用/修复各块，无服务端梯度下载。
& $Python -m jhtdb_pipeline.pressure_local --stage gradient --time-index 1 --config $Config
```

如果需要 SQLite 一致性备份，在已停止写入的源机执行（调整路径；目标文件应为新文件）：

```bash
python3 - <<'PY'
import sqlite3
from pathlib import Path
source = Path('.local/state/catalog.sqlite').resolve()
out = Path('/tmp/catalog.transfer.sqlite')
if out.exists():
    raise SystemExit('Backup destination already exists')
a = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
b = sqlite3.connect(out)
try:
    a.backup(b)
finally:
    b.close(); a.close()
PY
```

另一个 field 的 catalog 同样独立备份。不要覆盖含其他时间帧的目标数据库；这里的流程迁入空目录，不提供跨库合并。

## 正式结果迁移与路径陷阱

`shared_refs.json` 中存在绝对路径；manifest、QA、子项目 config_used 的路径也可能包含旧盘符。当前没有就地重写整个 provenance/hash 链的受支持工具。**改 YAML 只改变后续路径选择，不能修复现有 shared_refs。**

相同 OS、相同绝对布局可完整复制 state 与 result 后用 `open_complete_result` 验证；跨 OS 或不同布局，推荐迁入已验证速度，再按 [版本更新](data_versions.md) 的 v7→v7 或 v6→v7 工具重建到独立结果目录。原结果保留供对照。不要手改 COMPLETE 或 manifest hash 来绕过检查。

```python
from pathlib import Path
from jhtdb_pipeline.store import open_complete_result
root = open_complete_result(Path('/目标机/results/RESULT_ID'))
print({name: (root[name].shape, str(root[name].dtype)) for name in root})
```

QPower 输入迁移后用本机配置重新 preflight。历史 CSV/图片可直接查看，历史 config_used 保留旧源路径作为 provenance；若需继续后处理，先建立新的本机运行配置并重新运行分析，不把历史路径的可用性当作结果有效性的证明。

## 断点与故障

重新运行相同 `cache` 会校验并复用 tile；`process-batch` 只复用符合当前参数和 schema 的完整结果，未完成 FFT 缓存可能重建。`process-full` 后要显式 `finalize-result`；`single-frame` 与 `process-batch` 会负责正式提交。`.staging` 不是结果，GUI 看不到是正常行为。

锁冲突先确认运行中的进程，不能通过删除 lock 文件绕开活跃写入。磁盘不足应改工作区或释放无用临时数据，并重新运行 plan；不要降低科学域大小假装完成全域。未做真实跨系统大数据迁移验证，目标机应按以上步骤校验。
