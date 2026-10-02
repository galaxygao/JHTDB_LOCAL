# Regime 内 Pi 正反传输

核心实现在 [`statistics.py`](statistics.py)，本目录保存代码、测试和输出。主库 `jhtdb_pipeline.regime_pi` 仅为 CLI/GUI 保留兼容导出。它逐块读取完整域 `pi`、
`work_full` 和 `work_resolved`，在六个 Cq regime 内分别统计：

- backscatter：存储的 `pi>0`；
- forward：存储的 `pi<0`，以正幅值 `-pi` 报告；
- `count` 和 regime 内方向格点占比 `fraction=N_q,d/N_q`；
- 方向内条件幅值 `mean=sum|pi|/N_q,d`；
- regime 体积平均强度 `intensity=sum|pi|/N_q=mean*fraction`；
- `intensity_backscatter-intensity_forward=mean(pi|regime)` closure。

多 sigma 运行：

```powershell
.\.venv\Scripts\python.exe -m jhtdb_pipeline compute-regime-pi `
  --time-index 1 --sigma-grids 10 15 30 55 75 `
  --filter-type smooth_sharp --sharp-edge-width-fraction 0.1171875 `
  --config configs\pipeline.yaml
```

输出默认位于
`regime_pi/output/<result_id>/regime_pi_transfer.json`，包含全部数值、源 result
manifest hash、覆盖检查和 closure。当前命令不单独写 CSV 或 HTML；三组柱状图和表格由
GUI 根据这份 JSON 动态生成。

GUI 的 “Weak asymmetry” 页面会自动读取与当前 result manifest hash 匹配的这份报告。

## 代码与验证导航

所有运行命令从项目根目录执行。完整参数见 [CLI 参考](../docs/cli_reference.md)，所有函数与实现定位见 [本项目代码参考](CODE_REFERENCE.md)。测试：`python -m pytest regime_pi/tests -q`；解释器使用根 README 对应平台虚拟环境。返回 [项目 README](../README.md)。
