"""Memory-bounded FARO reference inspection; never imported by inference."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sample_ply(path,max_points=500000):
    types={'double':'<f8','float':'<f4','uchar':'u1','uint8':'u1','int':'<i4','uint':'<u4'}
    fields=[]; count=None; vertex=False
    with path.open('rb') as file:
        if file.readline().strip()!=b'ply': raise ValueError('Expected PLY')
        while True:
            line=file.readline().decode('ascii').strip()
            if not line: raise ValueError('Truncated PLY header')
            if line.startswith('format') and line!='format binary_little_endian 1.0': raise ValueError('Expected little-endian binary PLY')
            if line.startswith('element'):
                _,name,size=line.split(); vertex=name=='vertex'
                if vertex: count=int(size)
            if vertex and line.startswith('property'):
                _,kind,name=line.split(); fields.append((name,types[kind]))
            if line=='end_header': break
        offset=file.tell()
    data=np.memmap(path,dtype=np.dtype(fields),mode='r',offset=offset,shape=(count,))
    rows=data[::max(1,int(np.ceil(count/max_points)))]
    xyz=np.column_stack([rows[k] for k in ('x','y','z')])
    return xyz[np.isfinite(xyz).all(axis=1)],count


def inspect(source,output):
    output.mkdir(parents=True,exist_ok=True)
    points,count=sample_ply(source)
    # Scanner cloud is already expressed in the registered venue frame. The
    # accompanying scanner pose describes the scanner location in that frame.
    np.savez_compressed(output/'reference_sample.npz',points=points)
    low,high=np.quantile(points[:,2],[.03,.97])
    band=points[(points[:,2]>low+.3)&(points[:,2]<min(low+1.8,high-.1))]
    fig,axes=plt.subplots(1,2,figsize=(14,6),layout='constrained')
    axes[0].hexbin(band[:,0],band[:,1],gridsize=350,bins='log',mincnt=1,cmap='magma_r')
    axes[0].set_aspect('equal'); axes[0].set_title('Independent laser: wall-height slice')
    axes[0].set_xlabel('Venue X (m)'); axes[0].set_ylabel('Venue Y (m)')
    axes[1].hist(points[:,2],bins=300,color='#245b78'); axes[1].set_xlabel('Venue Z (m)')
    axes[1].set_title('Reference height distribution')
    fig.savefig(output/'reference_inspection.png',dpi=180); plt.close(fig)
    summary={'input':str(source),'total_points':count,'sample_points':len(points),'z_range_quantiles_m':[low,high],
             'reference_status':'Scanner geometry only; polygon annotations require independent review',
             'inference_used':False}
    (output/'reference_metadata.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('source',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); print(json.dumps(inspect(args.source,args.output),indent=2))
