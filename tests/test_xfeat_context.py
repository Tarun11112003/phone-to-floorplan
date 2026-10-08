import numpy as np
import pytest
from scripts.experimental_xfeat_context import original_pixels, indexed_matches, validate_snapshot, checkpoint_key_compatibility


def test_xfeat_coordinates_restore_original_resolution_without_feature_reordering():
    points=np.array([[0.,0.],[100.,50.],[1023.,767.]],np.float32)
    np.testing.assert_allclose(original_pixels(points,(1920,1440),(1024,768)), points*1.875)
    for invalid in (np.array([[np.nan,0]]),np.array([[-1,0]]),np.array([[1024,0]])):
        with pytest.raises(ValueError): original_pixels(invalid,(1920,1440),(1024,768))
    with pytest.raises(ValueError): original_pixels(points,(1920,1440),(0,768))


def test_xfeat_indices_keep_identity_and_reverse_only_canonical_pair_columns():
    matches=np.array([[0,3],[2,1]],np.int64)
    a,b,actual=indexed_matches(matches,(3,4),(8,2))
    assert (a,b)==(2,8)
    np.testing.assert_array_equal(actual,[[3,0],[1,2]])
    assert actual.dtype==np.uint32 and actual.flags.c_contiguous
    assert indexed_matches(np.empty((0,2),np.int64),(0,0),(1,2))[2].shape==(0,2)


@pytest.mark.parametrize('matches,counts',[(np.array([[0,0],[0,1]]),(2,2)),
    (np.array([[2,0]]),(2,2)),(np.array([[-1,0]]),(2,2)),(np.array([[0.,0.]]),(2,2))])
def test_xfeat_rejects_corrupt_or_nonmutual_indices(matches,counts):
    with pytest.raises(ValueError): indexed_matches(matches,counts,(1,2))


def test_xfeat_snapshot_requires_pinned_source_and_checkpoint(tmp_path):
    (tmp_path/'LICENSE').write_text('different terms')
    with pytest.raises(ValueError,match='Pinned XFeat'): validate_snapshot(tmp_path)


def test_xfeat_loading_allows_only_documented_computed_buffer_and_training_extractor():
    assert checkpoint_key_compatibility({'weight','extractor.model.net.weight'},
        {'weight','confidence_thresholds'},{'weight'})==dict(
        computed_buffers=['confidence_thresholds'],unused_training_extractor_tensors=1)
    for state,model,parameters in [({'extra','weight'},{'weight'},{'weight'}),
        ({'weight'},{'weight','unknown_buffer'},{'weight'}),
        ({'weight'},{'weight','missing_weight'},{'weight','missing_weight'})]:
        with pytest.raises(ValueError,match='incomplete parameter'): checkpoint_key_compatibility(state,model,parameters)


def test_xfeat_comparison_rejects_different_inputs_or_weakened_downstream_guards():
    from scripts.evaluate_xfeat_context import assert_matched_context
    import copy
    baseline=dict(image_sha256={str(i):str(i) for i in range(32)}, options={'minimum_inliers':15},
        production_code_sha256={'production':'hash'}, temporal_window=list(range(32)),
        target_groups=[['first'],['second']],context_anchors=list(range(8)),graph={'pairs':[{}]*496})
    assert_matched_context(baseline,copy.deepcopy(baseline))
    for field,replacement in [('image_sha256',{}),('options',{'minimum_inliers':10}),
        ('production_code_sha256',{}),('target_groups',[]),('context_anchors',[]),('temporal_window',[])]:
        candidate=copy.deepcopy(baseline);candidate[field]=replacement
        with pytest.raises(ValueError,match='Frozen context'): assert_matched_context(baseline,candidate)
    candidate=copy.deepcopy(baseline);candidate['graph']['pairs'].pop()
    with pytest.raises(ValueError,match='496'): assert_matched_context(baseline,candidate)


def test_xfeat_pair_support_requires_one_saved_landmark_not_only_two_associations():
    from scripts.evaluate_xfeat_context import shared_native_point
    class Point:
        def __init__(self,pid): self.point3D_id=pid
        def has_point3D(self): return self.point3D_id is not None
    assert shared_native_point(Point(12),Point(12))
    assert not shared_native_point(Point(12),Point(13))
    assert not shared_native_point(Point(None),Point(None))
    assert not shared_native_point(Point(12),Point(None))


def test_xfeat_audit_cache_preserves_exact_spread_and_restores_shared_function(monkeypatch):
    from scripts.evaluate_xfeat_context import cached_track_spreads
    import scripts.audit_transition_tracks as module
    original=module.track_spread;calls=[]
    def counted(nodes,coords): calls.append(len(nodes));return original(nodes,coords)
    monkeypatch.setattr(module,'track_spread',counted)
    nodes=[('a',0),('a',1),('b',0)]
    coordinates={'a':np.array([[0.,0.],[17.,2.]]),'b':np.array([[5.,5.]])}
    expected=original(nodes,coordinates)
    with cached_track_spreads() as stats:
        for _ in nodes: assert module.track_spread(nodes,coordinates)==expected
        assert stats==dict(calls=3,component_computations=1,computed_nodes=3)
    assert calls==[3] and module.track_spread is counted
    with pytest.raises(RuntimeError):
        with cached_track_spreads(): raise RuntimeError('audit failed')
    assert module.track_spread is counted
