"""Offline pressure-power demo on a checksum-verified downloaded subvolume."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import numpy as np
import zarr

from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.input_fields import field_config
from jhtdb_pipeline.store import array_sha256


PROJECT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=PROJECT / 'configs/pipeline.yaml')
    parser.add_argument('--shape-xyz', type=int, nargs=3, default=(128, 128, 64),
                        metavar=('NX', 'NY', 'NZ'), help='Origin-aligned crop, multiples of 16')
    args = parser.parse_args()
    cfg = load_config(args.config)
    pressure_cfg = field_config(cfg, 'pressure_gradient')
    # No request is sent if any input is missing.
    nx, ny, nz = args.shape_xyz
    if any(n <= 0 or n % 16 or n > g for n, g in zip((nx, ny, nz), cfg.grid_shape)):
        raise ValueError('Crop dimensions must be positive multiples of 16 within the source grid')
    arrays = {}
    source_metadata = {}
    for field, view in [('velocity', cfg), ('pressure_gradient', pressure_cfg)]:
        root = zarr.open_group(str(view.raw_store_path(1)), mode='r')
        expected = dict(dataset=cfg.dataset, time_index=1, physical_time=cfg.physical_time(1),
                        grid_shape_xyz=list(cfg.grid_shape), axis_order=['component', 'z', 'y', 'x'])
        if field == 'velocity':
            expected['status'] = 'validated'
        else:
            expected.update(pressure_cfg.acquisition_metadata)
        if any(root.attrs.get(k) != v for k, v in expected.items()):
            raise ValueError(f'{field}: source metadata mismatch or unvalidated velocity')
        if root[field].shape != (3, *reversed(cfg.grid_shape)):
            raise ValueError(f'{field}: unexpected source shape')
        values = np.ascontiguousarray(root[field][:, :nz, :ny, :nx], dtype='<f4')
        if values.shape != (3, nz, ny, nx) or not np.isfinite(values).all():
            raise ValueError(f'{field}: incomplete or non-finite subset; no download attempted')
        arrays[field] = values
        source_metadata[field] = dict(path=str(view.raw_store_path(1)), attrs=dict(root.attrs))

    uri = pressure_cfg.catalog_path.resolve().as_uri() + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            'SELECT x0,y0,z0,nx,ny,nz,status,sha256 FROM tiles '
            'WHERE dataset=? AND time_index=1 AND x0<? AND y0<? AND z0<?',
            (cfg.dataset, nx, ny, nz)).fetchall()
    finally:
        connection.close()
    expected_origins = {(x, y, z) for x in range(0, nx, 16)
                        for y in range(0, ny, 16) for z in range(0, nz, 16)}
    if len(rows) != len(expected_origins) or {(r[0], r[1], r[2]) for r in rows} != expected_origins:
        raise ValueError('Subset does not have complete catalog coverage')
    for x, y, z, tx, ty, tz, status, digest in rows:
        if (tx, ty, tz) != (16, 16, 16) or status != 'verified' or not digest:
            raise ValueError('Subset contains an unverified pressure tile')
        chunk = arrays['pressure_gradient'][:, z:z+tz, y:y+ty, x:x+tx]
        if array_sha256(chunk) != digest:
            raise ValueError(f'Pressure checksum mismatch at {(x,y,z)}')

    job = PROJECT / 'qpower_analysis/output' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    job.mkdir(parents=True, exist_ok=False)
    for field, values in arrays.items():
        np.save(job / f'{field}.npy', values)
    scope = dict(
        kind='local_subvolume_demo', origin_xyz=[0, 0, 0], shape_xyz=[nx, ny, nz],
        full_grid_shape_xyz=list(cfg.grid_shape), pressure_tiles_checksum_verified=len(rows),
        normalization='q_rms and mean(u2) computed within this subset only',
        limitations='Not full-domain statistics or a full-domain filtered multi-sigma calculation.',
        gradient='Existing server fd4noint gradient; no differentiation or periodic wrapping of the crop.',
        sources=source_metadata,
    )
    (job / 'subset_provenance.json').write_text(json.dumps(scope, indent=2), encoding='utf-8')
    analysis = json.loads((PROJECT / 'qpower_analysis/config.example.json').read_text(encoding='utf-8'))
    analysis['frames'] = [dict(frame=1, time=cfg.physical_time(1),
        velocity_path=str(job / 'velocity.npy'), velocity_key='velocity',
        pressure_path=None, pressure_gradient_path=str(job / 'pressure_gradient.npy'),
        pressure_gradient_keys=['pressure_gradient'])]
    analysis.update(periodic_xyz=[False, False, False], gradient_method='finite_difference',
        domain_lengths_xyz=[cfg.domain_length * n / g for n, g in zip((nx, ny, nz), cfg.grid_shape)],
        visualization_stride=2, output_root=str(job / 'analysis'), subset_scope=scope)
    # gradient_method is unused because the checked server gradient is supplied.
    config_path = job / 'analysis_config.json'
    config_path.write_text(json.dumps(analysis, indent=2), encoding='utf-8')
    print(f'Verified {len(rows)} pressure tiles; running local subset: {job}', flush=True)
    subprocess.run([sys.executable, str(PROJECT / 'qpower_analysis/qpower_analysis.py'),
                    '--config', str(config_path)], cwd=PROJECT, check=True)
    print(f'Subset demo complete: {job}', flush=True)


if __name__ == '__main__':
    main()
