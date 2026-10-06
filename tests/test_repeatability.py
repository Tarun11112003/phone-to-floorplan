from copy import deepcopy

from floorplan.repeatability import evaluate_repeatability


def _fixture():
    room=dict(id='r',corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=2.5)
    return dict(rooms=[room],connections=[])


def test_consistent_wrong_heights_fail_accuracy_even_when_repeatable():
    truth=_fixture()
    first=deepcopy(truth)
    second=deepcopy(truth)
    first['rooms'][0]['ceiling_height_m']=2.54
    second['rooms'][0]['ceiling_height_m']=2.545
    result=evaluate_repeatability(first,second,truth)
    assert result['wall_repeatability']['gate']=='pass'
    assert result['ceiling_repeatability']['gate']=='pass'
    assert result['ceiling_accuracy']['gate']=='fail'


def test_physical_wall_spread_fails_even_when_each_capture_is_close():
    truth=_fixture()
    first=deepcopy(truth)
    second=deepcopy(truth)
    first['rooms'][0]['corners'][1][0]=4.025
    first['rooms'][0]['corners'][2][0]=4.025
    result=evaluate_repeatability(first,second,truth)
    assert result['wall_repeatability']['gate']=='fail'
    assert any(w['difference_m']>.02 for w in result['wall_repeatability']['measurements'])
