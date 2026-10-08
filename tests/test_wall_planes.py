import numpy as np

from floorplan.layout import _segments,_line,_bounded_corner_network


def test_wall_support_residual_uses_observed_plane_not_axis_projection():
    h,t=np.meshgrid(np.linspace(-1,1,40),np.linspace(0,4,100))
    slope=.05
    points=np.column_stack([1+slope*t.ravel(),h.ravel(),t.ravel()])
    normal=np.array([1.,0,-slope]); normal/=np.linalg.norm(normal)
    planes=[dict(normal=normal,offset=-1/np.sqrt(1+slope*slope),rms_m=0,support=len(points))]
    segments=_segments(points,planes,np.eye(3),1.5)
    assert len(segments)==1
    assert segments[0]['rms_m']<1e-12
    assert segments[0]['axis_projection_rms_m']>.03
    endpoints=np.array(_line(segments[0]).coords)
    assert abs(np.diff(endpoints[:,0])[0])>.15


def test_corner_network_never_extends_through_large_unobserved_gap():
    segments=[dict(axis=0,location=0.,lo=0.,hi=1.),dict(axis=1,location=1.5,lo=-1.,hi=1.)]
    result=_bounded_corner_network(segments)
    assert np.array_equal(np.array(_line(result[0]).coords),[[0,0],[0,1]])


def test_corner_gap_bound_uses_original_observation_not_previous_extension():
    # Each next horizontal fragment is near the last extension, but only the
    # first is within 15 cm of the actually observed vertical endpoint.
    vertical=dict(axis=0,location=0.,lo=0.,hi=1.)
    crosses=[dict(axis=1,location=y,lo=-1.,hi=1.) for y in [1.14,1.28,1.42]]
    network=_bounded_corner_network(crosses+[vertical])
    end=np.array(_line(network[-1]).coords)[1]
    assert end[1]<=1.15
    assert np.allclose(end,[0,1.14])


def test_corner_network_is_independent_of_segment_visit_order():
    import copy
    from shapely.ops import unary_union
    segments=[dict(axis=0,location=0.,lo=0.,hi=1.)]+[
        dict(axis=1,location=y,lo=-1.,hi=1.) for y in [.92,1.07,1.14]]
    forward=unary_union([_line(s) for s in _bounded_corner_network(copy.deepcopy(segments))])
    backward=unary_union([_line(s) for s in _bounded_corner_network(copy.deepcopy(segments[::-1]))])
    assert forward.equals(backward)


def test_depth_noise_does_not_resolve_a_nearly_axis_aligned_wall_as_tilted():
    h,t=np.meshgrid(np.linspace(-1,1,40),np.linspace(0,4,100))
    noise=np.random.default_rng(7).normal(0,.004,h.size)
    points=np.column_stack([1+.00015*t.ravel()+noise,h.ravel(),t.ravel()])
    normal=np.array([1.,0,-.00015]); normal/=np.linalg.norm(normal)
    planes=[dict(normal=normal,offset=-1/np.sqrt(1+.00015**2),rms_m=.004,support=len(points))]
    segments=_segments(points,planes,np.eye(3),1.5)
    assert segments[0]['axis_projection_rms_m']>.003
    assert not segments[0]['plane_line_resolved']
    assert np.diff(np.array(_line(segments[0]).coords)[:,0])[0]==0


def test_measured_endpoint_overshoot_and_roundoff_preserve_two_room_network():
    from shapely.ops import polygonize,unary_union
    # Reduced wall evidence from our generated noisy two-room E2E control.
    segments=[dict(axis=axis,location=location,lo=lo,hi=hi) for axis,location,lo,hi in [
        (0,-.0006575893417021571,-7.0002076889400415,.000029656065529931906),
        (1,-7.0001182269078255,-.0013121056379400498,1.9991627335651094),
        (1,-.0002519289942249996,-.00021832984810543727,3.999951319335689),
        (0,1.9991064589407923,-7.0006124727803,-3.000070337264901),
        (0,3.9996450183167775,-3.0004630980691656,-.0005338224286434632),
        (1,-3.000413096319473,1.9991564901152874,3.999920309081825),
        (1,-4.000131626553619,-.0011289844533406504,1.9997392110560317)]]
    network=_bounded_corner_network(segments)
    rooms=list(polygonize(unary_union([_line(s) for s in network])))
    assert len(rooms)==2
    assert all(p.area>5 for p in rooms)


def test_coplanar_furniture_fragment_cannot_inherit_another_walls_height_support():
    rng=np.random.default_rng(31)
    wall=np.column_stack([np.ones(1200),rng.uniform(-1,1,1200),rng.uniform(0,2,1200)])
    furniture=np.column_stack([np.ones(1200),rng.uniform(.8,1.,1200),rng.uniform(4,6,1200)])
    points=np.vstack([wall,furniture])
    plane=dict(normal=[1,0,0],offset=-1,support=len(points),centroid=[1,0,3],rms_m=0)
    segments=_segments(points,[plane],np.eye(3),1.5)
    assert len(segments)==1
    assert segments[0]['hi']<2.1
