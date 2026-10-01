# 全域 Pi PDF 分析

本目录提供独立的完整域 Pi 分布分析，不属于生产结果提交步骤。

项目存储 `pi=tau:S`；本分析使用常见 LES 符号：

```text
Pi_LES = -stored pi
Pi_LES > 0 : forward cascade
Pi_LES < 0 : backscatter
```

## 一维 PDF 与尾部

`plot_pi_pdf.py` 逐 Zarr chunk 扫描全部格点，生成原始 Pi、按每 sigma RMS 标准化的 Pi、
正反传输尾部、绝对值 CCDF 和累计贡献。中心图使用跨 sigma 公共 p99 范围，范围外概率在
metadata 中记录；尾部直方图覆盖包括精确零在内的全部格点。

```powershell
.\.venv\Scripts\python.exe pi_pdf\plot_pi_pdf.py `
  --time-index 1 --sigmas 5,10,15,30,55 `
  --filter-type smooth_sharp --sharp-edge-width-fraction 0.1171875 `
  --central-bins 512 --tail-bins 512 --tail-minimum 1e-6 `
  --config configs\pipeline.yaml
```

可用 `--output-dir` 改输出目录。`--smoke-chunks N` 只读取前 N 个 chunk，用于调试，不能
作为完整科学统计。

默认输出 `pi_pdf/output/tXXXXXX/`，包括 HTML、summary CSV/JSON、每 sigma counts/PDF 和
`COMPLETE.json`。

## Contribution-weighted log-Pi Gaussian 检验

`validate_log_pi_gaussian.py` 分别检验 forward/backscatter 的
`log10(abs(Pi_LES)/RMS(Pi_LES,sigma))` contribution-weighted 分布，输出 moments、CDF/PDF
拟合误差、曲率和 QQ 指标：

```powershell
.\.venv\Scripts\python.exe pi_pdf\validate_log_pi_gaussian.py `
  --time-index 1 --sigmas 5,10,15,30,55 `
  --filter-type smooth_sharp --sharp-edge-width-fraction 0.1171875 `
  --bins 256 --y-min -4 --y-max 4 `
  --config configs\pipeline.yaml
```

该分析不执行条件 PDF、tau-strain 分解、DBSCAN、GMM 或 decision tree。
