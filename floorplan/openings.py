"""Conservative aperture proposals from wall support and observed through-rays.

Empty occupancy alone is not an opening: require two actual camera views,
observed jambs and a header. Closed-door appearance detection is not implemented.
"""
from __future__ import annotations

import numpy as np


def detect_wall_openings(endpoints,height_m,floor,observations,cell_m=.04):
    import cv2
    if height_m is None or floor is None: return []
    a,b=np.asarray(endpoints,float); length=float(np.linalg.norm(b-a))
    if length<.5 or height_m<.5: return []
    direction=(b-a)/length; normal=np.array([-direction[1],direction[0]])
    width=int(np.ceil(length/cell_m)); height=int(np.ceil(height_m/cell_m))
    wall=np.zeros((height,width),np.int32); visible=np.zeros_like(wall)
    raw=[]; seen_cameras=set()
    def cells(u,h):
        good=(u>=0)&(u<length)&(h>=0)&(h<height_m)
        return np.column_stack([np.floor(h[good]/cell_m).astype(int),np.floor(u[good]/cell_m).astype(int)])
    for view in observations:
        points=np.asarray(view['points'],float); camera=np.asarray(view['camera'],float)
        if len(points)==0: continue
        identity=tuple(np.round(camera,5))
        if identity in seen_cameras: continue
        seen_cameras.add(identity)
        delta=points[:,[0,2]]-a
        u=delta@direction; h=floor-points[:,1]
        signed=delta@normal
        supported=np.abs(signed)<.05
        raw.append(np.column_stack([u[supported],h[supported]]))
        hits=cells(u[supported],h[supported])
        if len(hits): np.add.at(wall,(hits[:,0],hits[:,1]),1)
        rays=points-camera
        denominator=rays[:,[0,2]]@normal
        t=np.divide((a-camera[[0,2]])@normal,denominator,out=np.full(len(points),np.nan),where=np.abs(denominator)>1e-8)
        through=(t>0)&(t<1)&(np.abs(signed)>.12)&np.isfinite(t)
        intersections=camera+rays[through]*t[through,None]
        ray_cells=cells((intersections[:,[0,2]]-a)@direction,floor-intersections[:,1])
        if len(ray_cells):
            ray_cells=np.unique(ray_cells,axis=0)
            visible[ray_cells[:,0],ray_cells[:,1]]+=1
    if not raw: return []
    samples=np.concatenate(raw)
    # Close small sampling holes in through-ray support, not wall evidence.
    support=cv2.morphologyEx((visible>=2).astype(np.uint8),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    aperture=(support>0)&(wall==0)
    count,labels,stats,_=cv2.connectedComponentsWithStats(aperture.astype(np.uint8),8)
    result=[]
    for index in range(1,count):
        x,y,w,h,area=stats[index]
        lo,hi=x*cell_m,(x+w)*cell_m
        bottom,top=y*cell_m,(y+h)*cell_m
        if hi-lo<.25 or top-bottom<.4 or lo<.08 or hi>length-.08 or area/(w*h)<.65: continue
        vertical=(samples[:,1]>bottom+.08)&(samples[:,1]<top-.08)
        left=samples[vertical&(samples[:,0]>=lo-.10)&(samples[:,0]<=lo+.04),0]
        right=samples[vertical&(samples[:,0]>=hi-.04)&(samples[:,0]<=hi+.10),0]
        header=samples[(samples[:,0]>lo+.08)&(samples[:,0]<hi-.08)&(samples[:,1]>=top-.04)&(samples[:,1]<=top+.12),1]
        if min(len(left),len(right),len(header))<8: continue
        refined_lo=float(np.quantile(left,.95)); refined_hi=float(np.quantile(right,.05))
        refined_top=float(np.quantile(header,.05))
        doorway=bottom<=.16
        if doorway:
            refined_bottom=0.
        else:
            sill=samples[(samples[:,0]>lo+.08)&(samples[:,0]<hi-.08)&(samples[:,1]>=bottom-.12)&(samples[:,1]<=bottom+.04),1]
            if len(sill)<8: continue
            refined_bottom=float(np.quantile(sill,.95))
        if refined_hi<=refined_lo or refined_top<=refined_bottom: continue
        result.append(dict(start_fraction=refined_lo/length,end_fraction=refined_hi/length,
                           width_m=refined_hi-refined_lo,height_m=refined_top-refined_bottom,
                           sill_height_m=refined_bottom,kind='doorway' if doorway else 'window',
                           evidence='observed jamb/header and depth rays through aperture in >=2 views',
                           boundary_method='coarse occupancy proposal, unbinned edge quantiles',review_required=True))
    return result


def augment_room_openings(rooms,metadata,observations):
    """Refine traversed apertures and add supported windows/exterior doors."""
    basis=np.asarray(metadata['basis_columns_in_input'])
    aligned=[dict(points=np.asarray(v['points'])@basis,camera=np.asarray(v['camera'])@basis) for v in observations]
    count=0
    for room in rooms:
        corners=np.asarray(room['corners'],float)
        for edge,(a,b) in enumerate(zip(corners,np.roll(corners,-1,axis=0))):
            analysis_height=room.get('ceiling_height_m'); floor=room.get('floor_level_m',metadata.get('floor_level_m'))
            if analysis_height is None and floor is not None:
                # A jamb/header can be observed without seeing the ceiling.
                # Use supported wall extent only as a raster domain; it never
                # becomes a reported ceiling or opening height measurement.
                direction=(b-a)/np.linalg.norm(b-a); normal=np.array([-direction[1],direction[0]])
                support=[]
                for view in aligned:
                    points=view['points']; delta=points[:,[0,2]]-a
                    u=delta@direction; h=floor-points[:,1]
                    valid=(np.abs(delta@normal)<.05)&(u>=0)&(u<=np.linalg.norm(b-a))&(h>0)&(h<8)
                    support.extend(h[valid].tolist())
                if len(support)>=40: analysis_height=float(np.quantile(support,.995))
            proposals=detect_wall_openings([a,b],analysis_height,floor,aligned)
            for proposal in proposals:
                proposal['edge_index']=edge
                midpoint=(proposal['start_fraction']+proposal['end_fraction'])/2
                existing=next((o for o in room['openings'] if o['edge_index']==edge and o['start_fraction']<=midpoint<=o['end_fraction']),None)
                if existing is not None: existing.update(proposal)
                else: room['openings'].append(proposal)
                count+=1
    metadata['opening_observations']=dict(proposals=count,method='wall-aperture-through-rays-v1',
                                         limitations=['Closed-door appearance detection unavailable','Glass/occlusion may make apertures unobservable',
                                                      'Measurement precision needs independent calibration'])
