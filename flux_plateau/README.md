# Mean Pi / epsilon flux plateau

This analysis plots the full-domain mean forward SGS flux against the linear
Gaussian-equivalent scale:

```text
y = <Pi_forward> / epsilon_reference = -<stored pi> / epsilon_reference
x = r_eq / eta_reference
```

The defaults `epsilon_reference=0.0928` and `eta_reference=0.00287` exactly match the
provided Gaussian and paper comparison. For computed filters, `r_eq` is defined through
the common half-gain relation `k_1/2*r_eq=sqrt(24 ln 2)`. Paper `r/eta` values are plotted
directly without conversion.

The minus sign is required because the production store uses
`pi = tau_ij * d_j(velocity_bar_i)`, where negative values are forward cascade.
Both axes are linear, the gray band marks `1 +/- 5%`, and the dashed line is the
ideal inertial-range plateau.

```powershell
python -m flux_plateau.plot_pi_epsilon_vs_k --time-index 1 `
  --config configs/pipeline.yaml
```

Only `manifest.json`, `cq.json`, and `qa.json` are read. The full Zarr fields are not scanned.
The generated HTML includes every currently discoverable Gaussian and proportional-width
smooth-sharp result family plus the 14-point paper reference curve.

Two HTML views are written from the same points and normalization:

- `pi_over_epsilon_vs_r_eta_linear.html`: linear `r_eq/eta` x-axis and linear flux y-axis.
- `pi_over_epsilon_vs_log_k.html`: logarithmic half-gain wavenumber `k_1/2` x-axis and
  linear flux y-axis. For paper points, `k_1/2=sqrt(24 ln 2)/(r_eq/eta*eta_reference)`.

`plot_flux_comparison.m` adds the smooth-sharp result family to the existing Gaussian/paper
`r_eq/eta` comparison. It keeps the original reference values `epsilon=0.0928` and
`eta=0.00287`, and converts smooth-sharp sigma to a Gaussian-equivalent width by matching
the half-gain wavenumber.

## 代码与验证导航

所有运行命令从项目根目录执行。完整参数见 [CLI 参考](../docs/cli_reference.md)，所有函数与实现定位见 [本项目代码参考](CODE_REFERENCE.md)。测试：`python -m pytest flux_plateau/tests -q`；解释器使用根 README 对应平台虚拟环境。返回 [项目 README](../README.md)。

`plot_flux_comparison.m` 是独立 MATLAB 静态参考图脚本，内部固定 Gaussian、论文及 smooth-sharp 比较数组（包括历史固定边宽组），不读取当前 Zarr，不代表本次计算输出。MATLAB 中从项目根运行 `run('flux_plateau/plot_flux_comparison.m')`；当前生产滤波只使用比例边宽，重算图表应使用 Python 入口读取新报告。
