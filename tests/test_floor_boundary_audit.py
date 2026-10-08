from shapely.geometry import LineString
from scripts.audit_floor_boundary import enclosure


def walls(left_end=3.,width=2.,height=3.):
    return [LineString([(width,0),(width,height)]),LineString([(0,0),(0,left_end)]),
            LineString([(0,height),(width,height)]),LineString([(0,0),(width,0)])]


def test_four_directional_hits_do_not_prove_a_finite_enclosure():
    result=enclosure(walls(left_end=1))
    assert result['classification']=='finite_extents_do_not_support_bounded_enclosure'
    assert max(result['corner_missing_extent_m'])==2


def test_small_supported_enclosure_retains_the_existing_area_guard():
    result=enclosure(walls(left_end=.3,width=.2,height=.3))
    assert result['classification']=='bounded_enclosure_below_existing_area_guard'
    assert result['infinite_line_enclosure_area_m2']<1


def test_same_wall_hit_in_multiple_directions_is_not_a_closed_room():
    line=LineString([(0,0),(0,3)])
    assert enclosure([line]*4)['classification']=='degenerate_directional_hits'
