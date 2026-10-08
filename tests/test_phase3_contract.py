"""Regression coverage for actual contract/evaluator and command failure defects."""
from copy import deepcopy
import json

import pytest

from floorplan.assessment import build_assessment
from floorplan.assessment_io import to_evaluation_plan
from floorplan.assignment_gates import evaluate_assignment
from floorplan.contracts import validate_assessment
from floorplan.provenance import model_files,validate_sfm_cache
from floorplan.uncertainty import apply_calibration,fit_calibration
from floorplan.workflow import read_manifest,run_capture,run_succeeded


def ledger():
    return dict(configuration={'property_id':'audit'},manifest_sha256='a'*64,run_id='capture',
                tier='photos',result={'status':'proposal_requires_review'})


def shared_door():
    rooms=[dict(id='a',corners=[[0,0],[4,0],[4,3],[0,3]],ceiling_height_m=2.5,metric_status='sensor_scaled',
                openings=[dict(edge_index=1,start_fraction=1/3,end_fraction=2/3,height_m=2,kind='doorway')]),
           dict(id='b',corners=[[4,0],[7,0],[7,3],[4,3]],ceiling_height_m=2.5,metric_status='sensor_scaled',
                openings=[dict(edge_index=3,start_fraction=1/3,end_fraction=2/3,height_m=2,kind='doorway')])]
    return dict(rooms=rooms,connections=[dict(rooms=['a','b'],width_m=1,segment=[[4,1],[4,2]])])


def test_generated_assessment_is_evaluable_and_shared_door_counted_once():
    plan=shared_door()
    document=build_assessment(plan,ledger())
    assert document['schema_version']=='internal-assessment-v2'
    assert len(document['openings'])==1
    assert len(document['openings'][0]['surface_ids'])==2
    footprint=next(m for m in document['measurements'] if m['kind']=='footprint_area')
    assert footprint['value']==21
    projection=to_evaluation_plan(document)
    assert projection['openings'][0]['width_m']==pytest.approx(1)
    assert len(projection['connections'])==1
    truth=deepcopy(plan)
    truth['openings']=[dict(id='surveyed_door',rooms=['a','b'],kind='doorway',width_m=1,segment=[[4,1],[4,2]])]
    result=evaluate_assignment(document,truth,'photos')
    assert result['openings']['predicted_count']==1
    assert result['openings']['gate']=='pass'
    assert result['known_gates_pass']
    assert not result['calibrated_known_gates_pass']
    assert not result['assignment_complete']


def test_legacy_room_local_window_is_scored_instead_of_ignored():
    plan=shared_door()
    plan['rooms'][0]['openings'].append(dict(edge_index=0,start_fraction=.25,end_fraction=.5,height_m=1,kind='window'))
    records=to_evaluation_plan(plan)['openings']
    assert len(records)==2
    assert {r['kind'] for r in records}=={'window','doorway'}


def test_unknown_opening_height_keeps_net_area_unavailable():
    plan=shared_door()
    for room in plan['rooms']: room['openings'][0]['height_m']=None
    document=build_assessment(plan,ledger())
    linked=document['openings'][0]['surface_ids']
    assert all(m['value'] is None for m in document['measurements'] if m['kind']=='net_area' and m['entity_id'] in linked)


def test_reference_validation_and_nonfinite_confidence():
    document=build_assessment(shared_door(),ledger())
    document['openings'][0]['surface_ids'].append('missing')
    with pytest.raises(ValueError,match='attachment'): validate_assessment(document)
    document=build_assessment(shared_door(),ledger())
    document['measurements'][0]['interval']['confidence']=float('nan')
    with pytest.raises(ValueError,match='confidence'): validate_assessment(document)


def test_nine_properties_calibrate_but_eight_do_not_and_backend_mismatch_fails():
    document=build_assessment(shared_door(),ledger())
    groups={(m['kind'],m['unit']) for m in document['measurements']}
    records=[dict(property_id=f'p{i}',tier='photos',kind=kind,unit=unit,estimate=3.01,reference=3)
             for i in range(9) for kind,unit in groups]
    calibration=fit_calibration(records,.90,producer_fingerprint='backend')
    assert all(g['radius'] is not None for g in calibration['groups'].values())
    with pytest.raises(ValueError,match='fingerprint'): apply_calibration(document,calibration,'other')
    apply_calibration(document,calibration,'backend')
    assert all(m['interval']['calibrated'] for m in document['measurements'])
    assert document['calibration_status']['status']=='applied'
    assert all(g['radius'] is None for g in fit_calibration([r for r in records if r['property_id']!='p8'],.90)['groups'].values())
    with pytest.raises(ValueError,match='disjoint'):
        fit_calibration(records,.90,audit_property_ids=['p0'])


