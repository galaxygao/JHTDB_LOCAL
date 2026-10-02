import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('conditional_tails',Path(__file__).parents[1]/'conditional_tails.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


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
