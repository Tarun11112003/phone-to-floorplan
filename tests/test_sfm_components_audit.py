import pytest

from scripts.audit_sfm_components import connected_components


def test_pair_graph_keeps_isolated_images_and_transitive_components():
    assert connected_components([1, 2, 3, 4, 5, 6], [(1, 3), (2, 3), (5, 6)]) == [[1, 2, 3], [5, 6], [4]]


def test_unknown_pair_image_is_not_silently_discarded():
    with pytest.raises(ValueError, match='unknown image'):
        connected_components([1, 2], [(1, 3)])