def test_missing_calibration_groups_never_use_engineering_fallback():
    document=build_assessment(shared_door(),ledger())
    calibration=fit_calibration([dict(property_id=f'p{i}',tier='photos',kind='length',unit='m',estimate=3,reference=3) for i in range(9)],.9)
    apply_calibration(document,calibration)
    assert document['calibration_status']['status']=='incomplete'
    assert next(m for m in document['measurements'] if m['kind']=='ceiling_height')['interval'] is None


def test_assignment_profile_rejects_nested_truth_and_assistance(tmp_path):
    manifest=tmp_path/'capture.json'
    base=dict(schema_version=3,tier='photos',profile='assignment',source='images')
    for extra in ({'config':{'ground_truth':'survey.json'}},{'scale_references':[]},{'poses':[]}):
        manifest.write_text(json.dumps({**base,**extra}))
        with pytest.raises(ValueError): read_manifest(manifest)


def test_assessment_failure_never_means_success_and_assignment_requires_complete():
    item=dict(result={'floor_plan_ready':True},assessment_status='failed',configuration={})
    assert not run_succeeded(item)
    item['assessment_status']='written'
    assert run_succeeded(item)
    item['configuration']['profile']='assignment'
    assert not run_succeeded(item)
    item['contract_complete']=True
    assert run_succeeded(item)


def test_invalid_raw_capture_leaves_structured_intake_failure(tmp_path):
    result=run_capture('photos',tmp_path/'missing',tmp_path/'run')
    assert not run_succeeded(result)
    assert result['result']['stage']=='intake_or_preflight'
    assert result['assessment_status']=='written'
    assert (tmp_path/'run/result/run.json').exists()
    assert (tmp_path/'run/result/report.html').exists()


def test_cache_rejects_changed_producer_and_modified_model(tmp_path):
    (tmp_path/'cameras.bin').write_bytes(b'original')
    prior=dict(inputs={'image':'hash'},sfm_producer_fingerprint='one',sfm_model_sha256=model_files(tmp_path))
    validate_sfm_cache(prior,prior['inputs'],'one',tmp_path)
    with pytest.raises(ValueError,match='producer'): validate_sfm_cache(prior,prior['inputs'],'two',tmp_path)
    (tmp_path/'cameras.bin').write_bytes(b'modified')
    with pytest.raises(ValueError,match='model files'): validate_sfm_cache(prior,prior['inputs'],'one',tmp_path)


def test_rgb_scale_uses_multiview_prior_and_rejects_insufficient_or_inconsistent_support():
    from floorplan.rgb_metric import robust_metric_scale
    records=[dict(image=f'view{i//40}',model_depth_m=4,sfm_depth=2) for i in range(80)]
    scale,evidence=robust_metric_scale(records)
    assert scale==pytest.approx(2)
    assert evidence['support_views']==2
    with pytest.raises(ValueError,match='50'): robust_metric_scale(records[:40])
    for record in records[40:]: record['model_depth_m']=7
    with pytest.raises(ValueError,match='inconsistent'): robust_metric_scale(records)


def test_roomwise_photo_failures_never_invent_a_property(tmp_path,monkeypatch):
    from floorplan.rgb_metric import reconstruct_photo_property
    import floorplan.workflow as workflow
    source=tmp_path/'images'; source.mkdir()
    for name in ['a0.png','a1.png','b0.png','b1.png']: (source/name).write_bytes(b'fixture')
    def failed_reconstruction(manifest,output):
        output.mkdir()
        (output/'run.json').write_text('{}')
        return {'result':{'status':'no_model'}}
    monkeypatch.setattr(workflow,'reconstruct',failed_reconstruction)
    result=reconstruct_photo_property({'a':['a0.png','a1.png'],'b':['b0.png','b1.png']},source,tmp_path/'run','p')
    assert result['missing_room_ids']==['a','b']
    assert not result['floor_plan_ready']
    assert not (tmp_path/'run/artifacts/plan.json').exists()


