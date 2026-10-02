"""Full-domain bidirectional conditional means with central and logarithmic tail panels."""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import numpy as np
import zarr
from jhtdb_pipeline.store import spatial_slices


def quantile_from_hist(counts, edges, probability):
    cumulative=np.cumsum(counts)
    target=probability*cumulative[-1]
    index=min(int(np.searchsorted(cumulative,target,side='left')),len(counts)-1)
    previous=cumulative[index-1] if index else 0
    fraction=(target-previous)/counts[index] if counts[index] else 0
    return float(edges[index]+fraction*(edges[index+1]-edges[index]))


def tail_edges(lo,hi,n):
    if lo*hi>0:
        return np.sign(lo)*np.geomspace(abs(lo),abs(hi),n+1)
    return np.linspace(lo,hi,n+1)


def bin_statistics(x,y,edges):
    index=np.searchsorted(edges,x.ravel(),side='right')-1
    index[x.ravel()==edges[-1]]=len(edges)-2
    if np.any(index<0) or np.any(index>=len(edges)-1):
        raise ValueError('A data point lies outside the bins')
    count=np.bincount(index,minlength=len(edges)-1)
    sums=np.bincount(index,weights=y.ravel(),minlength=len(edges)-1)
    return count,sums


def fields(velocity,gradient,qr,um):
    chunks=tuple(min(128,n) for n in velocity.shape[1:])
    blocks=list(spatial_slices(velocity.shape[1:],chunks))
    for i,key in enumerate(blocks,1):
        u=velocity[(slice(None),*key)];g=gradient[(slice(None),*key)]
        q=-np.einsum('izyx,izyx->zyx',u,g,optimize=True)
        u2=np.einsum('izyx,izyx->zyx',u,u,optimize=True)
        if not np.isfinite(q).all() or not np.isfinite(u2).all():
            raise ValueError('Nonfinite inputs')
        if i%64==0: print(f'  {i}/{len(blocks)} blocks',flush=True)
        yield q.astype(np.float64)/qr,u2.astype(np.float64)/um


