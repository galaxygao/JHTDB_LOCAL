# r = Δx: top three periodic connected structures and enclosed cavities

Open `top3_cavities.html` in a browser; it is self-contained and needs no network.
Use the dropdown for each structure, all three together, or a local view around
the largest enclosed cavity of each structure. The local views retain exact voxel
surfaces and unwrap periodic coordinates. Local blue geometry is cropped at the
view boundary. Click legends to hide channels; the slider controls blue opacity.

There are seven views: three individual structures, one combined view, and three
cavity closeups. All four global views use [-256.5, 1279.5] on x/y/z. Only the
explicitly selected closeups use tighter ranges. The main periodic box retains
its original coordinates and is outlined in gray. The checkbox toggles periodic
continuation without changing the common axis ranges.

Periodic surface neighbors are resolved before extracting meshes: faces between
occupied voxels across the periodic seam are omitted. The same surface is tiled
through faces, edges, and corners into a 256-grid-spacing halo. Exterior copies
fade in four layers. The outer halo boundary is a display truncation, not the
end of a physical structure. There is no purple annotation. Red/green surfaces
repeat with the same periodic transformation; copies do not change counts.

Validation: a pair of voxels at opposite periodic faces has 20 surface triangles
instead of 24, with no caps at the joined faces; its exterior surface copies lie
within the configured halo. The primary-box coordinates and voxel counts stay
unchanged. `view_ranges.json` records the view count, shared ranges, and halo.

- Blue, transparent: the selected ranked structure.
- Green, opaque: points passing both thresholds but belonging to another
  component, inside an enclosed cavity of this structure.
- Red, opaque: points failing the joint threshold, inside such a cavity.
- External complement: invisible.

All classifications use the original 1024³ grid and periodic boundaries.
Foreground connectivity uses 6 neighbors, exactly r = Δx. Complement connectivity
uses 26 neighbors, so diagonal escape paths are treated as open. A background
component containing more than half the domain is verified and designated the
exterior. Remaining components are checked for periodic winding using lifted
coordinates; winding components are also excluded from cavities. This is a
conservative digital definition of enclosed cavities, not a convex hull or a
geometric envelope. Different complement adjacency rules can change counts.

| Rank | Structure points | Cavities | Green points | Red points |
|---:|---:|---:|---:|---:|
| 1 | 36,187,521 | 213 | 0 | 2,169 |
| 2 | 162,988 | 1 | 0 | 2 |
| 3 | 161,275 | 1 | 0 | 1 |

The global blue mesh of rank 1 aggregates occupied 8×8×8 blocks for browser
performance. It thickens fine branches and may cover small holes. This mesh must
not be used to infer cavity connectivity or precise shape. Rank 2/3 blue meshes,
all red/green meshes, and local cavity views retain original voxel resolution.
`preview.png` is a sampled XY projection of the primary box only, with depth collapsed. Use the HTML for periodic continuation.

Validation: a synthetic closed shell crossing the periodic boundary contains
exactly one green voxel and 124 red voxels. Opening a one-voxel passage removes
all cavity coloring. Full-data selected count (52,800,256), component count
(156,215), and maximum size match the earlier H0 results.

Reproduce from the qpower_analysis directory:

```sh
clang++ -O3 -std=c++17 scripts/visualize_h0_cavities.cpp -o /tmp/visualize_h0_cavities
/tmp/visualize_h0_cavities output/20261001T044629Z/strong_event_h0_alpha1_beta1/selection_mask.bits 1024 output/20261001T044629Z/strong_event_h0_alpha1_beta1/cavities_r1
MPLCONFIGDIR=/tmp/h0-mpl ../.venv-mac/bin/python scripts/render_h0_cavities.py output/20261001T044629Z/strong_event_h0_alpha1_beta1/cavities_r1
```

Binary point lists are uint32 flat indices in C-order z,y,x. Scripts read source
data internally; no raw binary, embedded image content, or full HTML is printed.
