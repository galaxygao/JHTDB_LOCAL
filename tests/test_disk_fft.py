from pathlib import Path
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pytest
from scipy import fft

from jhtdb_pipeline.disk_fft import build_spectrum, filter_spectrum
from jhtdb_pipeline.physics import close_memmap, full_spectrum, filter_smooth_sharp_from_spectrum
from jhtdb_pipeline.processing import process_batch, resource_plan
from jhtdb_pipeline.store import open_complete_result
from test_processing import fixture


@pytest.mark.parametrize('n,slab', [(16,3), (17,4)])
def test_disk_fft_matches_full_fft_without_full_volume_transforms(tmp_path, n, slab):
    source=np.random.default_rng(8).standard_normal((n,n,n),dtype=np.float32)
    expected=full_spectrum(source, slab, workers=2)
    output=np.empty_like(source)
    reference=np.empty_like(source)
    filter_smooth_sharp_from_spectrum(expected, reference, 2., 2*np.pi, .1171875, slab, workers=2)
    original_fft, original_ifft = fft.fft, fft.ifft
    sizes=[]
    def forward(a, *args, **kwargs):
        sizes.append(a.size)
        return original_fft(a,*args,**kwargs)
    def inverse(a, *args, **kwargs):
        sizes.append(a.size)
        return original_ifft(a,*args,**kwargs)
    with patch('jhtdb_pipeline.disk_fft.fft.fft',side_effect=forward), patch('jhtdb_pipeline.disk_fft.fft.ifft',side_effect=inverse):
        mapped=build_spectrum(source,tmp_path/'spectrum.c64',slab,workers=2,full=True)
        assert isinstance(mapped,np.memmap)
        try:
            np.testing.assert_allclose(mapped,expected,rtol=2e-5,atol=5e-5)
            before=np.asarray(mapped).copy()
            filter_spectrum(mapped,output,tmp_path/'filtered.c64',2.,2*np.pi,.1171875,slab,workers=2)
            np.testing.assert_array_equal(mapped,before)
            np.testing.assert_allclose(output,reference,rtol=2e-5,atol=2e-6)
        finally:
            close_memmap(mapped)
    assert max(sizes)<=slab*n*(n//2+1)
    assert not (tmp_path/'filtered.c64').exists()


@pytest.mark.parametrize('kind',['gaussian','smooth_sharp'])
def test_disk_batch_preserves_shared_work_and_all_full_fields(tmp_path,kind):
    cfg,_=fixture(tmp_path/'disk')
    cfg=replace(cfg,filter_type=kind,fft_cache_mode='memmap',sigma_grid=1.,sigma_grids=(1.,2.))
    from jhtdb_pipeline.physics import derivative_field
    with patch('jhtdb_pipeline.processing.build_spectrum',wraps=build_spectrum) as spectra:
        paths=process_batch(cfg,1)
    # Both scales share the same twelve source spectra, with no rebuilding per scale.
    assert spectra.call_count==12
    baseline,_=fixture(tmp_path/'memory')
    baseline=replace(baseline,filter_type=kind,fft_cache_mode='memory',sigma_grid=1.,sigma_grids=(1.,2.))
    expected=process_batch(baseline,1)
    for path,ref in zip(paths,expected):
        result,reference=open_complete_result(path),open_complete_result(ref)
        for field in result:
            assert result[field].shape[-3:]==cfg.full_shape_zyx
            np.testing.assert_allclose(result[field][:],reference[field][:],rtol=3e-5,atol=3e-6)
    assert not list(cfg.run_path(1).glob('batch-cache-*'))
    assert resource_plan(cfg)['batch_shared_RAM_GiB']==0


def test_failed_disk_cache_is_closed_and_removed(tmp_path):
    cfg,_=fixture(tmp_path)
    cfg=replace(cfg,fft_cache_mode='memmap',sigma_grids=(1.,2.))
    with patch('jhtdb_pipeline.processing.build_spectrum',side_effect=RuntimeError('test failure')):
        with pytest.raises(RuntimeError,match='test failure'):
            process_batch(cfg,1)
    assert not list(cfg.run_path(1).glob('batch-cache-*'))
    assert not list(cfg.result_root.glob('*/COMPLETE'))
