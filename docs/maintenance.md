# 文档和目录维护

根 README 管项目功能、平台端到端流程和导航；docs 管共用实现/配置/迁移/两版数据格式；子项目 README 管本项目公式、输入输出和运行。每个子项目的 scripts、tests、output、缓存应放在本目录内；共享正式输入/结果及 CLI/GUI 接口归核心。生成结果中的 provenance 不为了修复展示链接而重写。

## 更新文档

```bash
.venv-mac/bin/python scripts/update_docs.py
.venv-mac/bin/python scripts/update_docs.py --check
```

生成器用 Python AST 读取项目 Python 源码，生成核心及每个子项目的逐函数参考，以及全部 argparse 参数源码参考；不导入科学模块，不下载数据，不读取 token 或大型输出。`--check` 检查生成文档是否落后以及文档间本地链接是否存在。历史输出报告中的旧外部路径不纳入维护导航。

索引不能代替人工说明。改代码后同步修改公式、参数解释、系统步骤、数据版本表，再生成索引。只保留最近两版主结果 schema 的人工格式说明与更新工具。输入/报告的独立版本不属于主结果的两版窗口。

## 验证

```bash
.venv-mac/bin/python -m pytest tests block_statistics/tests qpower_analysis/tests pi_pdf/tests pi_slices/tests scatter/tests regime_pi/tests flux_plateau/tests -q
```

Windows 用 `.venv\Scripts\python.exe` 或 deploy 创建的 `.venv-windows\Scripts\python.exe`，Linux 用 `.venv-linux/bin/python`。这些合成测试不需要真实 token。shell/PowerShell 脚本的参数见 [scripts README](../scripts/README.md)。网络 smoke、完整域资源和目标 OS 实测另行记录。

## 本次目录迁移

| 原位置 | 当前位置 |
|---|---|
| 根 README_DEPLOY.md | [deployment.md](deployment.md) |
| 根 3D_QPOWER_ANALYSIS_TASK.md | [QPower TASK](../qpower_analysis/TASK.md) |
| scripts/download_then_qpower.py | qpower_analysis/scripts/download_then_qpower.py |
| scripts/quickstart_qpower_subset.py | qpower_analysis/scripts/quickstart_qpower_subset.py |
| outputs/qpower_jobs、qpower_subset | qpower_analysis/output 下同名目录 |
| tests 中各分析项目测试 | 对应子项目 tests/ |

历史 output JSON 和日志保留原始路径作为来源记录；新的默认 QPower 输出统一为 qpower_analysis/output。用户自定义输出路径仍有效。不要在 tests 搬迁时恢复用户已删除的历史结果。

## 本次验证记录（2026-10-02）

- macOS 现有 Python 3.13 环境：140 项合成测试通过；修复独立脚本导入后相关 39 项再次通过。两条 warning 来自 xarray/NumPy timedelta 弃用提示。
- editable 安装成功；19 个主库、部署、子项目和重建入口 `--help` 通过。
- 50 个 Python 源文件生成 9 份函数/CLI 参考；生成一致性与维护文档本地链接检查通过。
- 未触发真实科学数据下载、1024³ 重建或 Windows/Linux 实机运行；这些验证仍按平台手册执行。
