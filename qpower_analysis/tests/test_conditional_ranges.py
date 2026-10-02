import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]))
from conditional_ranges import indices,quantile_ranges,value_edges


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
