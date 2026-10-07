import numpy as np
import pytest



@pytest.mark.parametrize('maximum_width',[16,8])
def test_colmap_rectification_preserves_opencv_pixel_centers(maximum_width):
    import cv2
    import pycolmap
    from floorplan.dense import _undistort
    # A centered pinhole is already rectified. COLMAP's half-pixel origin
    # must be converted to array/OpenCV coordinates before remapping.
    camera=pycolmap.Camera.create_from_model_id(1,pycolmap.CameraModelId.PINHOLE,12.,16,12)
    y,x=np.mgrid[:12,:16]
    pixels=np.stack([x*10,y*10,(x+y)*5],axis=-1).astype(np.uint8)
    rectified,k=_undistort(pixels,camera,cv2,max_width=maximum_width)
    expected=cv2.resize(pixels,(maximum_width,round(12*maximum_width/16)),interpolation=cv2.INTER_LINEAR)
    assert np.array_equal(rectified,expected)
    assert k[0,2]==(maximum_width-1)/2
