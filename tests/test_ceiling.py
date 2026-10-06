import numpy as np
from shapely.geometry import Polygon

from floorplan.layout import _observed_ceiling


def _grid(xmax, zmax, y):
    x,z=np.meshgrid(np.linspace(.1,xmax-.1,40),np.linspace(.1,zmax-.1,30))
    return np.column_stack([x.ravel(),np.full(x.size,y),z.ravel()])


def test_broad_observed_ceiling_is_measured_and_cabinet_top_rejected():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    ceiling=_grid(4,3,-2.5)
    cabinet=_grid(.7,.7,-2.1)
    points=np.vstack((ceiling,cabinet))
    planes=[dict(normal=[0,1,0],offset=2.5,rms_m=.002),
            dict(normal=[0,1,0],offset=2.1,rms_m=.002)]
    height,evidence=_observed_ceiling(room,points,planes,np.eye(3),0,[[2,1.5,-1.5]])
    assert height==2.5
    assert evidence['coverage_fraction']>.5


def test_ceiling_missing_when_only_narrow_horizontal_surface():
    room=Polygon([(0,0),(4,0),(4,3),(0,3)])
    points=_grid(.7,.7,-2.5)
    height,evidence=_observed_ceiling(room,points,[dict(normal=[0,1,0],offset=2.5,rms_m=.002)],
                                       np.eye(3),0,[[2,1.5,-1.5]])
    assert height is None and evidence is None
