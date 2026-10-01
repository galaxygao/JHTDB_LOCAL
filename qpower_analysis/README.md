# 3-D pressure-power analysis

## Local 12-block example

Results for the `768 x 256 x 64` subvolume are recorded in
[the analysis report](output/subset_12blocks_t000001/analysis/20261001T003121Z/README.md).
It includes grid-point overlap counts, both conditional directions, their
independent-random baselines, and speed-squared contributions above thresholds.
HTML figures show sampled grid points, with separate colors for A-only, B-only,
and the intersection. Statistics use every grid point in the subvolume.
Extracted `.npy` input caches remain local and are excluded from Git.

This folder is a standalone implementation of `../3D_QPOWER_ANALYSIS_TASK.md`.
It computes

`q = -(u*dPdx + v*dPdy + w*dPdz)` and `u2 = u*u + v*v + w*w`

for one or more 3-D frames, writes per-frame and aggregate CSV files, orthogonal
slices, threshold-region HTML visualizations, overlays, and conditional means.

## Safety rule: pressure is required

Every invocation performs a metadata-only preflight before allocating a run
directory or loading full arrays. A frame must provide either:

- `pressure_path` containing `pressure_key`, or
- all three arrays named by `pressure_gradient_keys`.

Missing pressure is a hard error. It is never replaced with zero.

## Input formats

Zarr v2 directories, `.npy`, and `.npz` files are supported. Velocity may be a
single component-first array `(3, z, y, x)` or three separate arrays. Pressure
is `(z, y, x)`. Pressure gradients may be a component-first `(3, z, y, x)`
array or three separate arrays. All fields must have the same finite 3-D shape.

Copy `config.example.json`, set the paths and frame metadata, then run:

```powershell
..\.venv\Scripts\python.exe .\qpower_analysis.py --config .\config.example.json --preflight-only
..\.venv\Scripts\python.exe .\qpower_analysis.py --config .\config.example.json
```

The example points at the local velocity cache and the managed pressure-gradient
cache. Its preflight fails until the pressure-gradient download is complete.
See `../docs/pressure_gradient_loading.md` for acquisition commands.

Tests use small synthetic fields and do not need production data:

```powershell
..\.venv\Scripts\python.exe -m pytest .\tests -q
```
