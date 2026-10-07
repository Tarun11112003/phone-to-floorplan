from floorplan.supported_cells import propose_supported_cells
from shapely.geometry import Polygon


def _segments():
    def wall(axis,location,lo,hi):
        return dict(axis=axis,location=location,lo=lo,hi=hi,support=100,rms_m=.01)
    return [wall(0,0,0,3),wall(0,4,0,1.1),wall(0,4.05,2.1,3),
            wall(1,0,0,4),wall(1,3,0,4)]


def test_occlusion_proposal_records_gap_without_claiming_door():
    rooms,evidence=propose_supported_cells(_segments(),[[2,1],[2,2]])
    assert len(rooms)==1
    right=evidence[0]['edges'][1]
    assert .6<right['supported_fraction']<.7
    assert abs(right['max_gap_m']-1)<1e-6
    assert right['opening_classification'].startswith('unresolved')


def test_missing_wall_and_unvisited_room_are_rejected():
    segments=[s for s in _segments() if not (s['axis']==0 and s['location']>3)]
    assert propose_supported_cells(segments,[[2,1],[2,2]])[0]==[]
    assert propose_supported_cells(_segments(),[[7,7],[8,8]])[0]==[]


def test_observed_cells_are_excluded_before_greedy_partial_selection():
    segments=_segments()
    # A larger, more occupied hypothesis overlaps the existing observed cell.
    # It must not consume the smaller nonoverlapping candidate's place.
    segments += [dict(axis=0,location=2,lo=0,hi=3,support=100,rms_m=.01)]
    existing=Polygon([(0,0),(2,0),(2,3),(0,3)])
    path=[[.5,1],[1,2],[3,1],[3,2]]
    rooms,evidence=propose_supported_cells(segments,path,occupied_cells=[existing])
    assert len(rooms)==1 and len(evidence)==1
    assert rooms[0].intersection(existing).area<=.01
    assert rooms[0].bounds[0]==2
    assert evidence[0]['camera_samples_inside']==2


def test_vectorized_occupancy_preserves_rounded_buffer_boundary_semantics():
    from shapely.geometry import Point
    path=[[2,1],[2,2],[-.04,-.04],[-.03,-.03],[-.05,0],[0,0]]
    rooms,evidence=propose_supported_cells(_segments(),path)
    assert len(rooms)==1
    expected=sum(rooms[0].buffer(.05).covers(Point(p)) for p in path)
    assert evidence[0]['camera_samples_inside']==expected
