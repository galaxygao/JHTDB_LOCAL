# Compact 进程与接续记录

## 当前状态

本次行为保持型 compact 已完成（2026-10-03，共四轮），尚未提交或推送，没有半完成的代码块或正在进行的精简任务。基线提交：`5900e4ae5d6f79f0ec06b88e5fde78555c4c9220`。科学公式、浮点运算顺序、数据 schema、CLI 参数/输出/退出码和子项目目录归属保持不变。保留现有生产入口与兼容导入。另修复真实 Streamlit 启动路径下的同名模块遮蔽问题。

完成标准是合并具有相同契约的重复实现并验证现有输出，同时完成剩余候选的审查与保留决定；不是用压行、删除功能或改变模块路径追求最小文件数。累计生产代码减少 **354 行**，全部 Python 减少 **273 行**，文件数 **83 → 78**；全套 **152 项测试通过**。文件减少来自测试整合，生产/工具仍为 50 个文件。

## 基线

仅统计 Git 跟踪的 Python 文件；`tests` 路径单独计数，生成 Markdown、环境、科学输出不计入代码缩减。

| 类别 | 文件 | 总行数 | 非空行 |
|---|---:|---:|---:|
| 生产/工具 | 50 | 12560 | 11443 |
| 测试 | 33 | 3231 | 2837 |

## 第一轮结果

| 类别 | 文件（前 → 后） | 总行数（前 → 后） | 非空行（前 → 后） |
|---|---:|---:|---:|
| 生产/工具 | 50 → 50 | 12560 → 12374 | 11443 → 11262 |
| 测试 | 33 → 29 | 3231 → 3262 | 2837 → 2884 |
| 合计 | 83 → 79 | 15791 → 15636 | 14280 → 14146 |

生产代码净减少 186 行；包含新增回归用例的全部 Python 代码净减少 155 行。生产文件数保持 50，减少的四个文件来自测试合并，并非删除生产接口。计数不包括文档和科学输出。

## 第一轮计划

- [x] 合并 CLI 的 sigma 选择、单尺度路径命令和 QA 报告分派，保留输出形状和失败行为。
- [x] 合并三种 QA 报告的 hash/version/COMPLETE 校验链到已有 store 模块。
- [x] 统一分块计数和相同的符号 regime 分区；阈值 uncertain 判据保持独立。
- [x] 合并同功能小型测试文件，保留现有用例。
- [x] 对照修改前后的 24 个 CLI 场景与四类完整统计 JSON；运行全套回归及入口检查。
- [x] 更新生成文档、最终计数与后续待办。

## 第一轮实现定位

| 位置 | 已完成改动 |
|---|---|
| `src/jhtdb_pipeline/cli.py` | `_selected_sigmas` 统一尺度选择，`_input_status` 统一 catalog 查询，`_print_json` 统一 JSON 输出；同类命令使用局部 operation 映射，保留测试 monkeypatch 和原执行顺序 |
| `src/jhtdb_pipeline/store.py` | `chunk_count` 与 `load_chained_report` 替代多个重复实现；仍检查 report/manifest/Zarr attrs/COMPLETE 的完整 hash 链和 HTML 存在性 |
| `src/jhtdb_pipeline/physics.py` | `sign_regime_masks` 供 Cq 和 regime_pi 复用；磁盘 regime 的 uncertain 阈值判据独立保留 |
| `src/jhtdb_pipeline/processing.py` | 复用 `spatial_slices`，保持原 z/y/x chunk 遍历顺序；复用 chunk 计数 |
| `cq.py`、`sbar_qa.py`、`weak_asymmetry.py` | 各自计算、报告版本、格式和阈值仍独立，仅复用完整性校验与计数 |
| `regime_pi/statistics.py` | 复用符号分区与计数，保留全部统计字段和输出位置 |
| `src/jhtdb_pipeline/dashboard.py` | Streamlit 脚本执行时优先查找项目根目录包，避免同名 `regime_pi.py` 遮住子项目包 |

前一轮临时采用的按文件路径动态加载已由启动路径修复取代。子项目实现仍在原目录，核心兼容导入保留。此拆分在基线提交中已存在，报错不能归因为本轮新建拆分。

测试文件合并：

- `tests/test_coordinates.py` → `tests/test_planning.py`。
- `tests/test_gui_full_fields.py` → `tests/test_dashboard.py`。
- `block_statistics/tests/test_block_statistics_plot.py` 和 `test_block_regime_pair_asymmetry.py` → `test_block_statistics.py`。

