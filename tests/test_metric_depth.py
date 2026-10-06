import numpy as np
import pytest

from floorplan.metric_depth import depth_metrics


def test_sensor_comparison_preserves_scale_error_and_masks_invalid_reference():
    reference=np.array([[1.,2.],[0.,4.]])
    proposal=np.array([[2.,4.],[100.,8.]])
    result=depth_metrics(proposal,reference,np.ones((2,2),bool))
    assert result['valid_pixels']==3
    assert result['median_scale_ratio']==2
    assert result['absolute_relative_error']==1
    assert result['fraction_within_2cm']==0
    assert not result['scale_aligned']
    assert depth_metrics(proposal,reference,np.zeros((2,2),bool))['status']=='unavailable'
    with pytest.raises(ValueError): depth_metrics(proposal,reference,np.ones((1,2),bool))
