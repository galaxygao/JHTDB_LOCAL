"""Volume-weighted velocity/pressure-force angles in positive overlap events."""
import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np
import zarr
from jhtdb_pipeline.store import spatial_slices


def angle_degrees(u, g):
    dot = np.einsum('i...,i...->...', u, g)
    norm = np.sqrt(np.einsum('i...,i...->...', u, u) * np.einsum('i...,i...->...', g, g))
    return np.degrees(np.arccos(np.clip(np.divide(dot, norm, out=np.full_like(dot, np.nan), where=norm > 0), -1, 1)))


def run(folder, alpha=1., beta=1.):
    config = json.loads((folder / 'config_used.json').read_text())
    summary = next(csv.DictReader((folder / 'run_summary.csv').open()))
    frame = config['frames'][0]
    qr, um = float(summary['q_rms']), float(summary['u2_mean'])
    roots = [zarr.open_group(p, mode='r') for p in (frame['velocity_path'], frame['pressure_gradient_path'])]
    for root in roots:
        assert root.attrs['status'] == 'validated'
        assert root.attrs['time_index'] == frame['frame'] and root.attrs['physical_time'] == frame['time']
    u, g = roots[0][frame.get('velocity_key', 'velocity')], roots[1][frame['pressure_gradient_keys'][0]]
    assert u.shape == g.shape
    pieces = []
    blocks = list(spatial_slices(u.shape[1:], (128, 128, 128)))
    for i, key in enumerate(blocks, 1):
        ub, gb = u[(slice(None), *key)], g[(slice(None), *key)]
        q = -np.einsum('izyx,izyx->zyx', ub, gb, optimize=True)
        u2 = np.einsum('izyx,izyx->zyx', ub, ub, optimize=True)
        mask = (q > alpha * qr) & (u2 > beta * um)
        theta = 180.0 - angle_degrees(ub[:, mask].astype('float64'), gb[:, mask].astype('float64'))
        values = np.column_stack((theta, q[mask].astype('float64') / qr, u2[mask].astype('float64') / um)).astype('float32')
        assert np.isfinite(values).all()
        pieces.append(values)
        if i % 32 == 0: print(f'{i}/{len(blocks)} blocks; selected {sum(len(v) for v in pieces):,}', flush=True)
    values = np.concatenate(pieces); del pieces
    cosines = np.cos(np.deg2rad(values[:, 0].astype('float64')))
    out = folder / 'angle_statistics'; out.mkdir(exist_ok=True)
    result = dict(alpha=alpha, beta=beta, selection='q/q_rms > alpha AND u2/mean(u2) > beta', angle='acos(-u dot grad(P) / (|u| |grad(P)|)), degrees', weighting='equal cell volume', count=len(values), volume_fraction=len(values)/int(np.prod(u.shape[1:])), mean_angle_deg=float(np.mean(values[:,0], dtype='float64')), angle_percentiles=dict(zip(['p025','p25','p50','p75','p975'], map(float,np.quantile(values[:,0],[.025,.25,.5,.75,.975])))), q_definition='q=-u dot grad(P), normalized by q_rms', q_rms=qr, u2_mean=um)
    result['mean_cos_theta'] = float(np.mean(cosines))
    for col, name in enumerate(('q_normalized','u2_normalized')):
        x, y = values[:,col+1], values[:,0]
        result['pearson_angle_' + name] = float(np.corrcoef(x, y)[0,1])
        lo, hi = np.quantile(x,[.025,.975])
        edges = np.unique(np.r_[x.min(), np.linspace(lo,hi,41), x.max()])
        index = np.clip(np.searchsorted(edges,x,side='right')-1,0,len(edges)-2)
        rows=[]
        for b in range(len(edges)-1):
            selected=index==b; yy=y[selected]; xx=x[selected]
            if not len(yy): continue
            rows.append(dict(left=float(edges[b]),right=float(edges[b+1]),x_mean=float(np.mean(xx,dtype='float64')),count=len(yy),selected_volume_fraction=len(yy)/len(y),mean_angle_deg=float(np.mean(yy,dtype='float64')),mean_cos_theta=float(np.mean(cosines[selected])),p25=float(np.quantile(yy,.25)),p75=float(np.quantile(yy,.75))))
        with (out / f'angle_given_{name}.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    plot_saved(out)
    print(json.dumps(result,indent=2),flush=True)

def plot_saved(out):
    """Plot equal-width central bins; report pooled tails separately."""
    os.environ.setdefault('MPLCONFIGDIR', str(Path('.local/cache/matplotlib').resolve()))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    result=json.loads((out/'summary.json').read_text())
    fig, axes=plt.subplots(2,2,figsize=(12,8),sharex='col',gridspec_kw={'height_ratios':[3,1]},layout='constrained')
    for col,name in enumerate(('q_normalized','u2_normalized')):
        with (out/f'angle_given_{name}.csv').open() as f:
            rows=[{k:float(v) for k,v in r.items()} for r in csv.DictReader(f)]
        center=rows[1:-1]
        assert abs(sum(r['selected_volume_fraction'] for r in rows)-1)<1e-10
        x=[r['x_mean'] for r in center]
        top,bottom=axes[:,col]
        top.plot(x,[r['mean_angle_deg'] for r in center],label='Bin mean')
        top.fill_between(x,[r['p25'] for r in center],[r['p75'] for r in center],alpha=.2,label='25–75% point values')
        top.set(ylabel='Angle between u and -grad(P) (degrees)',title=name+' | central 95% of selected cells')
        cosine_axis = top.twinx()
        cosine_axis.plot(x, [r['mean_cos_theta'] for r in center], color='tab:orange', linestyle='--', linewidth=2, label='Mean cos(θ)')
        cosine_axis.set_ylabel('Mean cos(θ)', color='tab:orange')
        cosine_axis.tick_params(axis='y', labelcolor='tab:orange')
        handles, labels = top.get_legend_handles_labels()
        cos_handles, cos_labels = cosine_axis.get_legend_handles_labels()
        top.legend(handles + cos_handles, labels + cos_labels, loc='upper left')
        tails=[]
        for label,r in zip(('Lower tail','Upper tail'),(rows[0],rows[-1])):
            tails.append(f"{label}: {100*r['selected_volume_fraction']:.2f}% selected volume; mean angle {r['mean_angle_deg']:.2f}°; mean cos {r['mean_cos_theta']:.3f}")
        bottom.bar([r['left'] for r in center],[100*r['selected_volume_fraction'] for r in center],width=[r['right']-r['left'] for r in center],align='edge',alpha=.65,edgecolor='white',linewidth=.3)
        bottom.set(xlabel='q / q_rms' if col==0 else 'u² / mean(u²)',ylabel='Selected volume\nper bin (%)',ylim=(0,None),xlim=(center[0]['left'],center[-1]['right']))
        top.text(.02,.02,'\n'.join(tails),transform=top.transAxes,fontsize=8,color='firebrick',bbox=dict(facecolor='white',alpha=.85,edgecolor='none'))
        for ax in axes[:,col]: ax.grid(alpha=.2)
    fig.suptitle(f"Positive overlap: alpha={result['alpha']:g}, beta={result['beta']:g}; mean angle={result['mean_angle_deg']:.2f}°")
    fig.supxlabel(f"Bars: fraction of SELECTED volume ({100*result['volume_fraction']:.3f}% of full domain). Central bars sum to 95%; each tail holds 2.5%.\nShared x axes, equal-width central bins, linear volume axis. Shading: middle 50% of point values, not a confidence interval.",fontsize=10)
    fig.savefig(out/'angle_relationships.png',dpi=180);fig.savefig(out/'angle_relationships.pdf');plt.close(fig)

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-dir',type=Path,required=True);parser.add_argument('--alpha',type=float,default=1.);parser.add_argument('--beta',type=float,default=1.)
    args=parser.parse_args();run(args.run_dir,args.alpha,args.beta)
