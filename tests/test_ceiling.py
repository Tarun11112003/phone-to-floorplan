import numpy as np
from shapely.geometry import Polygon

from floorplan.layout import _observed_ceiling,_observed_floor


def _grid(xmax, zmax, y):
    x,z=np.meshgrid(np.linspace(.1,xmax-.1,40),np.linspace(.1,zmax-.1,30))
    return np.column_stack([x.ravel(),np.full(x.size,y),z.ravel()])


def test_broad_observed_ceiling_is_measured_and_cabinet_top_rejected():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    ceiling=_grid(4,3,-2.5)
    cabinet=_grid(.7,.7,-2.1)
    points=np.vstack((ceiling,cabinet))
    planes=[dict(normal=[0,1,0],offset=2.5,rms_m=.002),
            dict(normal=[0,1,0],offset=2.1,rms_m=.002)]
    height,evidence=_observed_ceiling(room,points,planes,np.eye(3),0,[[2,1.5,-1.5]])
    assert height==2.5
    assert evidence['coverage_fraction']>.5


def test_ceiling_missing_when_only_narrow_horizontal_surface():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    points=_grid(.7,.7,-2.5)
    height,evidence=_observed_ceiling(room,points,[dict(normal=[0,1,0],offset=2.5,rms_m=.002)],
                                       np.eye(3),0,[[2,1.5,-1.5]])
    assert height is None and evidence is None


def test_four_disconnected_ceiling_patches_do_not_count_their_convex_hull():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    small=_grid(.2,.2,-2.5)
    points=np.concatenate([small+np.array([x,0,z]) for x,z in [(0,0),(3.7,0),(0,2.7),(3.7,2.7)]])
    height,evidence=_observed_ceiling(room,points,[dict(normal=[0,1,0],offset=2.5,rms_m=.002)],
                                    np.eye(3),0,[[2,1.5,-1.5]])
    assert height is None and evidence is None


def test_ceiling_measurement_is_invariant_to_horizontal_capture_origin():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    points=_grid(4,3,-2.5); points[:,1]-=.001*points[:,0]
    normal=np.array([.001,1,0]); normal/=np.linalg.norm(normal)
    plane=dict(normal=normal,offset=2.5/np.sqrt(1+.001**2),rms_m=.002)
    height,_=_observed_ceiling(room,points,[plane],np.eye(3),0,[[2,1.5,-1.5]])
    shifted=points+np.array([100,0,0])
    moved=Polygon([(100,0),(104,0),(104,3),(100,3)])
    plane={**plane,'offset':plane['offset']-normal[0]*100}
    other,_=_observed_ceiling(moved,shifted,[plane],np.eye(3),0,[[102,1.5,-1.5]])
    assert abs(height-other)<1e-10


def test_resolved_ceiling_slope_retains_range_without_assumed_scalar_definition():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    points=_grid(4,3,-2.5); points[:,1]-=.05*points[:,0]
    normal=np.array([.05,1,0]); normal/=np.linalg.norm(normal)
    plane=dict(normal=normal,offset=2.5/np.sqrt(1+.05**2),rms_m=.002)
    height,evidence=_observed_ceiling(room,points,[plane],np.eye(3),0,[[2,1.5,-1.5]])
    assert height is None
    assert np.allclose(evidence['height_range_m'],[2.5,2.7])


def test_floor_observation_in_neighboring_room_is_not_borrowed():
    room=Polygon([(4,0),(8,0),(8,3),(4,3)])
    points=_grid(4,3,0)
    plane=dict(normal=[0,1,0],offset=0,rms_m=.002)
    floor,evidence=_observed_floor(room,points,[plane],np.eye(3),[[6,1.5,-1.5]])
    assert floor is None and evidence is None


def test_broad_table_does_not_replace_observed_storey_floor_datum():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    points=_grid(4,3,1.)
    plane=dict(normal=[0,1,0],offset=-1.,rms_m=.002)
    floor,evidence=_observed_floor(room,points,[plane],np.eye(3),[[2,1.5,0]],reference_floor=1.5)
    assert floor is None and evidence is None


def test_assessment_preserves_room_floor_failure_and_slope_evidence():
    from floorplan.assessment import build_assessment
    room=dict(id='a',corners=[[0,0],[4,0],[4,3],[0,3]],floor_observed=False,
              ceiling_height_m=None,ceiling_evidence=dict(height_range_m=[2.5,2.7],height_definition='unavailable: resolved slope'))
    document=build_assessment(dict(rooms=[room],provenance={'floor_observed':True}),
        dict(configuration={},manifest_sha256='a'*64,run_id='test',tier='lidar',result={'status':'partial'}))
    assert not next(s for s in document['surfaces'] if s['kind']=='floor')['observed']
    assert document['rooms'][0]['ceiling_evidence']['height_range_m']==[2.5,2.7]
    assert document['measurements'][0]['reason']=='unavailable: resolved slope'
