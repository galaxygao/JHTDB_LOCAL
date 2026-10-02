"""Add configurable per-bin central value ranges, retaining existing bins and means."""
import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np
import zarr
from conditional_tails import fields, quantile_from_hist, plot


def value_edges(name,minimum,maximum):
    if name=='q':
        positive=np.geomspace(1e-8,max(abs(minimum),abs(maximum))*(1+1e-12),32768)
        return np.concatenate((-positive[::-1],[0.],positive))
    return np.geomspace(min(minimum,1e-8),maximum*(1+1e-12),65537)


def indices(values,edges):
    result=np.searchsorted(edges,values.ravel(),side='right')-1
    result[values.ravel()==edges[-1]]=len(edges)-2
    if np.any(result<0) or np.any(result>=len(edges)-1):
        raise ValueError('Values outside histogram')
    return result


def quantile_ranges(hist,edges,exact,coverage=.95):
    probabilities=[(1-coverage)/2,(1+coverage)/2]
    output=[]
    for i,h in enumerate(hist):
        if h.sum()==0:output.append((float('nan'),float('nan')))
        elif i in exact:
            values=np.concatenate(exact[i])
            if len(values)!=h.sum():raise ValueError('Incomplete sparse-bin data')
            output.append(tuple(np.quantile(values,probabilities)))
        else:output.append((quantile_from_hist(h,edges,probabilities[0]),quantile_from_hist(h,edges,probabilities[1])))
    return output


def run(folder,coverage=.5,from_histograms=False):
    if not 0 < coverage < 1: raise ValueError("coverage must lie between 0 and 1")
    os.environ.setdefault('MPLCONFIGDIR',str(Path('.local/cache/matplotlib').resolve()))
    config=json.loads((folder/'config_used.json').read_text())
    with (folder/'run_summary.csv').open() as handle:
        summaries={int(r['frame']):r for r in csv.DictReader(handle)}
    out=folder/'conditional_tails'
    for frame in config['frames']:
        number=int(frame['frame']);summary=summaries[number]
        metadata=json.loads((out/f'frame_{number:06d}_metadata.json').read_text())
        plans={}
        for direction,xname,yname in (('q_given_u2','u2','q'),('u2_given_q','q','u2')):
            prefix=out/f'frame_{number:06d}_{direction}'
            with prefix.with_suffix('.csv').open() as handle: rows=list(csv.DictReader(handle))
            for row in rows:
                for key in ('bin_left','bin_right','bin_center','volume_fraction','conditional_mean_normalized'):row[key]=float(row[key])
                row['count']=int(row['count'])
            xedges=np.array([r['bin_left'] for r in rows]+[rows[-1]['bin_right']])
            source=metadata['plots']['u2_given_q' if yname=='q' else 'q_given_u2']
            yedges=value_edges(yname,source['minimum'],source['maximum'])
            plans[direction]=dict(rows=rows,xname=xname,yname=yname,xedges=xedges,yedges=yedges,
                histogram=np.zeros((len(rows),len(yedges)-1),dtype=np.int64),
                exact={i:[] for i,r in enumerate(rows) if 0<r['count']<100})
        roots=[zarr.open_group(frame[k],mode='r') for k in ('velocity_path','pressure_gradient_path')]
        for root in roots:
            if root.attrs.get('status')!='validated' or root.attrs.get('time_index')!=number or root.attrs.get('physical_time')!=frame['time']:
                raise ValueError('Unvalidated or mismatched input')
        u=roots[0][frame['velocity_key']];g=roots[1][frame['pressure_gradient_keys'][0]]
        if u.shape!=g.shape:raise ValueError('Input shapes differ')
        if from_histograms:
            for direction,plan in plans.items():
                with np.load(out/f'frame_{number:06d}_{direction}_value_histogram.npz') as saved:
                    if not np.array_equal(saved['x_edges'],plan['xedges']):raise ValueError('Cached bin edges differ')
                    plan['histogram']=saved['counts'].copy()
                    plan['yedges']=saved['y_edges'].copy()
                    plan['exact']={}
        else:
            print('Full-grid pass: conditional value distributions',flush=True)
            for q,u2 in fields(u,g,float(summary['q_rms']),float(summary['u2_mean'])):
                data={'q':q,'u2':u2}
                for plan in plans.values():
                    x,y=data[plan['xname']],data[plan['yname']]
                    ix=indices(x,plan['xedges']);iy=indices(y,plan['yedges'])
                    ny=len(plan['yedges'])-1
                    plan['histogram']+=np.bincount(ix*ny+iy,minlength=plan['histogram'].size).reshape(plan['histogram'].shape)
                    for i,arrays in plan['exact'].items():
                        values=y.ravel()[ix==i]
                        if values.size:arrays.append(values.copy())
        for direction,plan in plans.items():
            rows=plan['rows'];hist=plan['histogram']
            if not np.array_equal(hist.sum(axis=1),[r['count'] for r in rows]):
                raise ValueError('Bin memberships differ from previous plot')
            ranges=quantile_ranges(hist,plan['yedges'],plan['exact'],coverage)
            for row,(lower,upper) in zip(rows,ranges):
                row.update(value_lower=lower,value_upper=upper,value_coverage=coverage)
                if coverage == .5: row.update(value_p25=lower,value_p75=upper)
                elif coverage == .95: row.update(value_p025=lower,value_p975=upper)
            prefix=out/f'frame_{number:06d}_{direction}'
            with prefix.with_suffix('.csv').open('w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
            np.savez_compressed(out/f'frame_{number:06d}_{direction}_value_histogram.npz',counts=hist,y_edges=plan['yedges'],x_edges=plan['xedges'])
            plot(rows,direction,prefix,100,u.shape[1:],frame['time'])
        metadata['value_range']={'probabilities':[(1-coverage)/2,(1+coverage)/2],
            'meaning':f'central {coverage*100:g}% of point values WITHIN each x bin; not mean confidence interval',
            'method':('cached all-point histograms; interpolated quantiles for all bins' if from_histograms else 'all-point 65536-bin nonuniform histograms; exact NumPy percentiles for bins with <100 points'),
            'mean_and_x_bins':'unchanged from previous CSV; per-bin counts verified exactly',
            'empty_bins':'NaN range; omitted from plot','spatial_resampling':False}
        (out/f'frame_{number:06d}_metadata.json').write_text(json.dumps(metadata,indent=2))
    print(f'Completed {coverage*100:g}% value-range bands',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    parser.add_argument('--coverage',type=float,default=.5)
    parser.add_argument('--from-histograms',action='store_true')
    args=parser.parse_args()
    run(args.run_dir,args.coverage,args.from_histograms)
