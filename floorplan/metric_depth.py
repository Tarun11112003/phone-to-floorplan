"""Optional, pinned RGB-only depth proposals; sensor comparison is a separate stage."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from .workflow import file_hash

MODEL = 'depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf'
REVISION = '8078d68a9c75a972131914f6afd0c1723be0da7f'


def depth_metrics(predicted, reference, valid):
    predicted=np.asarray(predicted,float); reference=np.asarray(reference,float)
    if predicted.shape != reference.shape or reference.shape != np.asarray(valid).shape:
        raise ValueError('Depth and validity shapes must agree')
    valid=np.asarray(valid,bool)&np.isfinite(reference)&(reference>0)&np.isfinite(predicted)&(predicted>0)
    if not valid.any():
        return dict(valid_pixels=0,status='unavailable')
    p,r=predicted[valid],reference[valid]; error=np.abs(p-r)
    return dict(valid_pixels=int(valid.sum()),status='evaluated',mae_m=float(error.mean()),
                median_absolute_error_m=float(np.median(error)),p95_absolute_error_m=float(np.quantile(error,.95)),
                absolute_relative_error=float(np.mean(error/r)),median_scale_ratio=float(np.median(p/r)),
                fraction_within_2cm=float(np.mean(error<=.02)),scale_aligned=False)


def predict_depth(images, output, cache=None):
    """Accepts image paths only: neither poses nor reference depths enter inference."""
    import torch
    from huggingface_hub import snapshot_download
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    output=Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a fresh prediction directory')
    images=[Path(p).resolve() for p in images]
    if not images: raise ValueError('At least one RGB image is required')
    output.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    cache=Path(cache or Path(__file__).resolve().parents[1]/'.tools'/'hf_cache')
    snapshot=Path(snapshot_download(MODEL,revision=REVISION,cache_dir=str(cache),
                                   allow_patterns=['config.json','preprocessor_config.json','model.safetensors']))
    processor=AutoImageProcessor.from_pretrained(snapshot,local_files_only=True)
    model=AutoModelForDepthEstimation.from_pretrained(snapshot,local_files_only=True,
                                                    use_safetensors=True).eval()
    if model.config.depth_estimation_type != 'metric':
        raise ValueError('Relative-depth checkpoints must not be treated as metres')
    torch.set_num_threads(4)
    records=[]
    for index,path in enumerate(images):
        frame_started=time.perf_counter()
        with Image.open(path) as source:
            rgb=source.convert('RGB')
        inputs=processor(images=rgb,return_tensors='pt')
        with torch.inference_mode():
            depth=model(**inputs).predicted_depth
            depth=torch.nn.functional.interpolate(depth[:,None],size=(rgb.height,rgb.width),
                                                 mode='bicubic',align_corners=False)[0,0].numpy()
        if not np.isfinite(depth).all() or np.any(depth<=0):
            raise ValueError('Model returned invalid metric depths')
        name=f'depth_{index:04d}.npy'; np.save(output/name,depth)
        records.append(dict(image=str(path),image_sha256=file_hash(path),prediction=name,
                            prediction_sha256=file_hash(output/name),runtime_s=time.perf_counter()-frame_started))
    result=dict(model=MODEL,revision=REVISION,unit='m',device='cpu',status='unvalidated_depth_proposal',
                floor_plan_ready=False,accuracy_validated=False,reference_used_for_inference=False,
                runtime_s=time.perf_counter()-started,torch_version=torch.__version__,
                model_files={p.name:file_hash(p) for p in snapshot.iterdir() if p.is_file()},frames=records)
    (output/'predictions.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def benchmark_sensor_agreement(sequence_path,output,count=8):
    """Evaluate raw learned depth against LiDAR, without fitting a reference scale."""
    sequence_path=Path(sequence_path).resolve(); output=Path(output)
    if not 2<=count<=8: raise ValueError('Use 2 to 8 images for this bounded experiment')
    if output.exists() and any(output.iterdir()): raise FileExistsError('Use a fresh experiment directory')
    sequence=json.loads(sequence_path.read_text(encoding='utf-8'))
    indices=np.unique(np.linspace(0,len(sequence['frames'])-1,count,dtype=int))
    frames=[sequence['frames'][i] for i in indices]
    predicted=predict_depth([sequence_path.parent/f['rgb'] for f in frames],output/'predictions')
    results=[]
    for frame,record in zip(frames,predicted['frames']):
        reference_path=sequence_path.parent/frame['depth']
        reference=np.asarray(Image.open(reference_path),float)/sequence.get('depth_scale',1000)
        valid=(reference>=.2)&(reference<=8.)
        evidence=dict(depth_sha256=file_hash(reference_path))
        if 'confidence' in frame:
            confidence_path=sequence_path.parent/frame['confidence']
            valid &= np.asarray(Image.open(confidence_path))>=sequence.get('minimum_confidence',1)
            evidence['confidence_sha256']=file_hash(confidence_path)
        proposal=np.load(output/'predictions'/record['prediction'])
        results.append(dict(frame_id=frame['id'],reference=evidence,**depth_metrics(proposal,reference,valid)))
    result=dict(status='sensor_agreement_only',independent_survey_ground_truth=False,
                model=MODEL,revision=REVISION,sequence_sha256=file_hash(sequence_path),
                scale_fit_to_reference=False,reference_used_for_inference=False,frames=results,
                inference_runtime_s=predicted['runtime_s'])
    (output/'sensor_comparison.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
