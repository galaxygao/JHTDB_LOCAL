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
