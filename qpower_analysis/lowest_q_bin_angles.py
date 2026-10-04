"""Plot the lowest-q populations of the saved positive-overlap angle analysis."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np

from jhtdb_pipeline.store import spatial_slices
from qpower_analysis.angle_statistics import angle_degrees
from qpower_analysis.conditional_tails import validated_fields


def run(folder: Path) -> None:
    config = json.loads((folder/'config_used.json').read_text())
    saved = json.loads((folder/'angle_statistics/summary.json').read_text())
    frame = config['frames'][0]
    u, g = validated_fields(frame, frame.get('velocity_key', 'velocity'))
    with (folder/'angle_statistics/angle_given_q_normalized.csv').open() as handle:
        bins = list(csv.DictReader(handle))[:2]
    qr, um = saved['q_rms'], saved['u2_mean']
    pieces = [[], []]
    blocks = list(spatial_slices(u.shape[1:], (128, 128, 128)))
    overlap_count = 0
    for i, key in enumerate(blocks, 1):
        ub, gb = u[(slice(None), *key)], g[(slice(None), *key)]
        q = -np.einsum('izyx,izyx->zyx', ub, gb, optimize=True)
        u2 = np.einsum('izyx,izyx->zyx', ub, ub, optimize=True)
        overlap = (q > saved['alpha']*qr) & (u2 > saved['beta']*um)
        overlap_count += int(np.count_nonzero(overlap))
        # Saved angle statistics bins the float32 normalized horizontal variable.
        qn = (q.astype(np.float64)/qr).astype(np.float32).astype(np.float64)
        for row, selected in zip(bins, pieces):
            mask = overlap & (qn >= float(row['left'])) & (qn < float(row['right']))
            if np.any(mask):
                theta = 180.-angle_degrees(ub[:, mask].astype(np.float64), gb[:, mask].astype(np.float64))
                selected.append(theta.astype(np.float32))
        if i % 64 == 0:
            print(f'{i}/{len(blocks)} blocks', flush=True)
    if overlap_count != saved['count']:
        raise ValueError('Overlap population differs from saved statistics')
    values = [np.concatenate(p) for p in pieces]
    results = []
    edges = np.arange(0, 91, dtype=float)
    for row, theta in zip(bins, values):
        if len(theta) != int(row['count']) or not np.isfinite(theta).all():
            raise ValueError('Selected count or finite-value check failed')
        probabilities = [.025, .25, .5, .75, .975]
        quantiles = dict(zip(['p025', 'p25', 'p50', 'p75', 'p975'], map(float, np.quantile(theta, probabilities))))
        mean = float(np.mean(theta, dtype=np.float64))
        if abs(mean-float(row['mean_angle_deg'])) > 1e-6:
            raise ValueError('Mean angle differs from saved bin')
        for k in ('p25', 'p75'):
            if abs(quantiles[k]-float(row[k])) > 1e-5:
                raise ValueError('Quartile differs from saved bin')
        counts = np.histogram(theta, edges)[0]
        if counts.sum() != len(theta):
            raise ValueError('Angle histogram omitted points')
        results.append(dict(q_left=float(row['left']), q_right=float(row['right']),
                            count=len(theta), mean_angle_deg=mean, **quantiles,
                            fraction_within_p25_p75=float(np.mean((theta>=quantiles['p25']) & (theta<=quantiles['p75']))),
                            fraction_35_to_65_deg=float(np.mean((theta>=35) & (theta<=65))),
                            angle_min=float(theta.min()), angle_max=float(theta.max()),
                            fraction_near_perpendicular=float(np.mean(theta>np.degrees(np.arccos(.1))))))
    out = folder/'angle_statistics/lowest_q_bin_distribution'
    out.mkdir(exist_ok=True)
    np.savez_compressed(out/'angle_values.npz', lower_tail=values[0], first_visible_bin=values[1])
    metadata = dict(selection=saved['selection'], alpha=saved['alpha'], beta=saved['beta'],
                    angle='angle(u,-grad(P)), degrees', weighting='equal cell volume',
                    histogram='1 degree bins; percentages normalized within each population',
                    method='Full-grid scan, no sampling. Exact NumPy quartiles of all retained float32 angles; counts, means and quartiles checked against saved CSV.',
                    overlap_count=overlap_count, lower_tail=results[0], first_visible_bin=results[1])
    (out/'summary.json').write_text(json.dumps(metadata, indent=2)+'\n')
    rows = []
    for name, theta in zip(('lower_tail', 'first_visible_bin'), values):
        counts = np.histogram(theta, edges)[0]
        rows.extend(dict(population=name, angle_left=l, angle_right=r, count=int(n), fraction=n/len(theta))
                    for l, r, n in zip(edges[:-1], edges[1:], counts))
    with (out/'histogram.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0]); writer.writeheader(); writer.writerows(rows)
    os.environ.setdefault('MPLCONFIGDIR', str(Path('.local/cache/matplotlib').resolve()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharex=True, sharey=True, layout='constrained')
    # The left panel is the actual leftmost bin visible in angle_relationships.png.
    for ax, idx, title in zip(axes, (1, 0), ('Leftmost bin shown in angle relationship', 'Pooled lower-q tail (not shown as a main bin)')):
        theta, result = values[idx], results[idx]
        counts = np.histogram(theta, edges)[0]
        ax.bar(edges[:-1], 100*counts/len(theta), width=1, align='edge', color='#377eb8', alpha=.75)
        ax.axvspan(result['p25'], result['p75'], color='#f5b348', alpha=.28, label='Middle 50% of point angles')
        for k in ('p25', 'p75'):
            ax.axvline(result[k], color='#bd7b0b', lw=1.5)
        ax.axvline(result['mean_angle_deg'], color='black', ls='--', label=f"Mean {result['mean_angle_deg']:.2f}°")
        ax.set(title=title+f"\n{result['q_left']:.5f} ≤ q/q_rms < {result['q_right']:.5f}; N = {len(theta):,}",
               xlabel='Angle between u and -grad(P) (degrees)',
               ylabel='Cells in each 1° bin (% of this population)', xlim=(0,90))
        ax.text(.03,.96,f"P25–P75: {result['p25']:.2f}°–{result['p75']:.2f}°\nMedian: {result['p50']:.2f}°", transform=ax.transAxes, va='top',
                bbox=dict(facecolor='white', alpha=.9, edgecolor='none'))
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(axis='y', alpha=.2)
    fig.suptitle('Angle distributions in the lowest-q part of POSITIVE OVERLAP\nSelection: q > q_rms AND u² > mean(u²)', fontsize=14)
    fig.supxlabel('Orange shading: 25th–75th percentiles of individual angles, not uncertainty of the mean. Each histogram totals 100%.', fontsize=9)
    for suffix in ('png', 'pdf'):
        fig.savefig(out/f'angle_distribution.{suffix}', dpi=180)
    plt.close(fig)
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    run(parser.parse_args().run_dir)