以上四个旧文件删除，全部测试定义迁入目标文件，可从基线 Git 提交恢复原布局。

## 第一轮验证证据

```bash
.venv-mac/bin/python -m pytest tests block_statistics/tests qpower_analysis/tests pi_pdf/tests pi_slices/tests scatter/tests regime_pi/tests flux_plateau/tests -q
.venv-mac/bin/python scripts/update_docs.py
.venv-mac/bin/python scripts/update_docs.py --check
```

- 基线 140 项测试通过；最终 145 项通过，2 条已有 xarray/NumPy 弃用 warning。
- AST 对照确认所有原有 test 定义仍存在。新增 GUI 脚本路径检查 2 个参数用例、QA 校验链检查 3 个参数用例。
- GUI：独立新进程将脚本目录置于 sys.path 第一位，分别验证根入口及核心 Streamlit 脚本；小域 AppTest 遍历全部页面及首尾切片。
- 行为对照：24 个 CLI 场景的 stdout/stderr/退出码/调用参数和 Cq、S-bar、weak-asymmetry、regime_pi 四类完整 JSON，与修改前 snapshot 逐字节一致。临时 snapshot 位于 `/tmp/jhu-compact-before.json`，不作为长期依赖；后续对照应从起点 Git 提交重新生成基线。
- 保留原有 memory/memmap 两路径全字段数值对照、失败清理、schema 和科学 closure 测试。
- 文档索引更新并通过一致性/本地链接检查；所有生产入口的 `--help` 通过。
- 未执行在线下载、真实 1024³ 重算或 Windows/Linux 实机测试。实际完整域内存峰值与图像效果仍须按项目手册验证。

## 第二轮：字段操作与 slab 遍历

起点为第一轮完成后的工作树；没有新增 Git 提交。不要用最初基线提交恢复第二轮起点，否则会丢失第一轮改动。改动仅涉及 `processing.py`、`physics.py` 和文档，不删除生产或测试入口。

- [x] 修改前记录四种完整处理组合的数值、格式和报告基线。
- [x] 引入 `physics.spatial_slabs`，统一 z slab 的首尾边界，供拷贝、累加、统计、清零、乘积加减和 y/x 轴 FFT 分片复用。
- [x] `_accumulate_zarr_product` 复用现有 `ProductView` 与 `_accumulate_zarr`。源必须同 shape；乘积仍在读取 chunk 时计算，不创建全域乘积数组。
- [x] 原始散度三个对角梯度的累加复用 `_accumulate_full`，保持 float32 和分量顺序。
- [x] 保留 memmap 原位 `+=` / `-=`、页面释放顺序、有限值检查和写入读回检查。
- [x] 完整字段及报告对照、全套回归、生成文档与链接检查通过。

不同存储方式仍分别按 chunk 或 slab 遍历；未将它们合成一个带模式参数的大函数。资源预检、QA 输出字典及失败清理逻辑未改动。

| 类别 | 文件（轮前 → 轮后） | 总行数（轮前 → 轮后） | 非空行（轮前 → 轮后） |
|---|---:|---:|---:|
| 生产/工具 | 50 → 50 | 12374 → 12350 | 11262 → 11236 |
| 测试 | 29 → 29 | 3262 → 3262 | 2884 → 2884 |
| 合计 | 79 → 79 | 15636 → 15612 | 14146 → 14120 |

本轮生产代码净减少 24 行、26 个非空行。累计两轮生产代码净减少 **210 行**；含新增回归用例的全部 Python 代码净减少 **179 行**，文件从 83 降为 79。没有新增测试文件或删除测试用例。

验证：

- 使用 `tests/test_processing.py::fixture` 的完整 16³ 合成域，分别运行 Gaussian / smooth-sharp × memory / memmap，sigma 为 `(1.0, 2.0)`，slab 宽度为 3，覆盖末尾不足一个 slab 的情况。
- 四组合 × 二尺度 × 九逻辑字段，共 **72 个字段**的 SHA256、bytes、min/max、shape、dtype、chunks 与修改前一致；九场含共享 velocity / gradient。每个结果的完整 `qa.json` 和重新计算的 Cq、S-bar、weak-asymmetry、regime_pi 报告也一致。各组合分别对照本身的基线，不要求不同 FFT 路径的输出完全相同。
- 比较序列化后的整体 JSON，修改前后逐字节相同；snapshot SHA256 为 `662a50f492827445812936bda6224db538b7a8cede9ab1856ee7f27459453345`。
- 全套回归 **145 passed，2 条已有 xarray/NumPy 弃用 warning**；未另加只复述 helper 实现的测试。已有 FFT 非整除 slab、memmap 清理、完整域处理、GUI、QA 和各子项目测试继续通过。
- `scripts/update_docs.py --check`：50 个生产/工具源码、9 个生成参考及本地链接检查通过；`git diff --check` 通过。新 helper 的职责同时补入[架构说明](architecture.md)。

