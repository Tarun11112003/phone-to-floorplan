"""Fit reference wall lines inside manually inspected FARO regions, independently
of any prediction. Reference uncertainty is reported, not treated as zero.
"""
import argparse
import json
from pathlib import Path
import numpy as np


def annotate(sample_path,regions_path,output):
    sample=np.load(sample_path)['points']
    spec=json.loads(regions_path.read_text(encoding='utf-8'))
    lines=[]; reports=[]; rng=np.random.default_rng(317)
    for region in spec['walls_in_boundary_order']:
        lo,hi=np.asarray(region['min']),np.asarray(region['max'])
        pts=sample[np.all((sample>=lo)&(sample<=hi),axis=1),:2]
        if len(pts)<100: raise ValueError('Reference region has too little support')
        best=None
        for _ in range(300):
            a,b=pts[rng.choice(len(pts),2,replace=False)]
            delta=b-a
            if np.linalg.norm(delta)<.2: continue
            normal=np.array([-delta[1],delta[0]])/np.linalg.norm(delta)
            mask=abs((pts-a)@normal)<.008
            if best is None or mask.sum()>best.sum(): best=mask
        fit=pts[best]; center=fit.mean(axis=0)
        _,_,vt=np.linalg.svd(fit-center,full_matrices=False)
        normal=vt[-1]; offset=-normal@center
        lines.append((normal,offset))
        reports.append({'wall':region['name'],'region_points':len(pts),'inliers':len(fit),
                        'rms_m':float(np.sqrt(np.mean((fit@normal+offset)**2))),
                        'observed_span_m':float(np.ptp(fit@vt[0]))})
    corners=[]
    for (a,ao),(b,bo) in zip(lines,[*lines[1:],lines[0]]):
        corners.append(np.linalg.solve(np.stack([a,b]),-np.array([ao,bo])).tolist())
    result={'rooms':[{'id':spec['room_id'],'corners':corners}],'connections':[],
            'provenance':{'type':'FARO-derived reference with manually selected wall regions',
                          'sample':str(sample_path),'region_specification':str(regions_path),
                          'wall_fits':reports,'annotation_uncertainty_floor_m':.01,
                          'independently_reviewed':False,'field_certification':False,
                          'limitation':'Extrapolated wall intersections; one scanner station; uncertainty floor is assumed, not a metrology certificate'}}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('sample',type=Path); p.add_argument('regions',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); print(json.dumps(annotate(a.sample,a.regions,a.output),indent=2))
