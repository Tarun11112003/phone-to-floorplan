"""The exact brief must not pass when old geometry-only outputs omit essentials."""
import copy
import json
from pathlib import Path

import pytest

from floorplan.assignment_gates import evaluate_assignment


def scene():
    rooms=[dict(id='a', corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=2.5),
           dict(id='b', corners=[[4,0],[7,0],[7,3],[4,3]],ceiling_height_m=2.5)]
    truth=dict(rooms=rooms,openings=[dict(id='door',rooms=['a','b'],kind='doorway',width_m=1.,segment=[[4,1],[4,2]])],
               connections=[dict(rooms=['a','b'],width_m=1.)])
    plan=copy.deepcopy(truth)
    for room in plan['rooms']:
        room['metric_status']='sensor_scaled'
        room['measurement_intervals']={'floor_area_m2':{'lower':0,'upper':100,'confidence':.95},
              'ceiling_height_m':{'lower':2.4,'upper':2.6,'confidence':.95},
              'walls_m':[{'lower':0,'upper':10,'confidence':.95} for _ in room['corners']]}
    plan['openings'][0]['width_interval_m']={'lower':.9,'upper':1.1,'confidence':.95}
    return plan,truth


def test_assignment_gate_counts_missing_and_phantom_openings():
    plan,truth=scene()
    good=evaluate_assignment(plan,truth,'photos')
    assert good['known_gates_pass']
    assert not good['assignment_complete']  # Published schema/Round 1 still absent.
    plan['openings']=[]
    missing=evaluate_assignment(plan,truth,'photos')
    assert missing['openings']['false_negatives']==1
    assert missing['openings']['gate']=='fail'
    plan,truth=scene()
    plan['openings'].append(dict(id='phantom',rooms=['a','b'],width_m=.8,kind='doorway',segment=[[4,2],[4,2.5]]))
    phantom=evaluate_assignment(plan,truth,'photos')
    assert phantom['openings']['false_positives']==1
    assert phantom['openings']['gate']=='fail'


def test_assignment_height_and_interval_omission_fail_even_when_walls_are_exact():
    plan,truth=scene()
    plan['rooms'][0]['ceiling_height_m']=None
    plan['rooms'][1].pop('measurement_intervals')
    result=evaluate_assignment(plan,truth,'lidar')
    assert result['legacy_geometry']['wall_geometry_targets_met']
    assert result['ceiling']['gate']=='fail'
    assert result['intervals']['gate']=='fail'
    assert result['walls']['gate']=='pending_round1_definition'
    assert not result['known_gates_pass']


def test_assignment_photo_and_video_relative_wall_gates_diverge():
    plan,truth=scene()
    plan['rooms'][0]['corners'][1][0]=4.2
    plan['rooms'][0]['corners'][2][0]=4.2
    # Geometry correspondence may be imperfect after global alignment, but a
    # 5% first wall error is inside the photo gate and outside the video gate.
    photo=evaluate_assignment(plan,truth,'photos')
    video=evaluate_assignment(plan,truth,'video')
    assert photo['walls']['gate']=='pass'
    assert video['walls']['gate']=='fail'


def test_old_v3_artifact_fails_full_assignment_contract():
    root=Path(__file__).resolve().parents[1]
    plan=json.loads((root/'tests/fixtures/legacy_multiview_plan.json').read_text(encoding='utf-8'))
    truth=json.loads((root/'tests/fixtures/legacy_multiview_reference.json').read_text(encoding='utf-8'))
    result=evaluate_assignment(plan,truth,'photos')
    assert result['ceiling']['gate']=='fail'
    assert result['intervals']['gate']=='fail'
    assert not result['known_gates_pass']


def test_collinear_export_vertex_does_not_hide_a_surveyed_wall():
    plan,truth=scene()
    plan['rooms'][0]['corners'].insert(1,[2,0])
    result=evaluate_assignment(plan,truth,'photos')
    assert result['walls']['count']==8
    assert result['walls']['gate']=='pass'
    # A real extra corner must still fail full wall correspondence.
    plan['rooms'][0]['corners'][1]=[2,.1]
    result=evaluate_assignment(plan,truth,'photos')
    assert result['walls']['gate']=='fail'
