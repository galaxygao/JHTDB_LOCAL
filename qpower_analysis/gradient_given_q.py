"""Full-grid pressure-gradient magnitude conditioned on existing signed q bins."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import numpy as np

from jhtdb_pipeline.store import spatial_slices
try:
    from .conditional_tails import quantile_from_hist, validated_fields
except ImportError:
    from conditional_tails import quantile_from_hist, validated_fields


def plot(rows, destination, shape, frame_time):
    os.environ.setdefault('MPLCONFIGDIR', str(destination.parent / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, NullFormatter

    fig, axes = plt.subplots(
        2, 3, figsize=(15, 8), layout='constrained',
        gridspec_kw={'height_ratios': [2.5, 1], 'width_ratios': [1, 1.7, 1]},
    )
    for col, region in enumerate(('lower_tail', 'center', 'upper_tail')):
        subset = [r for r in rows if r['region'] == region]
        left = np.array([r['bin_left'] for r in subset])
        right = np.array([r['bin_right'] for r in subset])
        x = np.array([r['bin_center'] for r in subset])
        mean = np.array([r['mean_gradient_normalized'] for r in subset])
        lower = np.array([r['gradient_p25_normalized'] for r in subset])
        upper = np.array([r['gradient_p75_normalized'] for r in subset])
        count = np.array([r['count'] for r in subset])
        volume = np.array([r['volume_fraction'] * 100 for r in subset])
        color = '#2563a6' if region == 'center' else '#c33434'
        top, bottom = axes[:, col]
        top.fill_between(x, lower, upper, color=color, alpha=.18,
                         label='Within-bin 25th–75th percentiles')
        top.plot(x, mean, color=color, lw=1.7, label='Conditional mean')
        dense, sparse = count >= 100, (count > 0) & (count < 100)
        top.scatter(x[dense], mean[dense], color=color, s=12, zorder=3)
        if sparse.any():
            top.scatter(x[sparse], mean[sparse], facecolors='white',
                        edgecolors=color, s=35, zorder=3, label='Fewer than 100 cells')
        top.axhline(1, color='#777', ls='--', lw=.8, label='Global gradient RMS')
        bottom.bar(left, volume, width=right-left, align='edge',
                   color=color, alpha=.65, edgecolor='white', linewidth=.3)
        for ax in (top, bottom):
            ax.set_xlim(left[0], right[-1])
            ax.grid(alpha=.2)
            ax.tick_params(labelsize=9)
            if region != 'center' and left[0] * right[-1] > 0:
                if right[-1] < 0:
                    ax.set_xscale('symlog', linthresh=abs(right[-1])/2)
                else:
                    ax.set_xscale('log')
                ticks = np.sign(left[0]) * np.geomspace(abs(left[0]), abs(right[-1]), 4)
                ax.set_xticks(ticks)
                ax.xaxis.set_major_formatter(FuncFormatter(lambda value, pos: f'{value:.3g}'))
                ax.xaxis.set_minor_formatter(NullFormatter())
        if region != 'center':
            bottom.set_yscale('log')
        top.set_ylabel(r'$|\nabla P|/(\nabla P)_{\mathrm{rms}}$' + '\n(mean and middle 50% of values)')
        bottom.set_ylabel('Volume per bin (%)' + ('\nlog y' if region != 'center' else ''))
        bottom.set_xlabel(r'$q/q_{\mathrm{rms}}$')
        title = {'lower_tail': 'Lower 2.5% | logarithmic magnitude x',
                 'center': 'Central 95% | linear x',
                 'upper_tail': 'Upper 2.5% | logarithmic x'}[region]
        top.set_title(title + f'\nActual volume: {volume.sum():.4f}%', fontsize=11)
        top.legend(fontsize=7, loc='best')
    fig.suptitle('Pressure-gradient magnitude conditioned on signed pressure power\n'
                 f'Full {shape[2]} × {shape[1]} × {shape[0]} frame, t = {frame_time:g}; '
                 r'$q=-\mathbf{u}\cdot\nabla P$, $P=p/\rho$', fontsize=15)
    fig.supxlabel('Shading: within-bin middle 50% of point values, not a confidence interval.\n'
                  'All cells and both full tails retained; independent linear y limits. '
                  'Bars: full-domain volume per bin.', fontsize=9)
    fig.savefig(destination, dpi=180)
    plt.close(fig)


def run(folder: Path):
    config = json.loads((folder / 'config_used.json').read_text())
    outputs = []
    with (folder / 'run_summary.csv').open() as handle:
        summaries = {int(r['frame']): r for r in csv.DictReader(handle)}
    for frame in config['frames']:
        number = int(frame['frame'])
        qr = float(summaries[number]['q_rms'])
        if not np.isfinite(qr) or qr <= 0:
            raise ValueError('Positive finite q RMS required')
        source = folder / f'conditional_tails/frame_{number:06d}_u2_given_q.csv'
        with source.open() as handle:
            bins = list(csv.DictReader(handle))
        edges = np.r_[[float(r['bin_left']) for r in bins], float(bins[-1]['bin_right'])]
        if (np.any(np.diff(edges) <= 0)
                or any(float(r['bin_right']) != edges[i+1] for i, r in enumerate(bins))):
            raise ValueError('Existing q bins must be contiguous and increasing')
        u, g = validated_fields(frame, frame.get('velocity_key', 'velocity'))
        total = int(np.prod(u.shape[1:]))
        n_bins = len(bins)
        counts = np.zeros(n_bins, dtype=np.int64)
        sums = np.zeros(n_bins)
        q_sums = np.zeros(n_bins)
        gradient_edges = np.r_[0., np.geomspace(1e-8, 1e6, 8193)]
        hist = np.zeros((n_bins, len(gradient_edges)-1), dtype=np.int64)
        gradient2_sum = 0.
        blocks = list(spatial_slices(u.shape[1:], (128, 128, 128)))
        print(f'Frame {number}: one full-grid pass, {total:,} cells', flush=True)
        for i, key in enumerate(blocks, 1):
            ub, gb = u[(slice(None), *key)], g[(slice(None), *key)]
            # Preserve float32 q membership used by the original conditional plots.
            q = -np.einsum('izyx,izyx->zyx', ub, gb, optimize=True).ravel().astype(np.float64) / qr
            gg = gb.astype(np.float64)
            g2 = np.einsum('i...,i...->...', gg, gg).ravel()
            magnitude = np.sqrt(g2)
            if not np.isfinite(q).all() or not np.isfinite(magnitude).all():
                raise ValueError('Nonfinite pressure power or gradient magnitude')
            index = np.searchsorted(edges, q, side='right')-1
            index[q == edges[-1]] = n_bins-1
            if np.any(index < 0) or np.any(index >= n_bins):
                raise ValueError('q values lie outside the saved bins')
            gi = np.searchsorted(gradient_edges, magnitude, side='right')-1
            if np.any(gi < 0) or np.any(gi >= hist.shape[1]):
                raise ValueError('Gradient values lie outside percentile histogram bounds')
            counts += np.bincount(index, minlength=n_bins)
            sums += np.bincount(index, weights=magnitude, minlength=n_bins)
            q_sums += np.bincount(index, weights=q, minlength=n_bins)
            hist += np.bincount(index*hist.shape[1]+gi, minlength=hist.size).reshape(hist.shape)
            gradient2_sum += float(g2.sum(dtype=np.float64))
            if i % 32 == 0:
                print(f'  {i}/{len(blocks)} blocks', flush=True)
        expected = np.array([int(r['count']) for r in bins])
        if counts.sum() != total or not np.array_equal(counts, expected):
            raise ValueError('Full-grid counts differ from existing conditional q bins')
        if not np.array_equal(hist.sum(axis=1), counts):
            raise ValueError('Percentile histogram omitted data')
        gr = float(np.sqrt(gradient2_sum/total))
        if gr <= 0:
            raise ValueError('Positive gradient RMS required')
        rows = []
        for b, r in enumerate(bins):
            n = int(counts[b])
            mean = sums[b]/n if n else float('nan')
            p25, p75 = (quantile_from_hist(hist[b], gradient_edges, p) if n else float('nan')
                        for p in (.25, .75))
            rows.append(dict(region=r['region'], bin_left=edges[b], bin_right=edges[b+1],
                             bin_center=float(r['bin_center']), q_mean_normalized=q_sums[b]/n if n else float('nan'),
                             count=n, volume_fraction=n/total, mean_gradient=mean,
                             mean_gradient_normalized=mean/gr, gradient_p25=p25, gradient_p75=p75,
                             gradient_p25_normalized=p25/gr, gradient_p75_normalized=p75/gr,
                             reliable_count=n >= 100))
        out = folder / 'gradient_statistics'
        out.mkdir(exist_ok=True)
        prefix = out / f'frame_{number:06d}_gradient_given_q'
        with prefix.with_suffix('.csv').open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0])
            writer.writeheader()
            writer.writerows(rows)
        metadata = dict(frame=number, time=frame['time'], grid_shape_zyx=list(u.shape[1:]),
                        grid_count=total, q_rms=qr, gradient_rms=gr,
                        pressure_definition=config['pressure_definition'],
                        q_definition='q = -u dot grad(P); original float32 q, normalized by q_rms',
                        gradient_definition='sqrt(sum(grad(P)_i**2)); float64 norms',
                        weighting='equal cell volume; all cells, no velocity/event selection',
                        q_bins_source=str(source), counts_match_source=True,
                        mean_method='All cells, exact bin membership and float64 sums',
                        percentile_method='Approximate linear interpolation within 8192 geometric magnitude bins plus one near-zero bin',
                        histogram_max_adjacent_edge_ratio=float(gradient_edges[2]/gradient_edges[1]),
                        band='Within-bin 25th–75th percentiles of gradient magnitude; not a confidence interval',
                        global_mean_gradient=float(sums.sum()/total),
                        global_mean_gradient_normalized=float(sums.sum()/total/gr))
        prefix.with_suffix('.json').write_text(json.dumps(metadata, indent=2)+'\n')
        np.savez_compressed(prefix.with_suffix('.npz'), counts=hist, gradient_edges=gradient_edges, q_edges=edges)
        plot(rows, prefix.with_suffix('.png'), u.shape[1:], frame['time'])
        print(f'Completed: {prefix.with_suffix(".png")} (gradient RMS = {gr:.9g})', flush=True)
        outputs.append(prefix)
    return outputs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', required=True, type=Path)
    run(parser.parse_args().run_dir)