def test_successful_roomwise_registration_is_not_overridden_by_a_failed_global_model(tmp_path,monkeypatch):
    import floorplan.sfm as sfm
    import floorplan.rgb_metric as rgb
    from floorplan.workflow import reconstruct
    source=tmp_path/'images'; source.mkdir(); (source/'one.png').write_bytes(b'fixture')
    monkeypatch.setattr(sfm,'reconstruct_rgb',lambda *args,**kwargs:dict(model_directory=str(tmp_path/'sparse'),registered_fraction=.25))
    monkeypatch.setattr(rgb,'reconstruct_metric_rgb',lambda *args,**kwargs:dict(status='proposal_requires_review',
        floor_plan_ready=True,experimental_backend=True,registration_coverage_source='verified_per_room_models'))
    manifest=tmp_path/'capture.json'
    manifest.write_text(json.dumps(dict(schema_version=3,tier='photos',source='images',profile='assignment',metric_backend='moge2_experimental')))
    ledger=reconstruct(manifest,tmp_path/'result')
    assert ledger['result']['status']=='proposal_requires_review'
    assert ledger['result']['floor_plan_ready']
    assert not run_succeeded(ledger)  # An experimental/unfilled contract still cannot pass assignment.


def test_calibration_audit_counts_properties_and_reports_small_sample_uncertainty():
    from floorplan.uncertainty import audit_calibration
    records=[dict(property_id=f'p{i}',tier='photos',kind='length',unit='m',estimate=3.1,reference=3) for i in range(9)]
    calibration=fit_calibration(records,.9)
    audit=[dict(property_id='unseen',tier='photos',kind='length',unit='m',estimate=3.01,reference=3) for _ in range(20)]
    result=audit_calibration(audit,calibration)
    group=result['groups']['photos:length:m']
    assert group['audit_properties']==1
    assert group['simultaneous_coverage']==1
    assert group['coverage_sampling_interval']['lower']<.1
    with pytest.raises(ValueError,match='overlaps'): audit_calibration(records,calibration)


def test_v1_shared_door_faces_recover_adjacency_after_deduplication():
    document=build_assessment(shared_door(),ledger())
    document['schema_version']='internal-assessment-v1'
    document['connections']=[]
    first=document['openings'][0]
    second=deepcopy(first)
    second['id']='opening:other_face'
    first['rooms']=['room:a']; second['rooms']=['room:b']
    first['surface_ids']=[first['surface_id']]
    second['surface_id']=next(s['id'] for s in document['surfaces'] if s['room_id']=='room:b' and s.get('edge_index')==3)
    second['surface_ids']=[second['surface_id']]
    document['openings'].append(second)
    for measurement in list(document['measurements']):
        if measurement['entity_id']==first['id']:
            copied=deepcopy(measurement)
            copied.update(id=f"{second['id']}:{copied['kind']}",entity_id=second['id'])
            document['measurements'].append(copied)
    plan=to_evaluation_plan(document)
    assert len(plan['openings'])==1
    assert plan['connections'][0]['rooms']==['room:a','room:b']


def test_two_view_dense_fallback_does_not_require_openmvs_binaries(tmp_path,monkeypatch):
    import pycolmap
    import floorplan.dense as dense
    from floorplan.openmvs import reconstruct_openmvs
    class TwoViews:
        def num_reg_images(self): return 2
    monkeypatch.setattr(pycolmap,'Reconstruction',lambda path:TwoViews())
    monkeypatch.setattr(dense,'reconstruct_dense',lambda *args,**kwargs:{'backend':'two_view'})
    result=reconstruct_openmvs(tmp_path/'model',tmp_path/'images',tmp_path/'out',[],binary_dir=tmp_path/'absent')
    assert result['backend']=='two_view'


def test_calibrated_fields_alone_cannot_promote_disconnected_or_partial_geometry():
    from floorplan.assessment import contract_blockers
    plan=shared_door(); plan['provenance']={'floor_observed':True}
    document=build_assessment(plan,ledger())
    for measurement in document['measurements']:
        measurement['interval']['calibrated']=True
    document['damage_assessment_status']='evaluated'
    ready=ledger(); ready['result']['floor_plan_ready']=True
    assert not contract_blockers(document,ready)
    document['connections']=[]
    assert 'disconnected property adjacency' in contract_blockers(document,ready)
    document['status']='partial'
    assert 'complete geometry not ready' in contract_blockers(document,ready)
