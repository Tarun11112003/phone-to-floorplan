import numpy as np
import pytest

from floorplan.rgb_metric import calibrated_prediction_grid


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


def test_conditioned_camera_maps_preserve_rays_with_off_center_non_square_pixels():
    k=np.array([[600.,0,317],[0,620,233],[0,0,1]])
    grid=calibrated_prediction_grid(k,640,480)
    virtual=grid['virtual_k']
    assert grid['fov_x']==pytest.approx(np.degrees(2*np.arctan(640/1200)))
    for x,y in [(200,100),(320,240),(450,350)]:
        u,v=(a[y,x] for a in grid['to_original'])
        assert (u-k[0,2])/k[0,0]==pytest.approx((x-virtual[0,2])/virtual[0,0],abs=1e-7)
        assert (v-k[1,2])/k[1,1]==pytest.approx((y-virtual[1,2])/virtual[1,1],abs=1e-7)
        u,v=(a[y,x] for a in grid['to_virtual'])
        assert (u-virtual[0,2])/virtual[0,0]==pytest.approx((x-k[0,2])/k[0,0],abs=1e-7)
        assert (v-virtual[1,2])/virtual[1,1]==pytest.approx((y-k[1,2])/k[1,1],abs=1e-7)


@pytest.mark.parametrize('k',[np.eye(2),[[0,0,0],[0,1,0],[0,0,1]],
                              [[1,.1,0],[0,1,0],[0,0,1]],
                              [[float('nan'),0,0],[0,1,0],[0,0,1]]])
def test_invalid_prediction_calibration_rejected(k):
    with pytest.raises(ValueError,match='calibration'):
        calibrated_prediction_grid(k,640,480)


def test_rgb_backend_honors_pose_correction_off(tmp_path,monkeypatch):
    from PIL import Image
    import floorplan.rgb_metric as backend
    import floorplan.rgbd as rgbd
    images=tmp_path/'images'; images.mkdir()
    for i in range(2): Image.new('RGB',(16,12)).save(images/f'{i}.png')
    camera=dict(width=16,height=12,fx=12,fy=12,cx=7.5,cy=5.5)
    def predictions(paths,output,**kwargs):
        return [dict(id=i,source_name=p.name,rgb=str(p),depth='fixture.npy',intrinsics=camera)
                for i,p in enumerate(paths)],{'experimental':True}
    def reconstruction(sequence,output):
        import json
        manifest=json.loads(sequence.read_text())
        assert manifest['optimize_poses'] is False
        assert manifest['path_breaks']==[1]
        return dict(status='incomplete_geometry',floor_plan_ready=False)
    monkeypatch.setattr(backend,'predict_images',predictions)
    monkeypatch.setattr(rgbd,'reconstruct_rgbd',reconstruction)
    result=backend.reconstruct_metric_rgb({'images_directory':str(images)},tmp_path/'run',optimize_poses=False)
    assert result['experimental_backend']
    assert not result['accuracy_validated']