本轮临时对照工具 `/tmp/jhu_compact_round2_compare.py`，snapshot 为 `/tmp/jhu-compact-round2-before.json` 与 `/tmp/jhu-compact-round2-after.json`，可用 `cmp` 复核。临时文件可能被系统清理，不作为生产依赖；下一轮必须从当时工作树重新建立基线。第二轮起点源码 SHA256：

```text
processing.py 0b3a8dac439eaee6085a619f29d30129e69ee5c8aa388f075adf829440f1ade3
physics.py    5e908600b619ca391211997c1fe57d09c63c4fdc96cf9b3e18dba7ba3016579b
```

本轮未测真实 1024³ 域的峰值内存或运行时，也未运行在线请求。新增复用保持切片读写，没有新增全域数组；小域结果一致不能替代完整域资源验证。

## 第三轮：QA 摘要与报告元数据更新

起点为第二轮完成后的工作树，无新增 Git 提交。本轮涉及主库 `processing.py`、`store.py`、`validation.py`、`cq.py`、`sbar_qa.py`、`weak_asymmetry.py`，以及现有测试和文档；子项目代码、科学结果目录及生产入口未移动。

- [x] 修改前记录初次提交、三种报告重算和严格阈值 QA 失败的持久化内容。
- [x] `store.report_summary` 统一 passed/scope/report_version/report_hash 四个共同摘要字段，附加指标由调用方传入。
- [x] `store.report_metadata` 统一 manifest 与 attrs 的带前缀三字段，保留 passed 的原值。
- [x] `weak_asymmetry_summary` 统一三处重复的全局比值与 closure 摘要定义。
- [x] `validation.update_report_metadata` 统一重算后的 manifest → attrs → COMPLETE 更新，保留已有 JSON 原子写入和调用方锁。
- [x] 对照完整字段、报告与存储元数据，验证写入中断及重试，更新生成索引和架构说明。

没有合并不同 QA 的科学计算。正式结果初次 finalization 的 schema 校验、字段 hash、attrs 读取默认值和 bool 转换仍由原函数执行。公共写入函数不自行获取锁，调用方继续使用原 `qa-metadata-*` 锁；写报告和 `qa.json` 的顺序不变，也没有新增跨文件事务。

| 类别 | 文件（轮前 → 轮后） | 总行数（轮前 → 轮后） | 非空行（轮前 → 轮后） |
|---|---:|---:|---:|
| 生产/工具 | 50 → 50 | 12350 → 12304 | 11236 → 11182 |
| 测试 | 29 → 29 | 3262 → 3307 | 2884 → 2922 |
| 合计 | 79 → 79 | 15612 → 15611 | 14120 → 14104 |

本轮生产代码净减少 **46 行**、54 个非空行；新增写入中断测试增加 45 行，因此包含测试的总行数净减少 1 行。累计三轮生产代码净减少 **256 行**，全部 Python 净减少 **180 行**，文件仍为 79 个；没有删测试来缩减计数。

验证：

- 同第二轮的四处理组合、两个 sigma、16³ 完整域和 slab=3；每个结果依次记录初次生成、Cq 重算、weak-asymmetry 重算、S-bar 重算、将 identity 阈值改为 `1e-12` 后 S-bar 不通过这五个阶段，共 **40 个阶段 snapshot**。
- **72 个完整字段**的 hash/bytes/min/max/shape/dtype/chunks 在各阶段与轮前一致。逐字节对照 `qa.json`、`manifest.json`、`COMPLETE`、三份报告 JSON、`divergence.json`、结果 `.zattrs`；`shared_refs.json` 仅将临时 fixture 根路径替换为固定占位符后比较，其余内容不归一化。重算接口返回的完整报告也一致。
- 整体 snapshot SHA256：`4dbc18cbc2fd6ef85a347c5cf9b310120f9238948b83c1c5a34b4e7cf4110e5f`。临时工具 `/tmp/jhu_compact_round3_compare.py`，输出 `/tmp/jhu-compact-round3-before.json` 和 `/tmp/jhu-compact-round3-after.json`；`cmp` 通过。下一轮需从当时工作树重新建立基线，不依赖临时文件长期存在。
- 在现有 `tests/test_catalog_store.py` 增加 3 个参数用例，分别模拟 manifest、attrs、COMPLETE 写入失败：旧 COMPLETE 不被提前更新，reader 拒绝新报告与旧链组合，重试后科学 QA 不通过的报告也能被正确读取，其他报告 hash 和字段信息仍保留。
- 全套回归 **148 passed，2 条已有 xarray/NumPy 弃用 warning**；50 个源码、9 个生成参考和本地文档链接检查通过；`git diff --check` 通过。

