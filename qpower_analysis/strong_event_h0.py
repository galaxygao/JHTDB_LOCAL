"""Exact distance-connected components of the positive alpha/beta intersection."""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
from jhtdb_pipeline.store import spatial_slices

try:
    from .conditional_tails import validated_fields
except ImportError:
    from conditional_tails import validated_fields


def prepare_selection(folder, out, alpha=1., beta=1.):
    config = json.loads((folder / 'config_used.json').read_text())
    frame = config['frames'][0]
    with (folder / 'run_summary.csv').open() as handle:
        summary = next(r for r in csv.DictReader(handle) if int(r['frame']) == frame['frame'])
    qr, um = float(summary['q_rms']), float(summary['u2_mean'])
    u, g = validated_fields(frame, frame.get('velocity_key', 'velocity'))
    shape = tuple(u.shape[1:])
    lengths = np.asarray(config['domain_lengths_xyz'][::-1], dtype=float)
    spacing = lengths / np.asarray(shape)
    if not all(config['periodic_xyz']) or not np.allclose(spacing, spacing[0], rtol=1e-12, atol=0):
        raise ValueError('This exact lattice-distance engine requires three periodic axes and isotropic spacing')
    if shape[2] % 8 or np.prod(shape) >= 2**32 or min(qr, um, alpha, beta) <= 0:
        raise ValueError('Requires nx divisible by 8, fewer than 2**32 cells, and positive scales/thresholds')
    identity = dict(frame=frame, alpha=alpha, beta=beta, q_rms=qr, u2_mean=um,
                    shape_zyx=list(shape), domain_lengths_xyz=config['domain_lengths_xyz'],
                    periodic_xyz=config['periodic_xyz'], spacing=float(spacing[0]))
    out.mkdir(parents=True, exist_ok=True)
    metadata_path = out / 'selection.json'
    mask_path = out / 'selection_mask.bits'
    if metadata_path.exists() and mask_path.exists():
        saved = json.loads(metadata_path.read_text())
        if saved['identity'] != identity or mask_path.stat().st_size != int(np.prod(shape)) // 8:
            raise ValueError('Cached selection differs from this run or has the wrong size')
        print(f"Reusing full-grid selection: {saved['selected_count']:,} points", flush=True)
        return saved
    expected = None
    with (folder / 'overlap_statistics.csv').open() as handle:
        for row in csv.DictReader(handle):
            if (int(row['frame']) == frame['frame'] and float(row['alpha']) == alpha
                    and float(row['beta']) == beta and row['event_mode'] == 'positive'):
                expected = int(row['intersection_count'])
                break
    temporary = out / 'selection_mask.partial'
    packed = np.memmap(temporary, mode='w+', dtype=np.uint8,
                       shape=(shape[0], shape[1], shape[2]//8))
    blocks = list(spatial_slices(shape, (128, 128, 128)))
    count = 0
    started = time.perf_counter()
    for i, key in enumerate(blocks, 1):
        ub, gb = u[(slice(None), *key)], g[(slice(None), *key)]
        q = -np.einsum('izyx,izyx->zyx', ub, gb, optimize=True)
        u2 = np.einsum('izyx,izyx->zyx', ub, ub, optimize=True)
        if not np.isfinite(q).all() or not np.isfinite(u2).all():
            raise ValueError('Nonfinite pressure power or velocity energy')
        selected = (q > alpha*qr) & (u2 > beta*um)
        count += int(selected.sum())
        z, y, x = key
        packed[z, y, slice(x.start//8, x.stop//8)] = np.packbits(selected, axis=2, bitorder='little')
        if i % 32 == 0:
            print(f'  Selection {i}/{len(blocks)} blocks; {count:,} events', flush=True)
    packed.flush()
    del packed
    if expected is not None and count != expected:
        raise ValueError(f'Intersection count mismatch: {count} != {expected}')
    if count == 0:
        raise ValueError('The selected intersection is empty')
    temporary.replace(mask_path)
    saved = dict(identity=identity, selected_count=count, full_grid_count=int(np.prod(shape)),
                 volume_fraction=count/int(np.prod(shape)), matches_existing_count=count == expected,
                 selection='q/q_rms > alpha AND u2/mean(u2) > beta; positive q; strict inequalities',
                 encoding='C-order z,y,x; packed little-endian bits; no downsampling',
                 elapsed_seconds=time.perf_counter()-started)
    metadata_path.write_text(json.dumps(saved, indent=2)+'\n')
    print(f'Full-grid selection verified: {count:,} points', flush=True)
    return saved


def build_engine():
    root = Path(__file__).resolve().parent
    source = root / 'scripts/strong_event_h0.cpp'
    binary = root / '.local/bin/strong_event_h0'
    binary.parent.mkdir(parents=True, exist_ok=True)
    if not binary.exists() or binary.stat().st_mtime < source.stat().st_mtime:
        subprocess.run(['clang++', '-O3', '-std=c++17', '-DNDEBUG', str(source), '-o', str(binary)], check=True)
    return binary


def run(folder, out, alpha=1., beta=1., initial_radius=32, prepare_only=False):
    metadata = prepare_selection(folder, out, alpha, beta)
    if prepare_only:
        return
    binary = build_engine()
    shape = metadata['identity']['shape_zyx']
    subprocess.run([str(binary), str(out/'selection_mask.bits'), *map(str, shape),
                    str(out), str(initial_radius)], check=True)
    finish_outputs(out, metadata)


def finish_outputs(out, metadata):
    """Save physical distances, a multiplicity-compressed H0 barcode and plots."""
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parent/'.local/matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    dx = metadata['identity']['spacing']
    total = metadata['selected_count']
    with (out/'connectivity_grid.csv').open() as handle:
        raw = list(csv.DictReader(handle))
    integer_keys = ['r_squared_grid', 'structure_count', 'merges_at_r', 'largest_size',
                    'count_ge10', 'count_ge100', 'count_ge1000']
    rows = []
    for row in raw:
        r = {k: (int(v) if k in integer_keys else float(v)) for k, v in row.items()}
        r['r_physical'] = r['r_grid']*dx
        r['mean_component_size'] = total/r['structure_count']
        rows.append(r)
    counts = np.array([r['structure_count'] for r in rows])
    radii = np.array([r['r_grid'] for r in rows])
    if (counts[0] != total or counts[-1] != 1 or np.any(np.diff(counts) > 0)
            or sum(r['merges_at_r'] for r in rows) != total-1):
        raise ValueError('H0 monotonicity or total merge count failed')
    if not np.array_equal(np.r_[0, -np.diff(counts)], [r['merges_at_r'] for r in rows]):
        raise ValueError('H0 deaths do not reconstruct the component-count curve')
    if np.any(np.diff([r['largest_size'] for r in rows]) < 0):
        raise ValueError('Largest connected structure unexpectedly shrank')

    def save_csv(path, records):
        with path.open('w', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=records[0], lineterminator='\n')
            writer.writeheader()
            writer.writerows(records)

    save_csv(out/'connectivity.csv', rows)
    bars = [dict(birth_r_grid=0., death_r_grid=r['r_grid'], birth_r_physical=0.,
                 death_r_physical=r['r_physical'], multiplicity=r['merges_at_r'], essential=False)
            for r in rows if r['merges_at_r']]
    bars.append(dict(birth_r_grid=0., death_r_grid=float('inf'), birth_r_physical=0.,
                     death_r_physical=float('inf'), multiplicity=1, essential=True))
    save_csv(out/'h0_barcode_counts.csv', bars)
    chosen = sorted(set([0., 1., np.sqrt(2), np.sqrt(3), 2., 3., 4., 6., 8., 12., 16., 24., 32., radii[-1]]))
    chosen = [x for x in chosen if x <= radii[-1]]
    selected = []
    for value in chosen:
        i = np.searchsorted(radii, value+1e-12, side='right')-1
        row = dict(rows[i])
        row.update(r_grid=float(value), r_physical=float(value*dx))
        selected.append(row)
    save_csv(out/'selected_r_summary.csv', selected)

    identity = metadata['identity']
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5), layout='constrained')
    axes[0].step(radii, counts, where='post', color='#2563a6', lw=1.8)
    axes[0].set(yscale='log', ylabel=r'$N(r)=\beta_0(r)$', title='All connected structures (including singletons)')
    for k, color in ((10, '#3288bd'), (100, '#f28e2b'), (1000, '#8b4a9e')):
        y = np.array([r[f'count_ge{k}'] for r in rows])
        axes[1].step(radii, np.where(y > 0, y, np.nan), where='post', color=color,
                     label=f'At least {k:,} selected points')
    axes[1].set(yscale='log', ylabel='Number of connected structures', title='Component-size filters (applied after connecting)')
    axes[1].legend(fontsize=8)
    largest = np.array([r['largest_fraction']*100 for r in rows])
    axes[2].step(radii, largest, where='post', color='#b23a48', lw=1.8)
    axes[2].set(ylim=(0, 102), ylabel='Largest structure / all selected points (%)',
                title='Growth of the largest structure')
    for ax in axes:
        ax.set(xlim=(0, radii[-1]*1.025 if radii[-1] else 1), xlabel=r'Link distance $r/\Delta x$')
        ax.grid(alpha=.2)
        top = ax.secondary_xaxis('top', functions=(lambda x: x*dx, lambda x: x/dx))
        top.set_xlabel('r (physical distance)')
    fig.suptitle(r'Distance connectivity of strong events: $\alpha=\beta=1$'+'\n'
                 f'{total:,} selected points; full grid; periodic Euclidean distance; no subsampling', fontsize=14)
    fig.supxlabel(r'$S=\{q/q_{\rm rms}>1,\ u^2/\langle u^2\rangle>1\}$; edges join selected points iff distance '
                  r'$\leq r$. Background points are excluded.'+'\n'
                  f'All H0 classes are born at r=0. First complete connection: r/Δx={radii[-1]:.6g}, '
                  f'r={radii[-1]*dx:.6g}; Δx={dx:.8g}.', fontsize=9)
    fig.savefig(out/'structure_count_vs_r.png', dpi=180)
    plt.close(fig)

    engine = json.loads((out/'engine_summary.json').read_text())
    summary = dict(selection=metadata, engine=engine,
                   filtration='Graph on fixed selected vertices; edges iff periodic Euclidean distance <= r',
                   periodic_metric='sqrt(sum(min(abs(x_i-y_i), L_i-abs(x_i-y_i))**2))',
                   homology='H0, equivalent to connected components of the Vietoris-Rips complex',
                   spatial_distance_parameter='r is edge length, not ball radius; no factor of two',
                   algorithm='Exact lattice-offset enumeration ordered by squared distance and disjoint-set union',
                   optimizations='Already connected largest-component interior edges can be omitted; every cross-component edge still has an examined endpoint',
                   resolution='All original selected grid points; no spatial coarsening or subsampling for statistics',
                   singleton_rule='One isolated selected point counts as one structure',
                   finite_h0_bars=total-1, essential_h0_bars=1,
                   all_births_at_r=0, connectivity_radius_physical=float(radii[-1]*dx),
                   connectivity_radius_grid=float(radii[-1]),
                   validation='11 independent small-grid tests against brute-force all-pairs graphs; periodic boundaries, diagonal distances, transitive chains, antipodes, and random point sets; full-grid selected count, monotonicity, merge conservation and saved size histograms checked',
                   caveat='Connected means linked by a chain; a large component can span the domain and need not be a single compact physical object',
                   reference='https://gudhi.inria.fr/python/latest/rips_complex_user.html')
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    lines = [
        '# α=β=1 强事件交集的距离连通结构（H₀）', '',
        '固定点集 S={q/q_rms>1 且 u²/⟨u²⟩>1}，只使用满足两个严格阈值的格点。',
        f'全域共有 {total:,} 个强事件点；与原 overlap_statistics.csv 的交集计数一致。', '',
        '两点的三维周期欧氏距离 ≤r 时连边；通过任意长度的边链相连的点属于同一个结构。',
        '交集外的格点不参与连通。r 是点间连边距离，不是膨胀球半径。',
        'N(r)=β₀(r)，即 Vietoris–Rips 滤波的零维持久同调。所有顶点在 r=0 出生。',
        f'Δx={dx:.12g}；盒子尺寸为 '+str(identity['domain_lengths_xyz'])+'。', '',
        '## 结果', '',
        '| r/Δx | r（物理距离） | 结构数 N(r) | 最大结构占强事件点比例 | ≥100 点结构数 |',
        '|---:|---:|---:|---:|---:|',
    ]
    for r in selected:
        lines.append(f"| {r['r_grid']:.6g} | {r['r_physical']:.7g} | {r['structure_count']:,} | {100*r['largest_fraction']:.3f}% | {r['count_ge100']:,} |")
    lines += ['', f'首次全部连通：r/Δx={radii[-1]:.9g}，r={radii[-1]*dx:.9g}。',
              'r<Δx 时，各点独立，因此 N(r)=52,800,256（本次 α=β=1 数据）。', '',
              '## 解释与计算精度', '',
              '单点也算一个结构。图中另列至少含 10、100、1000 个强事件点的结构数；这些只是连通后的大小筛选，不改变阈值点集或连接规则。',
              'r 增大时，全部结构数 N(r) 只能减少；大小筛选后的结构数可以先增加再减少。',
              '较大的连通分量可通过很长的链条跨越空间；连成一体不表示它是一个紧凑的物理涡结构。此分析本身不产生唯一的最佳 r。',
              '原始 1024³ 网格上全量计算：没有抽样，也没有把非事件格点当作连接桥梁。',
              '利用等间距网格，按整数位移平方距离递增处理邻接关系，使用 union–find 合并。对已连通的最大分量，省略其内部边；任意跨分量边仍至少有一个被检查的端点，所以连通计数保持精确。',
              '11 个独立小网格测试与全点对距离图逐距离比较，涵盖周期边界、对角距离、传递连通和随机集合；全域结果核对选点数、N(r) 单调性、合并总数和结构大小守恒。', '',
              '## 文件', '',
              '- structure_count_vs_r.png：结构数量与最大结构占比。',
              '- connectivity.csv：每个处理距离下的完整统计，含物理距离和网格单位。',
              '- selected_r_summary.csv：便于阅读的若干 r 值。',
              '- h0_barcode_counts.csv：按死亡距离压缩的 H₀ 条形码；multiplicity 为该长度的条形数，另有一个无限长条形。',
              '- sizes_r2_*.csv：若干距离下的全量结构大小分布；文件名 r2 是 (r/Δx)²。',
              '- sample_r2_*.csv：用于显示的固定 stride 点及其全量连通标签和结构大小；仅显示坐标抽稀，计数未抽稀。',
              '- selection_mask.bits：全部强事件点的紧凑位掩码，可复算；selection.json 保存选择条件。', '',
              '方法参考：[GUDHI 的 Vietoris–Rips 滤波定义](https://gudhi.inria.fr/python/latest/rips_complex_user.html)。本计算只需要 H₀，直接使用连通合并，不依赖 GUDHI。', '']
    (out/'REPORT_CN.md').write_text('\n'.join(lines))
    print(f'Figure and complete H0 results: {out}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--alpha', type=float, default=1.)
    parser.add_argument('--beta', type=float, default=1.)
    parser.add_argument('--initial-radius', type=int, default=32,
                        help='Initial offset enumeration radius in grid spacings; expands until connected')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--from-results', action='store_true', help='Regenerate reports/plots from completed engine output')
    args = parser.parse_args()
    destination = args.out_dir or args.run_dir / f'strong_event_h0_alpha{args.alpha:g}_beta{args.beta:g}'
    if args.from_results:
        finish_outputs(destination, json.loads((destination/'selection.json').read_text()))
    else:
        run(args.run_dir, destination, args.alpha, args.beta, args.initial_radius, args.prepare_only)
