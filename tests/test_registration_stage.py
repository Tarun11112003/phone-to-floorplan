import struct
from types import SimpleNamespace

import pytest
from scripts.experiments.experimental_registration_stage import (BINARIES,image_records,
    replay_registration,require_snapshot_reproduction)
from scripts.diagnostics.audit_registration_stage import gate_saved_replay


def image_record(identity,name='image.png',point_id=9):
    return (struct.pack('<I7dI',identity,1.,0.,0.,0.,0.,0.,0.,identity)+name.encode()+b'\0'
        +struct.pack('<QddQ',1,10.,20.,point_id))


def model(path,identities):
    path.mkdir()
    for name in BINARIES-{'images.bin'}:
        (path/name).write_bytes(name.encode())
    (path/'images.bin').write_bytes(struct.pack('<Q',len(identities))+b''.join(
        image_record(identity) for identity in identities))
    return path


def test_resume_comparison_allows_only_complete_image_record_reordering(tmp_path):
    expected=model(tmp_path/'expected',[8,3]); actual=model(tmp_path/'actual',[3,8])
    result=require_snapshot_reproduction(expected,actual)
    assert result['model_state_exact'] and result['order_only_difference']
    assert result['image_records_exact']==2 and not result['numeric_tolerance_used']
    assert not result['raw_binary_equality']['images.bin']


@pytest.mark.parametrize('variable',['pose','feature','identity','camera','point','missing_file'])
def test_changed_geometry_and_identity_never_pass_reproduction(tmp_path,variable):
    expected=model(tmp_path/'expected',[8,3]); actual=model(tmp_path/'actual',[3,8])
    path=actual/'images.bin'; data=bytearray(path.read_bytes())
    if variable=='pose': data[12]^=1
    if variable=='feature': data[8+64+len('image.png')+1+8]^=1
    if variable=='identity': data[8]=4
    if variable in ('pose','feature','identity'): path.write_bytes(data)
    if variable=='camera': (actual/'cameras.bin').write_bytes(b'different')
    if variable=='point': (actual/'points3D.bin').write_bytes(b'different')
    if variable=='missing_file': (actual/'rigs.bin').unlink()
    with pytest.raises(ValueError): require_snapshot_reproduction(expected,actual)


@pytest.mark.parametrize('data',[b'',struct.pack('<Q',1),struct.pack('<Q',0)+b'noise',
    struct.pack('<Q',2)+image_record(3)*2,struct.pack('<Q',1)+image_record(3)[:-1],
    struct.pack('<Q',1)+struct.pack('<I7dI',3,1.,0.,0.,0.,0.,0.,0.,3)+b'name',
    struct.pack('<Q',1)+struct.pack('<I7dI',3,1.,0.,0.,0.,0.,0.,0.,3)+b'name\0'])
def test_corrupt_binary_records_are_rejected(tmp_path,data):
    path=tmp_path/'images.bin'; path.write_bytes(data)
    with pytest.raises(ValueError): image_records(path)


def test_native_stage_order_captures_accepted_pose_before_tri_and_local_ba():
    calls=[]; mapper_options=object(); tri_options=object(); ba_options=object()
    options=SimpleNamespace(get_mapper=lambda:mapper_options,get_triangulation=lambda:tri_options,
        get_local_bundle_adjustment=lambda:ba_options,ba_local_max_refinements=2,
        ba_local_max_refinement_change=.001)
    class Mapper:
        def register_next_image(self,*args):
            assert args==(mapper_options,31); calls.append('PnP'); return True
        def triangulate_image(self,*args):
            assert args==(tri_options,31); calls.append('triangulate'); return 211
        def iterative_local_refinement(self,*args):
            assert args==(2,.001,mapper_options,ba_options,tri_options,31); calls.append('local')
    def colors(): calls.append('colors'); return True
    assert replay_registration(Mapper(),options,31,calls.append,colors)==211
    assert calls==['before_registration','PnP','accepted_registration','triangulate',
        'after_triangulation','local','after_local_refinement','colors','after_color_extraction']


def test_failed_registration_never_runs_refinement():
    calls=[]
    mapper=SimpleNamespace(register_next_image=lambda *_:False)
    options=SimpleNamespace(get_mapper=lambda:object())
    with pytest.raises(ValueError,match='registration failed'):
        replay_registration(mapper,options,31,calls.append,lambda:pytest.fail('colors'))
    assert calls==['before_registration']


def test_changed_saved_stage_blocks_posthoc_interpretation(tmp_path):
    path=model(tmp_path/'stage',[3])
    record=dict(stages=[dict(path=str(path),binary_sha256={})])
    with pytest.raises(ValueError,match='Captured native stage changed'): gate_saved_replay(record)
