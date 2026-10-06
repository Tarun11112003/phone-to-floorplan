from floorplan.supported_cells import propose_supported_cells


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
