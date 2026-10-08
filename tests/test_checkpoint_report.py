import json

from scripts.evaluation.render_checkpoint_report import snapshot


def test_checkpoint_preserves_unregistered_source_rgb_views(tmp_path):
    ledger=dict(tier='video',runtime_s=5,code_changed_during_run=False,
        result=dict(status='partial',input_frames=2,tracked_frames=2,
            sparse_reconstruction=dict(input_images=24,registered_images=2)))
    (tmp_path/'run.json').write_text(json.dumps(ledger))
    (tmp_path/'assessment.json').write_text(json.dumps(dict(rooms=[],contract_complete=False)))
    record=snapshot('video',tmp_path)
    assert record['source_input_images']==24 and record['source_registered_images']==2
    assert record['input_frames']==2 and record['tracked_frames']==2
    assert not record['geometry_ready'] and not record['contract_complete']


def test_partial_sensor_checkpoint_explains_coverage_without_claiming_truth(tmp_path):
    ledger=dict(tier='lidar',runtime_s=5,code_changed_during_run=False,
        result=dict(status='partial',reason=None,input_frames=100,tracked_frames=100,
            plan_metadata=dict(unclosed_geometry=True,camera_center_coverage_fraction=.35)))
    (tmp_path/'run.json').write_text(json.dumps(ledger))
    (tmp_path/'assessment.json').write_text(json.dumps(dict(rooms=[{'id':'a'}],contract_complete=False)))
    record=snapshot('lidar',tmp_path)
    assert '35.0%' in record['reason'] and 'identities need review' in record['reason']
    assert record['source_input_images'] is None and not record['calibrated']
