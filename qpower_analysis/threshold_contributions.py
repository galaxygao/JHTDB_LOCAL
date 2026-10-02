"""Exact full-grid threshold contributions with bounded-memory Zarr reads."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import numpy as np
import zarr
from jhtdb_pipeline.store import spatial_slices


def histograms(q, u2, q_rms, u2_mean, alphas, betas):
    ai = np.zeros(q.shape, dtype=np.int8)
    bi = np.zeros(q.shape, dtype=np.int8)
    for a in alphas:
        ai += q > a * q_rms
    for b in betas:
        bi += u2 > b * u2_mean
    index = (ai.astype(np.int32) * (len(betas)+1) + bi).ravel()
    shape = (len(alphas)+1, len(betas)+1)
    size = shape[0]*shape[1]
    result = {'count': np.bincount(index, minlength=size).reshape(shape)}
    weights = {'u2': u2, 'q_positive': np.maximum(q, 0),
               'q_negative_magnitude': np.maximum(-q, 0), 'q_squared': np.square(q, dtype=np.float64)}
    for name, values in weights.items():
        result[name] = np.bincount(index, weights=values.ravel(), minlength=size).reshape(shape)
    return result


def run(folder):
    config = json.loads((folder/'config_used.json').read_text())
    if config.get('event_mode', 'positive') != 'positive':
        raise ValueError('This contribution report uses positive q events')
    alphas, betas = sorted(config['alphas']), sorted(config['betas'])
    if len(set(alphas)) != len(alphas) or len(set(betas)) != len(betas):
        raise ValueError('Thresholds must be unique')
    with (folder/'run_summary.csv').open(newline='') as handle:
        summaries = {int(row['frame']): row for row in csv.DictReader(handle)}
    with (folder/'overlap_statistics.csv').open(newline='') as handle:
        overlap = {(int(r['frame']),float(r['alpha']),float(r['beta'])):r for r in csv.DictReader(handle)}
    rows, totals = [], []
    for frame in config['frames']:
        number = int(frame['frame'])
        velocity_root = zarr.open_group(frame['velocity_path'],mode='r')
        gradient_root = zarr.open_group(frame['pressure_gradient_path'],mode='r')
        for root in (velocity_root, gradient_root):
            if root.attrs.get('status') != 'validated' or root.attrs.get('time_index') != number or root.attrs.get('physical_time') != frame['time']:
                raise ValueError('Input must be a validated matching frame')
        velocity = velocity_root[frame.get('velocity_key','velocity')]
        gradient = gradient_root[frame['pressure_gradient_keys'][0]]
        if velocity.shape != gradient.shape:
            raise ValueError('Input shapes differ')
        summary = summaries[number]
        qr, um = float(summary['q_rms']), float(summary['u2_mean'])
        accumulated = {}
        chunks = tuple(min(128,n) for n in velocity.shape[1:])
        blocks = list(spatial_slices(velocity.shape[1:],chunks))
        for i, key in enumerate(blocks,1):
            u = velocity[(slice(None),*key)]; g = gradient[(slice(None),*key)]
            q = -np.einsum('izyx,izyx->zyx',u,g,optimize=True)
            u2 = np.einsum('izyx,izyx->zyx',u,u,optimize=True)
            if not np.isfinite(q).all() or not np.isfinite(u2).all():
                raise ValueError('Nonfinite source field')
            for name, values in histograms(q,u2,qr,um,alphas,betas).items():
                if name not in accumulated: accumulated[name] = values
                else: accumulated[name] += values
            if i%16 == 0 or i==len(blocks): print(f'Frame {number}: {i}/{len(blocks)} blocks',flush=True)
        accumulated['q_absolute'] = accumulated['q_positive'] + accumulated['q_negative_magnitude']
        total = {name:float(values.sum()) for name,values in accumulated.items()}
        totals.append(dict(frame=number,time=frame['time'],**total))
        selections = [('A',a,'',i+1,0) for i,a in enumerate(alphas)]
        selections += [('B','',b,0,j+1) for j,b in enumerate(betas)]
        selections += [('intersection',a,b,i+1,j+1) for i,a in enumerate(alphas) for j,b in enumerate(betas)]
        for region,a,b,ai,bi in selections:
            sums = {name:float(values[ai:,bi:].sum()) for name,values in accumulated.items()}
            if region == 'intersection':
                reference = overlap[(number,float(a),float(b))]
                if int(sums['count']) != int(reference['intersection_count']):
                    raise ValueError('Threshold membership differs from existing overlap statistics')
            row = dict(frame=number,time=frame['time'],region=region,alpha=a,beta=b,
                       count=int(sums['count']),volume_fraction=sums['count']/total['count'])
            for name in ('u2','q_positive','q_negative_magnitude','q_absolute','q_squared'):
                row[name+'_sum'] = sums[name]
                row[name+'_fraction'] = sums[name]/total[name] if total[name] else float('nan')
            row['q_net_sum'] = sums['q_positive']-sums['q_negative_magnitude']
            rows.append(row)
    for name, records in [('threshold_contributions.csv',rows),('contribution_totals.csv',totals)]:
        path = folder/name
        temp = path.with_suffix('.csv.partial')
        with temp.open('w',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
        temp.replace(path)
    (folder/'contribution_metadata.json').write_text(json.dumps(dict(
        scope='all grid points; no sampling',summation='float64 weighted histograms',
        thresholds='reuse q_rms and u2_mean from the existing run summary',
        q_definition='-u dot grad(P)',net_q_fraction='not used: near-zero signed denominator',
        energy_fraction='u2 fraction equals kinetic-energy fraction for constant density',
        overlapping_thresholds='nested regions; fractions must not be added across thresholds'),indent=2))
    print('Saved threshold_contributions.csv',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    run(parser.parse_args().run_dir)
