"""Conservative cycle checks for independently verified rigid capture links."""
import numpy as np


def consistent_edges(count, edges, translation_limit=.15, rotation_limit_deg=5.):
    parents=list(range(count)); tree=[]; accepted=[]; rejected=[]
    def root(i):
        while parents[i]!=i: i=parents[i]
        return i
    def path_transform(source,target):
        queue=[(source,np.eye(4))]; seen={source}
        for node,transform in queue:
            if node==target: return transform
            for edge in tree:
                if edge['a']==node: other=edge['b']; step=edge['transform']
                elif edge['b']==node: other=edge['a']; step=np.linalg.inv(edge['transform'])
                else: continue
                if other not in seen:
                    seen.add(other); queue.append((other,step@transform))
        raise ValueError('Cycle path unavailable')
    for edge in sorted(edges,key=lambda e:(-e['visual_inliers'],-e['fitness'],e['a'],e['b'])):
        a,b=edge['a'],edge['b']; transform=np.asarray(edge['transform'],float)
        if (transform.shape!=(4,4) or not np.isfinite(transform).all()
                or not np.allclose(transform[3],[0,0,0,1])
                or not np.allclose(transform[:3,:3].T@transform[:3,:3],np.eye(3),atol=1e-4)
                or np.linalg.det(transform[:3,:3])<.99):
            rejected.append({**edge,'reason':'invalid rigid transform'}); continue
        cycle=root(a)==root(b)
        record={**edge,'transform':transform,'cycle':cycle}
        if cycle:
            delta=np.linalg.inv(path_transform(a,b))@transform
            distance=float(np.linalg.norm(delta[:3,3]))
            angle=float(np.degrees(np.arccos(np.clip((np.trace(delta[:3,:3])-1)/2,-1,1))))
            record.update(cycle_translation_residual_m=distance,cycle_rotation_residual_deg=angle)
            if distance>translation_limit or angle>rotation_limit_deg:
                rejected.append({**record,'reason':'inconsistent verified cycle'}); continue
        else:
            parents[root(a)]=root(b); tree.append(record)
        accepted.append(record)
    return accepted,rejected


def map_room_identities(source_polygons, rooms, minimum_iou=.5):
    """One-to-one overlap association, withholding ambiguous/lost room identities."""
    from scipy.optimize import linear_sum_assignment
    from shapely.geometry import Polygon
    source=list(source_polygons); targets=[Polygon(r['corners']) for r in rooms]
    costs=np.ones((len(source),len(targets)))
    for i,key in enumerate(source):
        polygon=Polygon(source_polygons[key])
        if not polygon.is_valid or polygon.area<=0: raise ValueError('Invalid transformed source room')
        for j,target in enumerate(targets):
            costs[i,j]=1-polygon.intersection(target).area/polygon.union(target).area
    row,col=linear_sum_assignment(costs)
    matches={source[i]:dict(room_id=rooms[j]['id'],iou=float(1-costs[i,j]))
             for i,j in zip(row,col) if 1-costs[i,j]>=minimum_iou}
    return dict(matches=matches,missing_source_rooms=sorted(set(source)-set(matches)),
                method='one-to-one transformed polygon IoU; no supplied adjacency')