def plot(rows,direction,destination,min_count,shape,frame_time):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, NullFormatter
    reverse=direction=='u2_given_q'
    xlabel=r'$q/q_{\mathrm{rms}}$' if reverse else r'$u^2/\langle u^2\rangle$'
    ylabel=r'$\langle u^2\mid q\rangle/\langle u^2\rangle$' if reverse else r'$\langle q\mid u^2\rangle/q_{\mathrm{rms}}$'
    fig,axes=plt.subplots(2,3,figsize=(15,8),gridspec_kw={'height_ratios':[2.5,1],'width_ratios':[1,1.7,1]},layout='constrained')
    for col,region in enumerate(('lower_tail','center','upper_tail')):
        subset=[r for r in rows if r['region']==region]
        left=np.array([r['bin_left'] for r in subset]);right=np.array([r['bin_right'] for r in subset])
        x=np.array([r['bin_center'] for r in subset]);y=np.array([r['conditional_mean_normalized'] for r in subset])
        count=np.array([r['count'] for r in subset]);volume=np.array([r['volume_fraction']*100 for r in subset])
        color='#2563a6' if region=='center' else '#c33434'
        top,bottom=axes[:,col]
        valid=count>=min_count; sparse=(count>0)&~valid
        has_range='value_lower' in subset[0] or 'value_p025' in subset[0]
        coverage=float(subset[0].get('value_coverage',.95))
        percentage=f'{coverage*100:g}'
        if has_range:
            lower=np.array([float(r['value_lower'] if 'value_lower' in r else r['value_p025']) for r in subset]);upper=np.array([float(r['value_upper'] if 'value_upper' in r else r['value_p975']) for r in subset])
            top.fill_between(x,lower,upper,where=count>0,color=color,alpha=.18,label=f'{(1-coverage)*50:g}–{(1+coverage)*50:g} percentiles')
            top.plot(x,lower,color=color,lw=.6,alpha=.5)
            top.plot(x,upper,color=color,lw=.6,alpha=.5)
        top.plot(x,np.where(valid,y,np.nan),color=color,lw=1.7,marker='o',ms=3,label=f'Bin mean (n >= {min_count})')
        if sparse.any():top.scatter(x[sparse],y[sparse],facecolors='none',edgecolors=color,marker='o',s=35,label=f'0 < n < {min_count}')
        top.axhline(1 if reverse else 0,color='#666',lw=.8,ls='--')
        bottom.bar(left,volume,width=right-left,align='edge',color=color,alpha=.65,edgecolor='white',linewidth=.3)
        for ax in (top,bottom):
            ax.set_xlim(left[0],right[-1]);ax.grid(True,alpha=.2);ax.tick_params(labelsize=9)
            if region!='center' and left[0]*right[-1]>0:
                if right[-1]<0:
                    ax.set_xscale('symlog',linthresh=abs(right[-1])/2)
                else:ax.set_xscale('log')
                ticks=np.sign(left[0])*np.geomspace(abs(left[0]),abs(right[-1]),4)
                ax.set_xticks(ticks);ax.xaxis.set_major_formatter(FuncFormatter(lambda value,pos:f'{value:.3g}'))
                ax.xaxis.set_minor_formatter(NullFormatter())
        if region!='center':bottom.set_yscale('log')
        top.set_ylabel((r'$u^2/\langle u^2\rangle$' if reverse else r'$q/q_{\mathrm{rms}}$')+f'\n(mean and {percentage}% value range)' if has_range else ylabel);bottom.set_ylabel('Volume per bin (%)'+ ('\nlog y' if region!='center' else ''))
        bottom.set_xlabel(xlabel)
        title={'center':'Central 95% | linear x','lower_tail':'Lower 2.5% | logarithmic x','upper_tail':'Upper 2.5% | logarithmic x'}[region]
        top.set_title(title+f'\nActual volume: {volume.sum():.4f}%',fontsize=11)
        if sparse.any() or has_range:top.legend(fontsize=7,loc='best')
    fig.suptitle(('Velocity squared conditioned on pressure power' if reverse else 'Pressure power conditioned on velocity squared')+f'\nFull {shape[2]} × {shape[1]} × {shape[0]} frame, t = {frame_time:g}; full tails retained',fontsize=15)
    fig.supxlabel((f'Shading: central {percentage}% of point values within each bin, NOT a confidence interval for the mean.\n' if has_range else '')+'Independent linear y limits per panel. Bars: volume per bin. Hollow means: fewer than 100 cells.',fontsize=9)
    fig.savefig(destination.with_suffix('.png'),dpi=180)
    fig.savefig(destination.with_suffix('.pdf'))
    plt.close(fig)


