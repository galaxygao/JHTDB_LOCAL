"""Render exact cavity labels without printing/loading asset contents into chat.

Binary inputs are consumed by this script only. Blue surfaces use occupied blocks
for display; cavity meshes retain original voxel resolution. Counts are exact.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio


def coordinates(path, n):
    p = np.fromfile(path, dtype=np.uint32)
    return np.column_stack((p % n, (p // n) % n, p // (n*n))).astype(np.int32)


def periodic_origin(xyz, n, step=1):
    """Put the display cut in the largest empty circular gap, if available.

    Otherwise choose an aligned low-occupancy plane; residual cuts are explicit.
    This is a periodic translation, not an inference of non-winding topology.
    """
    origin=[]; diagnostics=[]
    for axis in range(3):
        counts=np.bincount(xyz[:,axis],minlength=n)
        occupied=np.flatnonzero(counts)
        gaps=(np.roll(occupied,-1)-occupied-1)%n
        k=int(np.argmax(gaps)); gap=int(gaps[k])
        if gap:
            cut=int((occupied[k]+1+gap//2)%n)
        else:
            candidates=np.arange(0,n,step)
            score=counts[candidates]+counts[(candidates-1)%n]
            cut=int(candidates[np.argmin(score)])
        origin.append(cut)
        diagnostics.append(dict(axis='xyz'[axis],cut=cut,empty_gap=gap,
                                residual_cut_possible=not bool(gap)))
    return np.array(origin,dtype=np.int32),diagnostics


def periodic_translate(xyz, origin, n):
    return (xyz-origin)%n+origin


def shared_origin(folder, rows, n, step=8):
    """One periodic chart for all structures: never reposition ranks separately."""
    hist=[]
    for row in rows:
        p=np.fromfile(folder/f"blue_{row['rank']}.bin",dtype=np.uint32)
        hist.append([np.bincount((p//d)%n,minlength=n) for d in (1,n,n*n)])
    origin=[];report=[]
    for axis in range(3):
        candidates=np.arange(0,n,step)
        smaller=np.sum([h[axis] for h in hist[1:]],axis=0) if len(hist)>1 else np.zeros(n)
        small_score=smaller[candidates]+smaller[(candidates-1)%n]
        eligible=candidates[small_score==small_score.min()]
        big=hist[0][axis]
        cut=int(eligible[np.argmin(big[eligible]+big[(eligible-1)%n])])
        origin.append(cut)
        report.append(dict(axis='xyz'[axis],cut=cut,
            neighboring_plane_counts=[int(h[axis][cut]+h[axis][(cut-1)%n]) for h in hist]))
    return np.array(origin,dtype=np.int32),report


def seam_mesh(xyz, step, origin, n, vertices, faces):
    """Mark the translated opposite periodic face and any residual outer caps."""
    verts=[];tris=[];offset=0
    for axis in range(3):
        other=[a for a in range(3) if a!=axis]
        left=xyz[(xyz[:,axis]>=n-step)&(xyz[:,axis]<n)]
        right=xyz[(xyz[:,axis]>=n)&(xyz[:,axis]<n+step)]
        if not len(left) or not len(right):continue
        # Match occupied blocks on both sides of the original periodic seam.
        scale=2*n//step+2
        a=left[:,other]//step;b=right[:,other]//step
        common=np.intersect1d(a[:,0].astype(np.int64)*scale+a[:,1],
                              b[:,0].astype(np.int64)*scale+b[:,1])
        if not len(common):continue
        xy=np.column_stack((common//scale,common%scale))*step-.5
        v=np.zeros((len(xy),4,3),dtype=np.float32);v[:,:,axis]=n-.5
        v[:,:,other[0]]=xy[:,0,None];v[:,:,other[1]]=xy[:,1,None]
        v[:,1,other[0]]+=step;v[:,2,other[0]]+=step
        v[:,2,other[1]]+=step;v[:,3,other[1]]+=step
        f=np.tile([[0,1,2],[0,2,3]],(len(xy),1))
        f+=np.repeat(np.arange(len(xy))*4+offset,2)[:,None]
        verts.append(v.reshape(-1,3));tris.append(f);offset+=len(xy)*4
    cap=np.zeros(len(faces),dtype=bool)
    for axis in range(3):
        for edge in (origin[axis]-.5,origin[axis]+n-.5):
            cap|=np.all(np.isclose(vertices[faces,axis],edge),axis=1)
    if cap.any():
        verts.append(vertices);tris.append(faces[cap]+offset)
    if not verts:return np.empty((0,3)),np.empty((0,3),dtype=np.int32),cap
    return np.concatenate(verts),np.concatenate(tris).astype(np.int32),cap


def mesh(xyz, step, n, periodic=False):
    if len(xyz) == 0:
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.int32)
    cells = np.unique(xyz // step, axis=0)
    lo = cells.min(0)
    shape = cells.max(0) - lo + 3
    grid = np.zeros(shape, dtype=bool)
    local = cells - lo + 1
    grid[tuple(local.T)] = True
    vertices, faces = [], []
    count = 0
    # Cut surfaces at the displayed box boundary; periodic connectivity was
    # determined on the original grid and is not inferred from this mesh.
    for axis in range(3):
        others = [i for i in range(3) if i != axis]
        for sign in (-1, 1):
            adj = local.copy(); adj[:, axis] += sign
            occupied=grid[tuple(adj.T)]
            if periodic:
                boundary=cells[:,axis]==(0 if sign<0 else n//step-1)
                wrapped=local[boundary].copy()
                wrapped[:,axis]=(n//step-1 if sign<0 else 0)-lo[axis]+1
                valid=np.all((wrapped>=1)&(wrapped<shape-1),axis=1)
                values=np.zeros(len(wrapped),dtype=bool)
                values[valid]=grid[tuple(wrapped[valid].T)]
                occupied[boundary]=values
            exposed = cells[~occupied]
            if not len(exposed):
                continue
            v = np.repeat(exposed[:, None, :].astype(np.float32), 4, axis=1)
            v[:, :, axis] += int(sign == 1)
            v[:, 1, others[0]] += 1
            v[:, 2, others[0]] += 1; v[:, 2, others[1]] += 1
            v[:, 3, others[1]] += 1
            v = np.minimum(v * step - .5, n - .5)
            f = np.tile([[0, 1, 2], [0, 2, 3]], (len(exposed), 1))
            f += np.repeat(np.arange(len(exposed))*4 + count, 2)[:, None]
            vertices.append(v.reshape(-1, 3)); faces.append(f)
            count += len(exposed)*4
    vertices = np.concatenate(vertices)
    faces = np.concatenate(faces).astype(np.int32)
    vertices, inverse = np.unique(vertices, axis=0, return_inverse=True)
    return vertices, inverse[faces].astype(np.int32)


def periodic_extensions(vertices, faces, n, halo):
    """Tile only surface triangles in the visible halo; leave seams uncapped."""
    buckets=[([],[]) for _ in range(4)]
    if not len(faces):return []
    triangles=vertices[faces]
    low=triangles.min(axis=1);high=triangles.max(axis=1)
    middle=(low+high)/2
    for dx in (-1,0,1):
        for dy in (-1,0,1):
            for dz in (-1,0,1):
                if not(dx or dy or dz):continue
                shift=np.array([dx,dy,dz],dtype=np.float32)*n
                keep=np.all(low+shift>=-halo-.5,axis=1)&np.all(high+shift<=n+halo-.5,axis=1)
                ids=np.flatnonzero(keep)
                if not len(ids):continue
                c=middle[ids]+shift
                depth=np.maximum(np.maximum(-.5-c,c-(n-.5)),0).max(axis=1)
                band=np.minimum((depth/(halo/4)).astype(int),3)
                for k in range(4):
                    selected=faces[ids[band==k]]
                    if not len(selected):continue
                    unique,inverse=np.unique(selected,return_inverse=True)
                    vs,fs=buckets[k]
                    offset=sum(len(v) for v in vs)
                    vs.append(vertices[unique]+shift);fs.append(inverse.reshape(-1,3)+offset)
    return [(k,np.concatenate(vs),np.concatenate(fs).astype(np.int32))
            for k,(vs,fs) in enumerate(buckets) if vs]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('directory', type=Path)
    ap.add_argument('--n', type=int, default=1024); args = ap.parse_args()
    folder, n = args.directory, args.n
    selection_path = folder.parent / 'selection.json'
    selection = json.loads(selection_path.read_text()) if selection_path.exists() else None
    threshold_label = (f"α={selection['identity']['alpha']:g}, β={selection['identity']['beta']:g} · "
                       if selection else '')
    rows = list(csv.DictReader((folder/'statistics.csv').open()))
    fig = go.Figure(); metadata = []; boxes = []; groups = []; zooms = []
    projection = []; halo=n//4; extension_indices=[]
    for row in rows:
        rank = int(row['rank']); channels = {}; global_indices=[]
        for name, color, opacity in [('blue', '#2588e6', .18), ('green', '#00bb40', 1.), ('red', '#ed2323', 1.)]:
            xyz = coordinates(folder/f'{name}_{rank}.bin', n)
            if name == 'blue':
                step = 8 if len(xyz)>2_000_000 else 1
                origin=np.zeros(3,dtype=np.int32)
                unwrapping=[dict(mode='periodic surface with surrounding images')]
                blue_xyz = xyz
                lo = xyz.min(0); hi = xyz.max(0); boxes.append((lo, hi))
                print(f'periodic rank={rank} minority-piece origin={origin.tolist()}',flush=True)
            else:
                step = 1
                xyz=periodic_translate(xyz,origin,n)
            vertices, faces = mesh(xyz-origin, step, n, periodic=True)
            vertices+=origin
            channels[name] = xyz if name!='blue' else xyz[::max(1,len(xyz)//100000)]
            global_indices.append(len(fig.data))
            fig.add_trace(go.Mesh3d(x=vertices[:,0], y=vertices[:,1], z=vertices[:,2],
                i=faces[:,0], j=faces[:,1], k=faces[:,2], color=color, opacity=opacity,
                name=f'#{rank} {name} ({len(xyz):,} points)', visible=rank==1,
                flatshading=True, hoverinfo='name', showscale=False,
                lighting=dict(ambient=.8, diffuse=.6, specular=.1)))
            for band,v,f in periodic_extensions(vertices,faces,n,halo):
                fade=[2/3,4/9,2/9,1/12][band]
                idx=len(fig.data);extension_indices.append(idx);global_indices.append(idx)
                fig.add_trace(go.Mesh3d(x=v[:,0],y=v[:,1],z=v[:,2],i=f[:,0],j=f[:,1],k=f[:,2],
                    color=color,opacity=opacity*fade,visible=rank==1,showlegend=False,
                    name=f'#{rank} {name} periodic continuation {band+1}',
                    meta=dict(periodic_extension=True,channel=name,fade=fade),
                    flatshading=True,hoverinfo='name',lighting=dict(ambient=.8,diffuse=.6,specular=.1)))
            metadata.append(dict(rank=rank, channel=name, exact_points=len(xyz),
                                 display_block=step, triangles=len(faces),
                                 periodic_origin=origin.tolist(),unwrapping=unwrapping))
            print(f'render rank={rank} channel={name} count={len(xyz)} block={step} triangles={len(faces)}', flush=True)
        groups.append(global_indices)
        projection.append(channels)
        cavity = np.concatenate([channels['green'],channels['red']])
        if len(cavity):
            remaining=set(map(tuple,(cavity%n).tolist())); largest=[]
            while remaining:
                seed=remaining.pop(); comp=[seed]
                for x,y,z in comp:
                    for dx in (-1,0,1):
                        for dy in (-1,0,1):
                            for dz in (-1,0,1):
                                p=((x+dx)%n,(y+dy)%n,(z+dz)%n)
                                if p in remaining:remaining.remove(p);comp.append(p)
                if len(comp)>len(largest):largest=comp
            center=periodic_translate(np.array(largest[0]),origin,n)
            # Minimum-image coordinates keep boundary-crossing closeups intact.
            local_cavity=(np.array(largest)-center+n//2)%n-n//2
            low=local_cavity.min(0)-5;high=local_cavity.max(0)+5
            zstart=len(fig.data)
            for name,col,opacity in [('blue','#2588e6',.18),('green','#00bb40',1.),('red','#ed2323',1.)]:
                original=blue_xyz if name=='blue' else channels[name]
                local=(original-center+n//2)%n-n//2
                local=local[np.all((local>=low)&(local<=high),axis=1)]
                v,f=mesh(local-low,1,int((high-low).max())+1)
                if len(v):v+=low+center
                fig.add_trace(go.Mesh3d(x=v[:,0],y=v[:,1],z=v[:,2],i=f[:,0],j=f[:,1],k=f[:,2],
                    color=col,opacity=opacity,name=f'#{rank} cavity closeup {name}',visible=False,
                    flatshading=True,hoverinfo='name',lighting=dict(ambient=.8,diffuse=.6)))
            zooms.append((rank,list(range(zstart,zstart+3)),low+center,high+center))
    # Reference cube clarifies which geometry is the counted primary domain.
    box_xyz=[]
    for axis in range(3):
        other=[a for a in range(3) if a!=axis]
        for a in (-.5,n-.5):
            for b in (-.5,n-.5):
                v=np.zeros((2,3));v[:,axis]=[-.5,n-.5];v[:,other[0]]=a;v[:,other[1]]=b
                box_xyz.extend([v[0].tolist(),v[1].tolist(),[None,None,None]])
    box_xyz=list(zip(*box_xyz));box_index=len(fig.data)
    fig.add_trace(go.Scatter3d(x=box_xyz[0],y=box_xyz[1],z=box_xyz[2],mode='lines',
        line=dict(color='#777777',width=2),name='Primary periodic box',hoverinfo='skip'))
    for group in groups:group.append(box_index)
    buttons = []
    shared_low=np.full(3,-halo-.5)
    shared_high=np.full(3,n+halo-.5)
    shared_ranges={f'{a}axis.range':[float(shared_low[k]),float(shared_high[k])]
                   for k,a in enumerate('xyz')}
    for i, row in enumerate(rows):
        buttons.append(dict(label=f"Rank {i+1} · {int(row['structure_points']):,} points",method='update',
            args=[{'visible':[j in groups[i] for j in range(len(fig.data))]},
                  {f'scene.{k}':v for k,v in shared_ranges.items()}]))
    for rank,indices,low,high in zooms:
        buttons.append(dict(label=f'Rank {rank} · largest cavity (exact local surface)',method='update',
            args=[{'visible':[j in indices for j in range(len(fig.data))]},
                  {f'scene.{a}axis.range':[int(low[k])-1,int(high[k])+1] for k,a in enumerate('xyz')}]))
    normal=sum(groups,[])
    buttons.append(dict(label='Top 3 together (shared coordinates)',method='update',args=[{'visible':[j in normal for j in range(len(fig.data))]},
        {f'scene.{k}':v for k,v in shared_ranges.items()}]))
    fig.update_layout(title=threshold_label+'r = Δx · stitched periodic structures · shared axis ranges',
        scene=dict(aspectmode='data',xaxis_title='x / Δx',yaxis_title='y / Δx',zaxis_title='z / Δx'),
        updatemenus=[dict(buttons=buttons,x=0,y=1.10)],margin=dict(l=0,r=0,b=0,t=100),
        legend=dict(x=0,y=0),paper_bgcolor='white')
    fig.update_layout(**{f'scene.{k}':v for k,v in shared_ranges.items()})
    blue_traces=[i for i,t in enumerate(fig.data) if 'blue' in t.name]
    fig.update_layout(sliders=[dict(active=2,currentvalue={'prefix':'Blue opacity: '},
        x=.55,len=.4,y=0,steps=[dict(label=str(v),method='restyle',args=[{'opacity':[v*((fig.data[i].meta or {}).get('fade',1)) for i in blue_traces]},blue_traces])
                              for v in [0,.08,.18,.35,.6]])])
    (folder/'view_ranges.json').write_text(json.dumps(dict(global_ranges=shared_ranges,views=len(buttons),purple=False,periodic_halo=halo,extension_traces=len(extension_indices)),indent=2))
    html = pio.to_html(fig, include_plotlyjs=True, full_html=True,
                      config={'displaylogo':False}, div_id='cavities',post_script="""
    const gd=document.getElementById('cavities');
    function applyExtension(){
      const enabled=document.getElementById('periodic-toggle').checked;
      const slider=gd.layout.sliders[0];
      const blue=Number(slider.steps[slider.active].label);
      const ids=[],values=[];
      gd.data.forEach((t,i)=>{if(t.meta&&t.meta.periodic_extension){
        ids.push(i);values.push(enabled?(t.meta.channel==='blue'?blue:1)*t.meta.fade:0);
      }});
      if(ids.length)Plotly.restyle(gd,{opacity:values},ids);
    }
    document.getElementById('periodic-toggle').addEventListener('change',applyExtension);
    gd.on('plotly_sliderchange',()=>setTimeout(applyExtension,0));
    """)
    note = '''<div style="font:15px sans-serif;padding:12px;max-width:1100px">
    <b>蓝色半透明：所选连通结构；绿色不透明：封闭空腔内其他过阈值分量；红色不透明：空腔内未过阈值点。</b>
    <br><label><input id="periodic-toggle" type="checkbox" checked>显示周期延伸</label>　下拉框提供结构、合并及可用的空腔局部视图。拖动旋转、滚轮缩放。
    <br>主周期盒为0–1024，盒外延伸256格；蓝色及空腔的周期副本跨面、棱、角连续接合，分四层逐渐变淡。周期接合处不加封口、不标紫色。外缘仍是显示截断，结构会周期继续。副本不重复计数。
    <br>分类使用原始网格及周期边界：结构采用6邻域，背景采用26邻域；最大背景分量为外部，其他具有周期绕行的背景分量也排除。
    绿色表示同时通过两个阈值。超过200万点的结构，其全局蓝色表面按8格占据块简化，可能加厚细枝或遮盖小孔；其余结构及红绿空腔保持原始格点分辨率。
    下拉框的 largest cavity 视图以原始分辨率展示各结构最大的空腔及附近蓝色结构；蓝色在局部视图边缘被裁切，坐标按周期展开。
    展开后可能出现负坐标或超过1023的坐标；坐标取模1024后对应原始位置。
    三个结构的全局视图使用完全相同的x、y、z坐标范围，便于比较大小；只有局部放大视图改变范围。
    空腔数为零时不添加任何红绿区域。</div>'''
    html=html.replace('<body>','<body>'+f'<div style="font:16px sans-serif;padding:12px">{threshold_label}r = Δx</div>'+note)
    (folder/'top3_cavities.html').write_text(html)
    (folder/'render_metadata.json').write_text(json.dumps(metadata,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig2, axes=plt.subplots(1,len(rows),figsize=(16,5),squeeze=False)
    for i,(ax,channels,row) in enumerate(zip(axes[0],projection,rows)):
        for name,col,alpha,size in [('blue','#2588e6',.08,.2),('green','#00bb40',1,5),('red','#ed2323',1,5)]:
            xyz=channels[name]
            if len(xyz):ax.scatter(xyz[:,0],xyz[:,1],s=size,c=col,alpha=alpha,rasterized=True,label=name)
        ax.set_aspect('equal');ax.set_title(f"Rank {i+1}: {int(row['structure_points']):,} points\nCavities: {row['cavity_count']} | green: {row['green_points']} | red: {row['red_points']}")
        ax.set_xlabel('x / dx');ax.set_ylabel('y / dx')
        ax.set_xlim(shared_low[0],shared_high[0])
        ax.set_ylim(shared_low[1],shared_high[1])
    fig2.suptitle('XY projections of primary box — see HTML for periodic continuation')
    fig2.tight_layout();fig2.savefig(folder/'preview.png',dpi=160);plt.close(fig2)


if __name__=='__main__': main()
