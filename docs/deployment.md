# Windows / macOS / Linux：持久部署与压力流程

首次部署按 [根 README 的完整教程](../README.md#first-deployment) 顺序执行：
**安装环境 → 保存 token 文件 → 确认路径 → 本地检查**。两个 pipeline 共用环境；
本页补充 deploy 的路径规则、阶段边界和续跑方式。系统需要 Python 3.9+，安装时需要联网。

## 一键部署环境，首次执行

从项目根目录选择对应系统的命令。此阶段无需已有 token 内容，只记录文件路径；
不会下载科学数据或执行 pipeline。安装成功后按 [token 文件步骤](../README.md#token-file)
隐藏录入已有的 JHTDB token。

Windows / PowerShell：

```powershell
$DataRoot = '.local'
$TokenPath = Join-Path $HOME '.secrets\jhtdb_token'
py -3 deploy.py --stage setup --data-root $DataRoot --token-file $TokenPath
```

macOS：

```bash
python3 deploy.py --stage setup --data-root .local --token-file "$HOME/.secrets/jhtdb_token"
```

Linux / Pitt CRC：

```bash
cd /ix/lfang/xig134/JHTDB_LOCAL
python3 deploy.py --stage setup --data-root /ix/lfang/persistent --token-file "$HOME/.secrets/jhtdb_token"
```

`setup` 创建或复用环境，安装 `.[dev]` 并执行 `pip check`，最后生成本机 YAML。
**省略 `--stage` 默认运行 `all`，包含下载和计算，不能用作仅安装环境的命令。**

## 永久保存什么，下次如何复用

| 内容 | 实际位置 / 行为 |
|---|---|
| Windows 环境 | 项目 `.venv-windows/`；旧 PowerShell 包装脚本使用另一目录 `.venv/` |
| macOS 环境 | 项目 `.venv-mac/` |
| Linux 环境 | 项目 `.venv-linux/`；已有持久目录链接会被复用 |
| token 文件 | 本文显式指定用户主目录的 `.secrets/jhtdb_token`，安装命令不写入内容 |
| 本机配置 | `<data-root>/pipeline.yaml`，每次调用 deploy 都重新生成 |
| 输入与状态 | `<data-root>/state/`，含 inputs、catalog、manifest、QA 和锁 |
| 主工作区 / 主结果 | 生成 YAML 中分别为 `<data-root>/runs/`、`<data-root>/results/` |
| QPower 配置 | `qpower` / `all` 阶段生成 `<data-root>/qpower.json` |
| QPower 输出 | 项目 `qpower_analysis/output/<运行时间>/`，不随 `--data-root` 移动 |
| 部署锁 | `<data-root>/deploy.lock` |
| 后台日志 / PID | 使用 `--background` 时生成 `<data-root>/deploy.log` 和 `deploy.pid` |

关闭终端、重启电脑或结束 Slurm job 不会主动删除环境和 token 文件。
下次进入同一个项目目录，直接调用对应环境的 Python 即可；激活只影响当前终端。
使用 deploy 续跑时加 `--skip-install`，避免重复安装，继续传原来的数据与 token 路径。
更新依赖时重做 `--stage setup`，会在原环境中安装，不另建环境。

`--data-root` 默认为项目 `.local/`，不改变环境和 token 位置。可改成外置盘或持久盘的
绝对路径，例如 macOS 的 `/Volumes/Data/JHTDB`、Windows 的 `D:\JHTDB`。
安装和后续每次调用必须使用同一根目录，才能复用同一套缓存。
editable 安装依赖项目源码，移动项目或更换基础 Python 后应重新部署；环境不能跨系统复制。

生成 YAML 的来源固定为 `configs/pipeline.yaml`，只替换 platform 与 token 路径，
保留该模板的 RAM FFT、线程等参数。它不读取 `configs/pipeline.macos.yaml` 或 CRC 配置。
需要持久保存自定义参数时另存本机 YAML，用现有 CLI 的 `--config` 运行；
deploy 没有接受该独立 YAML 的参数。macOS 主计算和 CRC 两条 pipeline 的命令见
[根 README](../README.md)、[macOS 资源方案](macos_main_pipeline_run.md)、
[CRC 资源方案](linux_crc_run.md)。CRC 专用配置将工作文件放在 `/vast`，
直接调用 deploy 则仍使用 `<data-root>/runs`，两者路径不同。

Git 不保存环境、token 和 `.local` 运行目录；`output/` 运行目录默认被忽略，
其中 Markdown 报告按仓库规则可被跟踪。若使用云盘同步，还需在客户端排除环境、token
和活动数据库；`.gitignore` 不控制云盘。依赖声明锁定范围，不保证不同时间安装的版本完全一致。

## Token 路径与读取优先级

录入命令统一放在 [根 README](../README.md#token-file)，避免不同文档使用不同位置。
文件为一行 token，macOS/Linux 权限必须为 `600` 或更严格，Windows 使用用户自己的私有目录。
安装只将路径写进 YAML，不会生成 token 内容，也不是 SSH 认证配置。

deploy 的文件路径选择：指定 `--token-file` 时使用该路径；未指定时，项目
`.secrets/jhtdb_token` 若存在则使用它，否则选择用户主目录 `.secrets/jhtdb_token`。
随后 CLI 仍优先读取非空环境变量 `JHTDB_TOKEN`，再读取所选文件。
显式指定了不存在的文件时不会自动回退到其他文件。
`auth status` 仅报告来源，`doctor` 是本地环境/路径检查，在线 `smoke` 才会请求服务。

## 分阶段执行：环境已经安装以后

| `--stage` | 行为 | 下载科学数据 | 全域计算 |
|---|---|---|---|
| `setup` | 安装依赖、生成路径 YAML | 否 | 否 |
| `check` | 生成 YAML、doctor | 否 | 否 |
| `velocity` | doctor、速度 smoke、速度下载与校验 | 是 | 否 |
| `download` | doctor、速度 smoke、速度与标量压力下载/校验 | 是 | 否 |
| `qpower` | 从已有压力计算/复用 FD4 梯度，生成 JSON、preflight、QPower | 否 | 是 |
| `all`（默认） | 检查、速度与压力下载、FD4、QPower | 是 | 是 |

所有阶段都不运行主 pipeline 的多 sigma 滤波与能量传输计算。
`download` 不求压力梯度；`all` 的压力下载与本地 FD4 会重叠，最终验证通过后才进入 QPower。
默认第 1 帧（t=0），`--time-index 7` 可换帧；stage `qpower` 要求已有完整速度和压力。

macOS 示例：以下是按需要选择的命令，并非首次部署时全部执行。
更改过数据目录时，将每条命令的 `.local` 改为同一个目录。

```bash
# 本地检查
python3 deploy.py --stage check --skip-install --data-root .local --token-file "$HOME/.secrets/jhtdb_token"

# 只下载速度
python3 deploy.py --stage velocity --skip-install --data-root .local --token-file "$HOME/.secrets/jhtdb_token"

# 下载速度和标量压力，不计算梯度或 QPower
python3 deploy.py --stage download --skip-install --data-root .local --token-file "$HOME/.secrets/jhtdb_token"

# 已有速度和压力，计算/复用 FD4 梯度并执行 QPower
python3 deploy.py --stage qpower --skip-install --data-root .local --token-file "$HOME/.secrets/jhtdb_token"

# 检查 → 下载 → FD4 → QPower，要求内存足够
python3 deploy.py --stage all --skip-install --data-root .local --token-file "$HOME/.secrets/jhtdb_token"
```

Windows / PowerShell 示例：

```powershell
$DataRoot = '.local'
$TokenPath = Join-Path $HOME '.secrets\jhtdb_token'
py -3 deploy.py --stage download --skip-install --data-root $DataRoot --token-file $TokenPath
```

按需要将 `download` 改为表中其他阶段，检查退出码，失败后停止。
通用 Linux 可使用相同的 `python3 deploy.py` 参数；**Pitt CRC 的下载和计算应按
[专用资源方案](linux_crc_run.md) 显式传入 Linux 配置**，保持线程、内存与 `/vast` 路径规划。

QPower 使用原有全数组实现，float32 速度和梯度加载本身约 24 GiB，另需统计及可视化内存。
24 GB Mac 应只下载，再按 [迁移手册](system_migration.md) 将完整 state 迁移到内存足够的机器。
完整速度、压力、FD4 梯度未压缩分别约 12、4、12 GiB，合计 28 GiB，另需磁盘安全余量。

## 后台运行与续跑

token 文件需预先录入。已有环境时，macOS 示例：

```bash
python3 deploy.py --stage download --skip-install --data-root .local --token-file "$HOME/.secrets/jhtdb_token" --background
```

Windows 使用 `py -3` 并显式传相同的数据与 token 路径。后台标准输入关闭，不能交互录入 token。
日志写入 `<data-root>/deploy.log`，PID 写入 `<data-root>/deploy.pid`。
启动消息只表示进程创建；日志中的 `Completed stage: download` 才说明该阶段成功。
`setup` 成功时输出环境与本机配置路径，不打印 `Completed stage: setup`。
`--wait-lock` 可等待相同 data-root 的已有 deploy 结束，随后校验并复用缓存。
macOS 可用 `tail -f .local/deploy.log`，Windows 用 `Get-Content .local\deploy.log -Wait`。
后台运行不能延长 Slurm allocation 的 walltime，也不保证电脑休眠或关机后继续运行。
macOS 的 deploy 运行阶段使用 `caffeinate -i` 防止空闲睡眠。

轻量合成测试的维护命令见 [文档维护](maintenance.md)；首次部署不要求执行生产流程或完整测试集。

## 压力场与持久化压力梯度

当前入口不再请求服务端压力梯度。每帧在 `<data-root>/state/inputs/tNNNNNN/` 保存：

- `velocity_cache.zarr/`：已校验的速度缓存；
- `pressure_cache.zarr/`：原始压力，数组 `pressure[z,y,x]`；
- `pressure_gradient_fd4_cache.zarr/`：本地压力梯度，数组
  `pressure_gradient[component,z,y,x]`，分量依次为 x、y、z；
- `pressure_manifest.json` 和 `pressure_gradient_fd4_manifest.json`：校验和与来源信息。

旧的 `pressure_gradient_cache.zarr/` 属于服务端下载的部分数据，会保留，但新流程不用它。

使用公式 `(P[i-2]-8P[i-1]+8P[i+1]-P[i+2])/(12*h)`，`h=2π/1024`。
每个默认 `64³` 计算块读取两层 halo，按整个周期域取模，块边界和全域边界都用中心差分。
使用 float64 累加，保存 float32。中断后校验并复用已完成块；梯度来源绑定压力 manifest。
只有计算、写回校验全部通过后，梯度才标记为 `validated` 并交给 QPower。
QPower 使用显式保存的梯度，不再次执行 FFT 或其他求导。

只下载压力或只计算梯度（Windows 将解释器换为 `.venv-windows\Scripts\python.exe`）：

```bash
.venv-mac/bin/python -m jhtdb_pipeline.pressure_local --config .local/pipeline.yaml --time-index 1 --stage download
.venv-mac/bin/python -m jhtdb_pipeline.pressure_local --config .local/pipeline.yaml --time-index 1 --stage gradient --block-size 64
```

较小 `--block-size` 可降低差分内存开销；同一缓存的续算需保持块大小一致。
测试：`.venv-mac/bin/python -m pytest tests/test_pressure_local.py -q`。

## 下载与差分重叠执行

`deploy.py --stage all` 默认使用一个下载任务和一个本地差分工作线程。
只对压力块及其周期两层 halo 都已写回校验的区域计算梯度；周期边界处可能需要等待
网格另一端下载完成。梯度记录每块依赖的压力校验和，恢复时只复用来源一致且自身校验通过的块。
下载失败会停止同一进程的差分工作线程并保留中间结果。完整压力和全部梯度验证完成后才启动 QPower。

对已经启动的独立压力下载，可以在另一终端附加一个差分任务：

```bash
.venv-mac/bin/python -m jhtdb_pipeline.pressure_local --stage follow --config .local/pipeline.yaml --time-index 1
```

`follow` 不发送网络请求，和已有下载共享已校验的缓存；它独占该帧梯度写锁，
后续最终梯度阶段会等待此锁。下载数据连续 30 分钟无进展且尚未完成时，`follow` 报错退出，
保留部分梯度；可在恢复下载后重新执行。同一帧请只启动一个 `follow` 任务。

跨系统复制输入和结果前，阅读 [系统迁移](system_migration.md)。返回 [根 README](../README.md)。
