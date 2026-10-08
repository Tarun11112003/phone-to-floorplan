import numpy as np

from scripts.experiments.experimental_semantic_walls import removal_mask,upright_turns


def test_unknown_single_view_and_disagreed_points_cannot_be_removed_as_furniture():
    votes=np.array([0,1,2,2,3])
    visible=np.array([0,1,4,3,3])
    assert np.array_equal(removal_mask(votes,visible),[False,False,False,True,True])


def test_roll_normalization_returns_labels_to_original_camera_grid():
    pixels=np.arange(12).reshape(3,4)
    for down,expected in [([0,1,0],0),([1,0,0],-1),([-1,0,0],1),([0,-1,0],2),([0,0,1],0)]:
        turns=upright_turns(np.eye(4),down)
        assert turns==expected
        assert np.array_equal(np.rot90(np.rot90(pixels,turns),-turns),pixels)
