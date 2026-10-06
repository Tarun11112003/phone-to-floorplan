import json
import numpy as np
import pytest

from floorplan.benchmark import evaluate_polygons
from floorplan.layout import weighted_voxels, extract_layout
from floorplan.rgbd import _fit_planes
from floorplan.workflow import reconstruct


def room(id,points):
    return {'id':id,'corners':points,'metric_status':'sensor_scaled'}


def test_evaluator_preserves_scale_missing_rooms_and_control_exclusion():
    a = [[0,0],[4,0],[4,3],[0,3]]
    b = [[4,0],[6,0],[6,3],[4,3]]
    truth = {'rooms':[room('a',a),room('b',b)],'connections':[{'rooms':['a','b'],'width_m':1}]}
    prediction = {'rooms':[room('x',np.asarray(a).tolist()),room('y',np.asarray(b).tolist())],
                  'connections':[{'rooms':['x','y'],'width_m':1}]}
    exact = evaluate_polygons(prediction,truth,'identity')
    assert exact['targets_met'] and exact['dimension_count']==8
    prediction['connections'][0]['width_m'] = .8
    bad_door = evaluate_polygons(prediction,truth,'identity')
    assert bad_door['wall_geometry_targets_met'] and not bad_door['targets_met']
    prediction['connections'][0]['width_m'] = 1
    prediction['rooms'][0]['corners'] = (np.asarray(a)*1.05).tolist()
    assert not evaluate_polygons(prediction,truth)['targets_met']
    prediction['rooms'] = prediction['rooms'][:1]
    assert evaluate_polygons(prediction,truth)['missing_rooms']==1
    truth['excluded_evaluation_edges']=[{'room_id':'a','edge_index':0}]
    assert evaluate_polygons({'rooms':[room('x',a),room('y',b)]},truth,'identity')['dimension_count']==7


def test_evaluator_concave_polygon_and_single_global_alignment():
    a=np.array([[0,0],[4,0],[4,2],[2,2],[2,4],[0,4]],float)
    b=np.array([[4,0],[7,0],[7,2],[4,2]],float)
    rotation=np.array([[0,-1],[1,0]])
    plan={'rooms':[room('x',(a@rotation+10).tolist()),room('y',(b@rotation+10).tolist())]}
    truth={'rooms':[room('a',a.tolist()),room('b',b.tolist())]}
    assert evaluate_polygons(plan,truth)['targets_met']
    plan['rooms'][1]['corners']=(b@rotation+np.array([10.3,10])).tolist()
    assert not evaluate_polygons(plan,truth)['targets_met']


def test_voxels_average_all_observations_and_degenerate_planes():
    points=np.array([[.001,0,0],[.009,0,0]])
    xyz,_,weights=weighted_voxels(points,weights=[1,3])
    assert xyz[0,0]==pytest.approx(.007)
    assert weights[0]==4
    assert _fit_planes(np.ones((1000,3)))==[]


def test_unified_failure_is_persisted_with_no_plan(tmp_path):
    manifest=tmp_path/'capture.json'
    manifest.write_text(json.dumps({'schema_version':2,'tier':'lidar','sequence':'missing.json'}))
    ledger=reconstruct(manifest,tmp_path/'out')
    assert ledger['result']['status']=='failed'
    assert (tmp_path/'out'/'run.json').exists()
    assert not (tmp_path/'out'/'plan.json').exists()
    with pytest.raises(FileExistsError): reconstruct(manifest,tmp_path/'out')


def test_layout_extracts_two_rooms_only_with_traversed_door():
    rng=np.random.default_rng(7)
    points=[]; planes=[]
    # Two 3m x 3m rooms, common wall x=3 with 1m opening.
    definitions=[(0,0,0,3),(0,6,0,3),(1,0,0,6),(1,3,0,6),(0,3,0,1),(0,3,2,3)]
    for axis,location,lo,hi in definitions:
        n=2500
        horizontal=rng.uniform(lo,hi,n); vertical=rng.uniform(-.8,1.3,n)
        cloud=np.column_stack([np.full(n,location),vertical,horizontal]) if axis==0 else np.column_stack([horizontal,vertical,np.full(n,location)])
        points.append(cloud)
    floor=np.column_stack([rng.uniform(0,6,5000),np.full(5000,1.5),rng.uniform(0,3,5000)])
    points.append(floor)
    cloud=np.concatenate(points)
    planes=_fit_planes(cloud)
    path=np.array([[1,0,1.5],[2.5,0,1.5],[3.5,0,1.5],[5,0,1.5]])
    rooms,metadata=extract_layout(cloud,planes,path)
    assert len(rooms)==2
    assert metadata['camera_center_coverage_fraction']==1
    assert len(metadata['connections'])==1
    assert metadata['connections'][0]['width_m']==pytest.approx(1,abs=.03)
    # A missing wall must not be silently replaced with a rectangle.
    cloud=cloud[cloud[:,0]>.1]
    rooms,_=extract_layout(cloud,_fit_planes(cloud),path[:2])
    assert not rooms


def test_measured_scale_uses_triangulation_and_rejects_weak_baseline():
    pycolmap=pytest.importorskip('pycolmap')
    from floorplan.dense import measured_scale
    from types import SimpleNamespace
    camera=pycolmap.Camera.create_from_model_name(1,'PINHOLE',480,640,480)
    class Image:
        camera_id=1
        def __init__(self,name,center): self.name,self.center=name,np.array(center)
        def cam_from_world(self):
            return SimpleNamespace(matrix=lambda:np.column_stack([np.eye(3),-self.center]))
    images={1:Image('a.png',[0,0,0]),2:Image('b.png',[.4,0,0])}
    model=SimpleNamespace(images=images,cameras={1:camera})
    controls={'length_m':2.,'a':[],'b':[]}
    for name,point in [('a',[0,0,3]),('b',[1,0,3])]:
        controls[name]=[{'image':image.name,'pixel':camera.img_from_cam(np.asarray(point)-image.center).tolist()} for image in images.values()]
    scale,evidence=measured_scale(model,[controls])
    assert scale==pytest.approx(2)
    assert evidence[0]['reprojection_max_px']<1e-8
    controls['a']=controls['a'][:1]
    with pytest.raises(ValueError,match='two registered views'): measured_scale(model,[controls])


def test_unknown_opening_height_withholds_net_wall_area():
    from floorplan.pipeline import _quantities
    r=room('a',[[0,0],[4,0],[4,3],[0,3]])
    r.update(label='A',ceiling_height_m=2.7,openings=[{'edge_index':0,'start_fraction':.2,'end_fraction':.5,'height_m':None}])
    quantities=_quantities(r)
    assert quantities['area_m2']==12
    assert quantities['gross_wall_area_m2']==pytest.approx(37.8)
    assert quantities['net_wall_area_m2'] is None


def test_ordered_camera_jump_rejected_but_unordered_photos_not_assumed_continuous():
    from types import SimpleNamespace
    from floorplan.dense import camera_path_quality
    model = SimpleNamespace(images={i: SimpleNamespace(name=f'{i:04}.png', projection_center=lambda x=x: np.array([x,0,0]))
                                   for i,x in enumerate([0,.2,.4,6.6,6.8])})
    ordered = camera_path_quality(model, 1., True)
    assert not ordered['passed']
    assert ordered['suspicious_transitions'][0]['distance_m'] == pytest.approx(6.2)
    assert camera_path_quality(model, 1., False)['passed']
    assert camera_path_quality(model, .1, True)['passed']
