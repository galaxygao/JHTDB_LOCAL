"""Diagnose small pressure power using every cell of an existing QPower run."""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path

import numpy as np

from jhtdb_pipeline.store import spatial_slices
if __package__:
    from .conditional_tails import validated_fields, quantile_from_hist
else:
    from conditional_tails import validated_fields, quantile_from_hist


def run(folder: Path) -> None:
    config = json.loads((folder / 'config_used.json').read_text())
    frame = config['frames'][0]
    with (folder / 'run_summary.csv').open() as handle:
        summary = next(r for r in csv.DictReader(handle) if int(r['frame']) == frame['frame'])
    qr, um = float(summary['q_rms']), float(summary['u2_mean'])
    u, g = validated_fields(frame, frame.get('velocity_key', 'velocity'))
    blocks = list(spatial_slices(u.shape[1:], (128, 128, 128)))
    total = int(np.prod(u.shape[1:]))
    started = time.perf_counter()
    g2_sum = 0.0
    g_min = float('inf')
    print('Pass 1: pressure-gradient RMS over the full grid', flush=True)
    for i, key in enumerate(blocks, 1):
        gb = g[(slice(None), *key)].astype(np.float64)
        gg = np.einsum('i...,i...->...', gb, gb)
        if not np.isfinite(gg).all():
            raise ValueError('Nonfinite pressure gradient')
        g2_sum += gg.sum(dtype=np.float64)
        g_min = min(g_min, float(gg.min()))
        if i % 64 == 0:
            print(f'  {i}/{len(blocks)} blocks; {time.perf_counter()-started:.1f}s', flush=True)
    gr = float(np.sqrt(g2_sum / total))
    if min(qr, um, gr) <= 0:
        raise ValueError('Positive normalization scales required')
    with (folder / f"conditional_tails/frame_{frame['frame']:06d}_u2_given_q.csv").open() as handle:
        peak = max((r for r in csv.DictReader(handle) if r['region'] == 'center'), key=lambda r: int(r['count']))
    peak_lo, peak_hi = float(peak['bin_left']), float(peak['bin_right'])
    names = ['all', 'abs_q_lt_0.1_rms', 'abs_q_lt_0.05_rms', 'abs_q_lt_0.01_rms', 'existing_peak_bin']
    # Fine histograms support reproducible approximate medians; feature counts are exact.
    edges = {'speed': np.r_[np.linspace(0, 4, 4001), np.inf],
             'gradient': np.r_[np.linspace(0, 8, 8001), np.inf],
             'abs_cos': np.linspace(0, 1, 2001)}
    hist = {name: {k: np.zeros(len(e)-1, dtype=np.int64) for k,e in edges.items()} for name in names}
    stats = {name: dict(count=0, speed_small=0, gradient_small=0, perpendicular=0,
                       neither_norm_small_and_perpendicular=0, either_norm_small=0,
                       both_norm_small=0, all_three_regular=0, amplitude_lt_0_1_qrms=0,
                       speed2_sum=0., gradient2_sum=0., abs_cos_sum=0., amplitude_sum=0.) for name in names}
    zeros = dict(velocity_vector=0, gradient_vector=0, q_float32=0, q_float64_dot=0)
    angle_sq_sum = 0.
    print('Pass 2: exact feature counts and conditional histograms', flush=True)
    for i, key in enumerate(blocks, 1):
        ub, gb = u[(slice(None), *key)], g[(slice(None), *key)]
        # Keep event membership identical to the existing float32 QPower analysis.
        q = -np.einsum('izyx,izyx->zyx', ub, gb, optimize=True).ravel().astype(np.float64) / qr
        uu, gg = ub.astype(np.float64), gb.astype(np.float64)
        u2 = np.einsum('i...,i...->...', uu, uu).ravel()
        g2 = np.einsum('i...,i...->...', gg, gg).ravel()
        dot = np.einsum('i...,i...->...', uu, gg).ravel()
        amp = np.sqrt(u2*g2)
        cosine = np.clip(np.divide(np.abs(dot), amp, out=np.full_like(dot, np.nan), where=amp>0), 0, 1)
        if not np.isfinite(u2).all() or not np.isfinite(q).all():
            raise ValueError('Nonfinite velocity/power')
        speed, gradient = np.sqrt(u2/um), np.sqrt(g2)/gr
        us, gs, orth = speed < .1, gradient < .1, cosine < .1
        zeros['velocity_vector'] += int(np.count_nonzero(u2 == 0))
        zeros['gradient_vector'] += int(np.count_nonzero(g2 == 0))
        zeros['q_float32'] += int(np.count_nonzero(q == 0))
        zeros['q_float64_dot'] += int(np.count_nonzero(dot == 0))
        angle_sq_sum += float(np.nansum(cosine*cosine))
        selections = [np.ones(q.size, dtype=bool), np.abs(q)<.1, np.abs(q)<.05,
                      np.abs(q)<.01, (q>=peak_lo)&(q<peak_hi)]
        features = dict(speed_small=us, gradient_small=gs, perpendicular=orth,
                        neither_norm_small_and_perpendicular=~us & ~gs & orth,
                        either_norm_small=us | gs, both_norm_small=us & gs,
                        all_three_regular=~us & ~gs & ~orth,
                        amplitude_lt_0_1_qrms=amp/qr < .1)
        values = dict(speed=speed, gradient=gradient, abs_cos=cosine)
        # Arithmetic binning avoids sorting billion-cell inputs.
        indices = {}
        for field, v in values.items():
            finite = np.isfinite(v)
            idx = np.zeros(v.size, dtype=np.int64)
            idx[finite] = np.minimum((v[finite]*(1000 if field != 'abs_cos' else 2000)).astype(np.int64), len(edges[field])-2)
            indices[field] = (idx, finite)
        for name, mask in zip(names, selections):
            s = stats[name]
            s['count'] += int(np.count_nonzero(mask))
            for field, feature in features.items():
                s[field] += int(np.count_nonzero(mask & feature))
            s['speed2_sum'] += float(np.sum(u2[mask]/um))
            s['gradient2_sum'] += float(np.sum(g2[mask]/gr**2))
            s['abs_cos_sum'] += float(np.nansum(cosine[mask]))
            s['amplitude_sum'] += float(np.sum(amp[mask]/qr))
            for field, (idx, finite) in indices.items():
                hist[name][field] += np.bincount(idx[mask & finite], minlength=len(edges[field])-1)
        if i % 32 == 0:
            print(f'  {i}/{len(blocks)} blocks; {time.perf_counter()-started:.1f}s', flush=True)
    assert stats['all']['count'] == total
    if stats['existing_peak_bin']['count'] != int(peak['count']):
        raise ValueError(f"Peak count mismatch: {stats['existing_peak_bin']['count']} vs {peak['count']}")
    rows = []
    for name, s in stats.items():
        n = s['count']
        r = dict(population=name, count=n, volume_fraction=n/total)
        r.update({field+'_fraction': s[field]/n for field in features})
        r.update(mean_u2_over_global_mean=s['speed2_sum']/n,
                 mean_gradient2_over_global_mean=s['gradient2_sum']/n,
                 mean_abs_cos=s['abs_cos_sum']/n,
                 mean_amplitude_over_qrms=s['amplitude_sum']/n)
        for field in edges:
            for p in (.25, .5, .75):
                r[f'{field}_p{int(p*100):02d}'] = quantile_from_hist(hist[name][field], edges[field], p)
        rows.append(r)
    out = folder / 'near_zero_diagnostic'
    out.mkdir(exist_ok=True)
    with (out/'statistics.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader(); writer.writerows(rows)
    metadata = dict(frame=frame, grid_shape_zyx=list(u.shape[1:]), grid_count=total,
                    q_rms=qr, u2_mean=um, gradient_rms=gr, gradient_min=np.sqrt(g_min),
                    exact_zero_counts=zeros, global_cos_rms=np.sqrt(angle_sq_sum/total),
                    peak_bin=dict(left=peak_lo,right=peak_hi,count=int(peak['count'])),
                    definitions=dict(speed_small='|u| < 0.1 sqrt(mean(u2))',
                                     gradient_small='|grad(P)| < 0.1 sqrt(mean(|grad(P)|2))',
                                     perpendicular='|cos(angle(u,grad(P)))| < 0.1; 84.2608 to 95.7392 degrees',
                                     amplitude='|u| |grad(P)| / q_rms'),
                    method='Two full-grid passes; float64 norms and angles; existing float32 q for selection; exact counts and float64 sums; quartiles interpolated from histograms (speed/gradient step 0.001, abs cosine step 0.0005); features overlap, not causal attribution',
                    elapsed_seconds=time.perf_counter()-started)
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    np.savez_compressed(out/'histograms.npz', **{f'{n}_{f}':h for n,hs in hist.items() for f,h in hs.items()}, **{f'{f}_edges':e for f,e in edges.items()})
    plot_saved(out)
    print(json.dumps(dict(metadata=metadata,statistics=rows),indent=2),flush=True)


def plot_saved(out: Path) -> None:
    """Compare full-grid and near-zero conditional CDFs from saved histograms."""
    os.environ.setdefault('MPLCONFIGDIR', str(Path('.local/cache/matplotlib').resolve()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    populations = [('all', 'All cells'), ('existing_peak_bin', 'Existing peak bin'),
                   ('abs_q_lt_0.01_rms', r'$|q| < 0.01 q_{rms}$')]
    labels = dict(speed=r'$|\mathbf{u}|/u_{rms}$',
                  gradient=r'$|\nabla P|/(\nabla P)_{rms}$',
                  abs_cos=r'$|\cos\theta|$, $\theta=\angle(\mathbf{u},\nabla P)$')
    with np.load(out/'histograms.npz') as saved:
        fig, axes = plt.subplots(1, 3, figsize=(13, 4), layout='constrained')
        for ax, field in zip(axes, ('speed', 'gradient', 'abs_cos')):
            right = saved[f'{field}_edges'][1:]
            finite = np.isfinite(right)
            for population, label in populations:
                counts = saved[f'{population}_{field}']
                ax.plot(right[finite], np.cumsum(counts)[finite]/counts.sum(), label=label)
            ax.axvline(.1, color='gray', ls='--', lw=1)
            ax.set(xlabel=labels[field], ylabel='Fraction within each population',
                   xlim=(0, 1 if field == 'abs_cos' else 2), ylim=(0, 1))
            ax.grid(alpha=.2)
        axes[0].legend(fontsize=9)
        fig.suptitle('Near-zero pressure power: full-grid conditional distributions')
        for suffix in ('png', 'pdf'):
            fig.savefig(out/f'factor_cdfs.{suffix}', dpi=180)
        plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    run(parser.parse_args().run_dir)
