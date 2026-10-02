from dataclasses import replace
import numpy as np
import pytest
import zarr
from jhtdb_pipeline.config import load_config
from jhtdb_pipeline.pressure_local import download_pressure, compute_gradient, fd4_block
from jhtdb_pipeline.store import spatial_slices


def test_fd4_periodic_seams_and_component_order():
    shape = (16, 24, 32)
    lengths = (3.0, 5.0, 7.0)
    z, y, x = np.meshgrid(*(np.arange(n) * 2*np.pi/n for n in shape), indexing='ij')
    p = np.sin(x) + 2*np.cos(2*y) + 3*np.sin(3*z)
    expected = np.stack([(np.roll(p,2,axis)-8*np.roll(p,1,axis)+8*np.roll(p,-1,axis)-np.roll(p,-2,axis))/(12*lengths[c]/shape[axis]) for c,axis in enumerate((2,1,0))])
    actual = np.empty((3,*shape), dtype=np.float32)
    for key in spatial_slices(shape, (5,7,9)):
        actual[(slice(None),*key)] = fd4_block(p,key,lengths)
    np.testing.assert_allclose(actual,expected,rtol=2e-6,atol=2e-6)


def test_fourth_order_convergence():
    errors=[]
    for n in (16,32):
        x=np.arange(n)*2*np.pi/n
        p=np.broadcast_to(np.sin(x),(8,8,n))
        g=fd4_block(p,tuple(slice(0,k) for k in p.shape),[2*np.pi]*3)
        errors.append(np.max(np.abs(g[0,0,0]-np.cos(x))))
    assert 14 < errors[0]/errors[1] < 18


def test_download_resume_and_saved_gradient(tmp_path,monkeypatch):
    cfg=replace(load_config('configs/pipeline.yaml'), grid_shape=(16,16,16),
        request_shape=(8,8,8),tile_shape=(8,8,8),state_root=tmp_path/'state',
        run_root=tmp_path/'runs', persistent_safety_reserve_gib=0,request_cooldown_seconds=0)
    monkeypatch.setenv('JHTDB_TOKEN','test-only')
    class Fake:
        calls=0
        def __init__(self,*args): pass
        def fetch_tile(self,tile,frame):
            Fake.calls+=1
            z,y,x=np.meshgrid(np.arange(tile.z0,tile.z0+tile.nz),np.arange(tile.y0,tile.y0+tile.ny),np.arange(tile.x0,tile.x0+tile.nx),indexing='ij')
            return np.asarray(np.sin(x*2*np.pi/16)+np.cos(y*2*np.pi/16)+np.sin(z*2*np.pi/16),dtype='<f4')
    path=download_pressure(cfg,1,Fake)
    download_pressure(cfg,1,Fake)
    assert Fake.calls==8
    out=compute_gradient(cfg,1,8)
    root=zarr.open_group(str(out),mode='r')
    assert root.attrs['status']=='validated'
    assert root['pressure_gradient'].shape==(3,16,16,16)
    assert compute_gradient(cfg,1,8)==out
    pressure=zarr.open_group(str(path),mode='a')['pressure']
    pressure[0,0,0]=99
    with pytest.raises(ValueError,match='checksum'):
        compute_gradient(cfg,1,8)
    download_pressure(cfg,1,Fake)
    assert Fake.calls==9


def test_qpower_rejects_unvalidated_local_gradient(tmp_path):
    import importlib.util
    import sys
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('qpower_local_test',Path(__file__).resolve().parents[1]/'qpower_analysis/qpower_analysis.py')
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    velocity=tmp_path/'velocity.npy'
    np.save(velocity,np.ones((3,8,8,8),dtype=np.float32))
    path=tmp_path/'gradient.zarr'
    root=zarr.open_group(str(path),mode='w')
    root.create_dataset('pressure_gradient',shape=(3,8,8,8),dtype='<f4')
    root.attrs.update(source='local periodic fd4',status='computing',time_index=1,physical_time=0.0)
    frame=dict(frame=1,time=0.0,velocity_path=str(velocity),pressure_gradient_path=str(path),pressure_gradient_keys=['pressure_gradient'])
    with pytest.raises(module.PreflightError,match='validation'):
        module.preflight_frame(frame)
    root.attrs['status']='validated'
    assert module.preflight_frame(frame)['shape']==(8,8,8)
    frame['time']=0.002
    with pytest.raises(module.PreflightError,match='metadata mismatch'):
        module.preflight_frame(frame)


def test_partial_pressure_only_computes_blocks_with_complete_periodic_halo(tmp_path,monkeypatch):
    from jhtdb_pipeline.pressure_local import required_pressure_blocks
    cfg=replace(load_config('configs/pipeline.yaml'),grid_shape=(16,16,16),request_shape=(8,8,8),
        tile_shape=(8,8,8),state_root=tmp_path/'state',run_root=tmp_path/'runs',
        persistent_safety_reserve_gib=0,request_cooldown_seconds=0,retries=1)
    monkeypatch.setenv('JHTDB_TOKEN','test-only')
    class Fake:
        fail=True
        def __init__(self,*args): pass
        def fetch_tile(self,tile,frame):
            if Fake.fail and tile.x0==8:
                raise RuntimeError('interrupted download')
            return np.ones((tile.nz,tile.ny,tile.nx),dtype='<f4')
    with pytest.raises(RuntimeError,match='download failed'):
        download_pressure(cfg,1,Fake)
    assert required_pressure_blocks(cfg,(slice(2,4),)*3)=={'x0000_y0000_z0000'}
    assert 'x0008_y0008_z0008' in required_pressure_blocks(cfg,(slice(0,2),)*3)
    with pytest.raises(ValueError,match='not fully validated'):
        compute_gradient(cfg,1,2)
    path=cfg.persistent_input_path(1)/'pressure_gradient_fd4_cache.zarr'
    root=zarr.open_group(str(path),mode='r')
    np.testing.assert_array_equal(root['pressure_gradient'][:,2:4,2:4,2:4],0)
    assert np.isnan(root['pressure_gradient'][:,0:2,0:2,0:2]).all()
    assert root.attrs['status']=='computing'
    Fake.fail=False
    download_pressure(cfg,1,Fake)
    compute_gradient(cfg,1,2)
    root=zarr.open_group(str(path),mode='r')
    assert root.attrs['status']=='validated'
    np.testing.assert_array_equal(root['pressure_gradient'][:],0)
