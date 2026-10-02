# Windows / macOS 共用的一键部署入口

运行环境要求：系统已安装 Python 3.9+，可以联网安装依赖，并已准备个人 JHTDB token。
下载与计算均调用现有代码；原 Windows 脚本和配置继续可用。

## 一键安装、下载并执行 QPower

在项目根目录执行，macOS：

```bash
python3 deploy.py
```

Windows PowerShell：

```powershell
py -3 deploy.py
```

同一入口自动创建本机虚拟环境、安装 `.[dev]`、检查依赖、从
`configs/pipeline.yaml` 生成本机路径配置，执行 doctor 和速度在线 smoke，
然后串行下载并校验第 1 帧（t=0）的完整 `1024³` 速度与标量压力场，
all 阶段同时对邻域已齐全的块计算并保存周期四阶中心差分压力梯度，最后执行 QPower。macOS 运行阶段使用 `caffeinate -i`。
不计算速度梯度。失败立即停止后续步骤。仅需下载时加 `--stage download`。

长时间运行可使用后台模式（Windows 同样将 `python3` 换为 `py -3`）：

```bash
python3 deploy.py --background
```

后台进程独立于终端，日志写入 `<data-root>/deploy.log`，PID 写入
`<data-root>/deploy.pid`。启动消息只表示进程已创建；日志中出现
`Completed stage: all` 才代表全流程成功。`--wait-lock` 可等待同一数据目录的
已有任务结束，随后复用经过校验的缓存。macOS 可用 `tail -f .local/deploy.log`
查看日志，Windows 可用 `Get-Content .local\deploy.log -Wait`。

## Token

依次支持环境变量 `JHTDB_TOKEN`、`--token-file` 指定文件、项目中的
`.secrets/jhtdb_token`、用户主目录中的 `.secrets/jhtdb_token`。
文件只有一行 token；macOS 文件权限应为 `600`。token 内容不会写入生成的配置。

```bash
python3 deploy.py --token-file /绝对路径/jhtdb_token
```

Windows 可以使用 `py -3 deploy.py --token-file C:\你的路径\jhtdb_token`。

## 共用代码，本机环境

Git 同步 `deploy.py`、依赖声明、源码和文档。以下内容由各机器独立生成，已被忽略：

| 本机内容 | 位置 |
|---|---|
| macOS 虚拟环境 | `.venv-mac/` |
| Windows 虚拟环境 | `.venv-windows/` |
| 原 Windows 虚拟环境 | `.venv/` |
| token | `.secrets/` 或用户主目录 |
| 本机配置、输入数据、日志 | `.local/` |

虚拟环境不可跨系统复制。两个系统安装同一 `pyproject.toml` 声明的依赖范围，
各自获取适配本机的包；不保证不同安装时间解析出的版本完全一致。
若工作目录还受云盘同步，请另外在云盘客户端排除上述目录；`.gitignore` 只控制 Git。

可将数据放到外置盘：

```bash
python3 deploy.py --data-root /Volumes/Data/JHTDB
```

再次运行必须使用相同 `--data-root`；默认数据目录为项目 `.local/`。
完整速度、压力、压力梯度未压缩分别约 12、4、12 GiB，合计 28 GiB；
写入前还要求保留配置中的 24 GiB 空间余量。

## 分阶段、续传与 QPower

以下命令在 Windows 上将 `python3` 换为 `py -3`：

```bash
# 只创建环境和本机配置
python3 deploy.py --stage setup

# 检查环境、路径和 token 是否配置；不请求科学数据
python3 deploy.py --stage check --skip-install

# 基础输入流程：只下载速度，不需要压力梯度
python3 deploy.py --stage velocity --skip-install

# 复用环境并继续下载速度和标量压力；download 阶段不计算梯度
python3 deploy.py --stage download --skip-install

# 指定另一帧
python3 deploy.py --stage download --time-index 7 --skip-install

# 用已下载的压力计算/复用本地 FD4 梯度，再执行 QPower
python3 deploy.py --stage qpower --skip-install

# 环境配置 → 速度与压力下载/校验 → 保存 FD4 梯度 → QPower
python3 deploy.py --stage all
```

`qpower` 使用现有全数组实现，不会改成子域或分块算法；输入加载本身约 24 GiB，
另需统计和可视化内存，因此 24 GiB RAM 的 Mac 不适合运行完整域 QPower。
可在 Mac 完成下载后，将数据目录复制到有足够内存的 Windows 机器，通过
`--data-root` 指向该目录并运行 `--stage qpower`，入口会重新生成本机路径配置。
QPower 输出在项目的 `qpower_analysis/output/<运行时间>/`，不计算速度梯度。
该输出目录沿用项目已有结果管理方式，不属于 `.local/` 的忽略范围。

验证部署所调用的现有功能：

```bash
.venv-mac/bin/python -m pytest tests/test_deploy.py tests/test_pressure_gradient.py qpower_analysis/tests -q
```

Windows 使用 `.venv-windows\Scripts\python.exe -m pytest` 和相同测试路径。

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