def run(folder):
    config=json.loads((folder/'config_used.json').read_text())
    with (folder/'run_summary.csv').open() as handle:
        summaries={int(r['frame']):r for r in csv.DictReader(handle)}
    out=folder/'conditional_tails';out.mkdir(exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(Path('.local/cache/matplotlib').resolve()))
    for frame in config['frames']:
        number=int(frame['frame']); summary=summaries[number]
        qr,um=float(summary['q_rms']),float(summary['u2_mean'])
        roots=[zarr.open_group(frame[k],mode='r') for k in ('velocity_path','pressure_gradient_path')]
        for root in roots:
            if root.attrs.get('status')!='validated' or root.attrs.get('time_index')!=number or root.attrs.get('physical_time')!=frame['time']:
                raise ValueError('Unvalidated or mismatched input')
        u=roots[0][frame.get('velocity_key','velocity')];g=roots[1][frame['pressure_gradient_keys'][0]]
        if u.shape!=g.shape:raise ValueError('Input shapes differ')
        grid_count=int(np.prod(u.shape[1:]))
        fine_edges={}
        for name,scale in (('q',qr),('u2',um)):
            lo,hi=float(summary[name+'_min'])/scale,float(summary[name+'_max'])/scale
            margin=max(abs(lo),abs(hi),1)*1e-5
            fine_edges[name]=np.linspace(lo-margin,hi+margin,131073)
        counts={name:np.zeros(131072,dtype=np.int64) for name in fine_edges}
        ranges={name:[float('inf'),float('-inf')] for name in fine_edges}
        print('Pass 1: full-grid quantile histograms',flush=True)
        for q,u2 in fields(u,g,qr,um):
            for name,x in (('q',q),('u2',u2)):
                counts[name]+=np.histogram(x,bins=fine_edges[name])[0]
                ranges[name][0]=min(ranges[name][0],float(x.min()));ranges[name][1]=max(ranges[name][1],float(x.max()))
        plans={}
        for name in fine_edges:
            if counts[name].sum()!=grid_count:raise ValueError('Quantile histogram omitted data')
            lower=quantile_from_hist(counts[name],fine_edges[name],.025)
            upper=quantile_from_hist(counts[name],fine_edges[name],.975)
            lo,hi=ranges[name]
            if not lo<lower<upper<hi:raise ValueError('Degenerate quantile ranges')
            edges=np.concatenate([tail_edges(lo,lower,20)[:-1],np.linspace(lower,upper,61)[:-1],tail_edges(upper,hi,20)])
            plans[name]=dict(edges=edges,lower=lower,upper=upper,count=np.zeros(100,dtype=np.int64),sums=np.zeros(100))
        print('Pass 2: both conditional directions, including all tails',flush=True)
        for q,u2 in fields(u,g,qr,um):
            for name,x,y in (('q',q,u2),('u2',u2,q)):
                c,s=bin_statistics(x,y,plans[name]['edges']);plans[name]['count']+=c;plans[name]['sums']+=s
        metadata={'frame':number,'time':frame['time'],'grid_count':grid_count,'central_probability':.95,
                  'quantiles':'interpolated from 131072 equal-width full-grid histogram bins; approximate boundaries',
                  'statistics':'exact membership and float64 sums over every grid point; no sampling',
                  'volume':'count / full-domain count (bin mass, not density)', 'plots':{}}
        for name,direction in (('q','u2_given_q'),('u2','q_given_u2')):
            plan=plans[name]; edges=plan['edges'];rows=[]
            if plan['count'].sum()!=grid_count:raise ValueError('Conditional bins omitted data')
            for i,(lo,hi,count,total) in enumerate(zip(edges[:-1],edges[1:],plan['count'],plan['sums'])):
                region='lower_tail' if i<20 else 'center' if i<80 else 'upper_tail'
                center=np.sign(lo)*np.sqrt(abs(lo*hi)) if region!='center' and lo*hi>0 else (lo+hi)/2
                rows.append(dict(region=region,bin_left=lo,bin_right=hi,bin_center=center,count=int(count),volume_fraction=count/grid_count,
                                 conditional_mean_normalized=total/count if count else float('nan'),reliable_count=bool(count>=100)))
            prefix=out/f'frame_{number:06d}_{direction}'
            with prefix.with_suffix('.csv').open('w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
            metadata['plots'][direction]=dict(lower=plan['lower'],upper=plan['upper'],minimum=ranges[name][0],maximum=ranges[name][1],
                quantile_histogram_bin_width=float(fine_edges[name][1]-fine_edges[name][0]),
                volumes={region:sum(r['volume_fraction'] for r in rows if r['region']==region) for region in ('lower_tail','center','upper_tail')})
            plot(rows,direction,prefix,100,u.shape[1:],frame['time'])
        (out/f'frame_{number:06d}_metadata.json').write_text(json.dumps(metadata,indent=2))
    print(f'Completed: {out}',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',required=True,type=Path)
    run(parser.parse_args().run_dir)
