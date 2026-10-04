import numpy as np
import pytest
import zarr
from qpower_analysis import conditional_tails as module
from qpower_analysis.conditional_ranges import indices, quantile_ranges, value_edges


def test_full_range_and_shared_boundaries_counted_once():
    x=np.array([-10.,-1.,0.,1.,10.]); y=np.array([2.,4.,6.,8.,10.])
    c,s=module.bin_statistics(x,y,np.array([-10.,-1.,1.,10.]))
    np.testing.assert_array_equal(c,[1,2,2])
    np.testing.assert_allclose(s,[2,10,18])
    assert c.sum()==len(x)


def test_negative_tail_edges_increase_and_have_log_spacing():
    edges=module.tail_edges(-100,-1,4)
    assert np.all(np.diff(edges)>0)
    np.testing.assert_allclose(np.diff(np.log(-edges)),np.full(4,-np.log(100)/4))


def test_quantile_interpolation_and_empty_bins():
    counts=np.array([0,10,0,10]);edges=np.array([0.,1.,2.,3.,4.])
    assert module.quantile_from_hist(counts,edges,.25)==1.5
    assert module.quantile_from_hist(counts,edges,.75)==3.5


def test_sparse_range_uses_exact_point_percentiles():
    values=np.arange(40,dtype=float)
    histogram=np.array([[20,20],[0,0]])
    ranges=quantile_ranges(histogram,np.array([0.,20.,40.]),{0:[values]})
    np.testing.assert_allclose(ranges[0],np.quantile(values,[.025,.975]))
    assert np.isnan(ranges[1]).all()


def test_histogram_range_interpolates_uniform_population():
    histogram=np.array([[100,100]])
    result=quantile_ranges(histogram,np.array([0.,1.,2.]),{})
    np.testing.assert_allclose(result,[[.05,1.95]])


def test_signed_value_edges_cover_extremes_and_zero():
    edges=value_edges('q',-80,110)
    assert len(edges)==65537
    assert np.all(np.diff(edges)>0)
    ix=indices(np.array([-80.,0.,110.]),edges)
    assert np.all(ix>=0) and np.all(ix<len(edges)-1)


def test_middle_50_percent_range():
    result=quantile_ranges(np.array([[100,100]]),np.array([0.,1.,2.]),{},coverage=.5)
    np.testing.assert_allclose(result,[[.5,1.5]])


@pytest.mark.parametrize("changed", ["status", "time_index", "physical_time", "shape"])
def test_postprocessing_rejects_mismatched_gradient_cache(tmp_path, changed):
    frame = {'frame': 1, 'time': 0., 'velocity_path': str(tmp_path/'velocity'),
             'pressure_gradient_path': str(tmp_path/'gradient'), 'pressure_gradient_keys': ['gradient']}
    for path, name in ((frame['velocity_path'], 'velocity'), (frame['pressure_gradient_path'], 'gradient')):
        root = zarr.open_group(path, mode='w')
        shape = (3, 3, 2, 2) if changed == 'shape' and name == 'gradient' else (3, 2, 2, 2)
        root.create_dataset(name, shape=shape, dtype='float32')
        root.attrs.update(status='validated', time_index=1, physical_time=0.)
    root = zarr.open_group(frame['pressure_gradient_path'], mode='a')
    if changed != 'shape':
        root.attrs[changed] = {'status': 'partial', 'time_index': 2, 'physical_time': 1.}[changed]
    with pytest.raises(ValueError, match='Input shapes differ' if changed == 'shape' else 'Unvalidated'):
        module.validated_fields(frame, 'velocity')
