# Pi_LES 一维 PDF 与尾部基线

时间帧：`time_index=1`；范围：`full_domain`。

符号：`Pi_LES = -stored pi = -tau:S`，正值为 forward cascade，负值为 backscatter。

所有 tail histogram 覆盖每个格点。中心 PDF 为保证跨尺度可读性，只显示由六尺度全域 p99 确定的公共中心范围，范围外概率通过 metadata 明确记录，并在 CCDF/tail 图中完整保留。

## 输出

- `pi_pdf_raw.html`：原始物理单位中心 PDF；
- `pi_pdf_normalized.html`：Pi/RMS 标准化中心 PDF；
- `pi_signed_tail_pdf.html`：forward/backscatter 分侧尾部；
- `pi_abs_ccdf.html`：绝对强度 CCDF；
- `pi_tail_contribution.html`：阈值以上事件的 signed/absolute 累计贡献；
- `pi_pdf_summary.csv`：六尺度统计和闭合表；
- 各 `sigma_*` 子目录：精确 counts、PDF、weighted sums 和 metadata。

本阶段只建立 Pi 的一维分布基线；没有执行条件 PDF、tau--strain 分解、DBSCAN、GMM 或 decision tree。
