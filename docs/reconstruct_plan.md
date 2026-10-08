# 仓库整理：实施结果

日期：2026-10-08  
分支：`reconstruct`  
状态：已执行删除与依赖清理，验证通过；尚未提交或推送。

## 保留范围

仓库只保留两个 pipeline：

- 主功能 `src/jhtdb_pipeline/`：下载与输入校验、Gaussian / smooth-sharp 全周期域滤波、速度梯度、Work、Pi、S-bar、散度与能量 QA、Pi weak-asymmetry、结果存储、CLI 与只读 GUI。
- `qpower_analysis/`：现有压力功率、条件统计、角度、梯度及强事件分析、可视化和测试；共享压力下载、FD4 梯度与部署入口保留。

## 已完成删除

- 删除 `block_statistics/`、`pi_pdf/`、`pi_slices/`、`scatter/`、`regime_pi/`、`flux_plateau/` 整个目录，包括各自源码、文档、测试、缓存及专属结果。
- 删除主库 `strain.py` 兼容转发文件和 `PipelineConfig.strain_store_path`；其调用方仅属于已删除的 block 子项目，无需迁移实现或缓存。
- 删除主库 `regime_pi.py`、`cq.py`，以及 `compute-regime-pi` / `compute-cq` CLI 入口、GUI 对应展示和专属测试。
- 删除主计算 regime 分类和写入、physics 分类工具、结果字段、占比、阈值配置、Cq 分区 QA 及相关元数据。Work、Pi 与 S-bar 计算保留。
- 删除 `docs/compact_progress.md`、`scripts/rebuild_result.py` 与重建测试，清理历史更新/重建操作说明。
- 平台脚本、包发现、README、操作手册及代码索引同步调整，包发现只包含 `jhtdb_pipeline` 和 `qpower_analysis`。

Pi 正负分拆 closure 仍是保留的 weak-asymmetry QA，配置项独立命名为 `validation.weak_asymmetry_closure_relative_max`。已移除的 epsilon 和 Cq 配置项不再接受；自定义运行配置应使用当前 YAML。

## 结果格式与原有工作保护

新主结果格式为 v9，向量场继续每轴步长 2 保存，四个标量场保存完整网格，不再生成 regime 或 Cq 报告。每尺度未压缩大小从 23 GiB 降至 22 GiB。

新结果目录使用 `_v9` 后缀，共享目录使用 `_shared_stride2_v9`，batch manifest 使用 `_batch_manifest_v9.json`。旧主结果和输入未修改，读取器仍兼容 v7/v8；相同参数的新旧结果同时存在时，GUI 优先选择最高格式版本。

保留 QPower 已存在的未提交源码、测试、图像及分析结果。入口检查另修复 `lowest_q_bin_angles.py` 和 `near_zero_diagnostic.py` 的直接脚本导入遮蔽问题，不修改科学计算。

## 验证结果

```bash
.venv-mac/bin/python -m pytest tests qpower_analysis/tests -q
.venv-mac/bin/python scripts/update_docs.py --check
bash -n scripts/run_main_macos.sh scripts/download_pressure_mac.sh
git diff --check
```

- 主功能与 QPower：133 项测试通过；2 条原有 xarray/NumPy 弃用提示。
- 覆盖 memory/memmap、谱计算与物理恒等式、QA 校验链、GUI 页面、v9 移除字段、新旧结果路径隔离、旧采样数据读取和删除命令拒绝。
- 本机 10 份既有 v8 主结果经只读元数据/shape 检查均可打开。
- 14 个保留 CLI/直接脚本入口的 `--help` 通过；两个修复的 QPower 入口分别验证脚本与模块方式。
- 34 个 Python 源码生成 3 份参考文档，索引一致性、本地链接、shell 语法和 diff 空白检查通过。
- 未运行在线下载、真实 1024³ 重算或 Windows/Linux 实机验证。

## Git 跟踪范围

仅源码、配置和测试纳入 Git；结果、输出、图像、运行日志、缓存和文档保留本地并忽略。现有输出及文档从索引取消跟踪，不删除本地文件，不改写既有提交历史。
