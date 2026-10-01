# Log-Pi contribution Gaussian validation

范围：`full_domain`，时间帧 `time_index=1`。

正向与 backscatter 分开处理：`y=log10(|Pi_LES|/RMS(Pi_LES))`。每个格点按 `|Pi_LES|` 加权，因此拟合对象是 Pi contribution，不是普通点数 PDF。

每个分支的面积是该分支对 `mean(Pi_LES)`（正向）或 `mean(|Pi_LES|)`（backscatter magnitude）的贡献。参数 `mu_log10` 和 `sigma_log10` 使用精确流式 weighted moments 求得。

`log_pi_contribution_cdf.html` 用经验累计 contribution 与 Gaussian CDF 比较；`log_pi_contribution_pdf.html` 比较 histogram density 与 Gaussian CDF 的解析导数；`log_pi_gaussian_derivatives.html` 检查 log-density 的线性一阶导数和近似常数二阶导数；`log_pi_gaussian_qq.html` 做分位数检查。

由于全域点数极大，不能只用显著性检验决定是否 Gaussian；应结合 weighted skewness、excess kurtosis、CDF 核心区误差、log-density quadratic R²、曲率误差和 QQ 图判断。
