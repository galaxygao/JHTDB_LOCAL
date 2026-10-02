import importlib.util
from pathlib import Path
import numpy as np

spec=importlib.util.spec_from_file_location('contributions',Path(__file__).parents[1]/'threshold_contributions.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_histograms_match_direct_masks_including_threshold_boundaries():
    q=np.array([-3,-1,0,1,2,3,4,5],dtype=np.float32)
    u2=np.array([0,1,2,3,4,5,6,7],dtype=np.float32)
    alphas=[1.,2.,4.];betas=[1.,3.,5.]
    hist=module.histograms(q,u2,1.,1.,alphas,betas)
    fields={'u2':u2,'q_positive':np.maximum(q,0),'q_negative_magnitude':np.maximum(-q,0),'q_squared':q.astype(np.float64)**2}
    for i in range(4):
        for j in range(4):
            mask=np.ones(q.shape,dtype=bool)
            if i: mask &= q>alphas[i-1]
            if j: mask &= u2>betas[j-1]
            assert hist['count'][i:,j:].sum()==mask.sum()
            for name,values in fields.items():
                np.testing.assert_allclose(hist[name][i:,j:].sum(),values[mask].sum(dtype=np.float64))