第三轮起点源码 SHA256（工作树指纹，不是 Git 提交）：

```text
processing.py      41916ce41380663f41c59edfce0c4f7522eecad9b867a5b27812f29fd3a14947
store.py           a7c25e28c4fcb31d8f8fa2b3914a3b1f57a7ee34d7e9b42b2e76fbcbf5b07efd
validation.py      2fa4a251807e302b232d7596a257e557e260dd40621359bf507167dbefc0ed81
cq.py              5c1736c6454488dcc4be38d020de1705dd3c51b5c5c7c9014af7a43753f4d348
sbar_qa.py         bc30a8784180783e6cd1fbc13f2a66033867d4206f13daca26dcbbb106b04231
weak_asymmetry.py  0af40575f6a1234574ad893025c3ca8f1f67e7bee03f37b12151d42c6a830059
```

未执行在线请求或真实 1024³ 重算。HTML 渲染函数没有修改；本轮没有建立图片像素对照。共享写入函数沿用已有的单文件原子写入，不能将小域故障注入测试理解为所有系统崩溃情形均已验证。

## 第四轮：完成剩余重复实现与全项目审查

起点为第三轮完成后的工作树，仍未新增 Git 提交。修改前将所有跟踪的 Python 源码与测试复制到临时 `/tmp/jhu-compact-final-baseline`，用于函数与测试定义对照；临时目录不是长期恢复机制。

- [x] 核心滤波分派复用共同参数调用；smooth-sharp 的磁盘频谱分支及释放顺序仍独立。
- [x] `store.array_metadata` 统一共享梯度与单尺度结果字段的流式 hash、bytes、min/max、shape、dtype、chunks；正式字段的预期 shape 从原 rank 推导，检查与错误消息保留。
- [x] GUI 使用 `_extract_spatial_slice` 统一三种字段的 z/y/x 切片，保留公开函数；`_continuous_pair` 统一四处双图布局，保留次序、标题、色限和缩放。
- [x] flux_plateau 使用 `_flux_figure` 统一两个图的公共绘制，保留 `make_figure` / `make_log_k_figure` 入口，各自排序坐标、hover 字段、坐标类型和标题仍独立。
- [x] QPower 的 tails/ranges/contributions 复用 `validated_fields` 的只读输入校验，保留各调用方 key 默认值和错误消息；angle 的 assert 校验仍保留其原契约。
- [x] QPower 合并 alpha/beta 事件输出循环，保持 CSV 行顺序和输出文件名；展开主流程的多语句控制、I/O 与返回路径，提高可读性，不改变科学算式。
- [x] 将 `qpower_analysis/tests/test_conditional_ranges.py` 全部用例迁入 `test_conditional_tails.py`，删除重复导入与文件；包导入和直接脚本模式均验证。
- [x] 完成函数/测试定义检查、所有生产源码的重复函数与未引用私有函数扫描、入口检查、数值和图形对照、完整回归及文档更新。

| 类别 | 文件（轮前 → 轮后） | 总行数（轮前 → 轮后） | 非空行（轮前 → 轮后） |
|---|---:|---:|---:|
| 生产/工具 | 50 → 50 | 12304 → 12206 | 11182 → 11074 |
| 测试 | 29 → 28 | 3307 → 3312 | 2922 → 2927 |
| 合计 | 79 → 78 | 15611 → 15518 | 14104 → 14001 |

本轮生产代码减少 **98 行**；测试整合后又增加 4 个参数用例，测试净增加 5 行，因此全部 Python 净减少 **93 行**。相对于最初基线，生产减少 354 行、369 个非空行；全部 Python 减少 273 行、279 个非空行。所有原测试定义保留，没有删除生产函数或类的顶层定义。

最终验证：

- 主流水线四处理组合、两个尺度、72 个完整字段，以及初次提交和报告重算/QA 失败的 40 个阶段，与第三轮基线逐字节一致。对照输出 `/tmp/jhu-compact-final-pipeline.json`，SHA256 仍为 `4dbc18cbc2fd6ef85a347c5cf9b310120f9238948b83c1c5a34b4e7cf4110e5f`。
- GUI AppTest 覆盖全部 7 页、x/y/z 法向、首尾切片和梯度 linear/SymLog，共 **39 个视图**。完整 Plotly spec、指标和错误提示与轮前一致；此处是图形配置对照，未将它称为浏览器截图像素对照。
- flux_plateau 两种完整 Plotly JSON 一致，包含 Gaussian、smooth-sharp 和论文参考数据的分组、排序、hover 与平台线。
- QPower 在固定随机种子的完整 12³ 域执行主分析、contributions、tails、95% ranges、50% cached ranges、angles；对照 **26 个 CSV/JSON/PNG/NPZ 输出**和 **8 个 HTML 的 Plotly 图形**。PNG 文件 SHA256 一致，NPZ 数组字节一致；CSV/JSON 仅归一化临时 fixture 根路径，时钟固定。PDF 继续生成，但没有将其时间戳敏感的文件字节纳入相等判据。
- 四种 filter/cache 配置的资源估算完整 JSON 一致。预检公式和错误消息未修改。
- 合并的条件范围测试原定义全部存在；新增 4 个参数用例检查 gradient cache 的 status、帧号、物理时间及 shape 不匹配时拒绝读取。
- 最终全套 **152 passed，2 条已有 xarray/NumPy 弃用 warning**；**23 个直接脚本/模块 CLI help** 检查通过；50 个源码、9 个生成参考与本地链接一致；`git diff --check` 通过。

额外对照工具 `/tmp/jhu_compact_final_compare.py`，snapshot 为 `/tmp/jhu-compact-final-before.json` 与 `/tmp/jhu-compact-final-after.json`；整体 SHA256 为 `cfef0cfc6b9656904fc9bf1af56a348d878696a60914105b32af90fc52c8c8a0`，`cmp` 通过。所有这些 `/tmp` 文件可被清理，下一次新修改应从当时工作树重新生成基线。科学生产输出、在线下载、真实 1024³ 重算和其他操作系统实机测试不在本次验证范围。

## 最终审查与保留决定

以下是已审查后保留的实现，不是未完成的 compact 待办。

| 范围 | 保留理由 |
|---|---|
| 单尺度、多尺度、共享梯度及 scratch 资源预检 | 同盘用最大 reserve，异盘分别预留；单尺度额外 FFT 临时空间与 batch 的 12 频谱 cache 不同。合并会隐藏不同空间公式，公共 helper 没有明确净收益 |
| pressure_local 下载 / FD4 / follow 状态机 | 下载锁、梯度锁、周期两层 halo、依赖 checksum、恢复和停止事件各有独立契约；保留，避免把不同职责耦合 |
| QPower 初始全数组计算与后处理分块计算 | 不同 dtype、einsum、归一化与严格阈值运算顺序必须保留，不能仅因表达式相似就统一；angles 的 assert 与其他脚本的 ValueError 也不混用 |
| PDF、scatter、切片和 Gaussian 判据的统计/绘图函数 | 不同归一化、分位数、分箱和 subplot 契约保持独立；不是重复科学功能。共享前提明确的 flux 两种图已合并 |
| 配置、鉴权、catalog、下载、验证、部署与维护入口 | 独立职责和 CLI 路径已文档化。静态扫描没有找到可以直接删除的未引用私有顶层函数；不因文件小就破坏模块接口 |
| 核心 regime_pi / strain 兼容导出，根 dashboard 与各包 `__init__.py` | 现有导入和 Streamlit 路径依赖这些入口；setuptools 使用 `namespaces=false`，空包入口也不能直接删除 |
| 子项目代码与科学输出目录 | 各自保留 README、源码、测试及 output；不为减少文件数把子项目实现搬回主库，也不删历史科学结果 |

## 接续方法

本次任务已结束。以后明确提出新一轮精简时，先阅读本文件、[架构](architecture.md)和[维护说明](maintenance.md)，再检查 `git status`，建立新的行为基线。每轮记录起点提交、改动范围、前后计数、测试命令/结果、未验证范围。缩减不能靠删测试、减少科学数据或省略异常检查；不要重写历史科学结果。已完成项只在验证通过后勾选。
