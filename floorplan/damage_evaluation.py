"""Independent surface annotation scoring; never imported by reconstruction."""
import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import shape

CLASSES={'water_stain_candidate':'water_staining','crack_candidate':'cracking',
         'water_staining':'water_staining','cracking':'cracking'}


def evaluate_damage(assessment, annotations, minimum_match_iou=.1):
    if assessment['property_id']!=annotations['property_id']:
        raise ValueError('Damage annotations belong to a different property')
    if not 0<minimum_match_iou<=1: raise ValueError('Invalid damage association IoU')
    if 'regions' not in annotations or not annotations.get('evaluated_surface_ids'):
        raise ValueError('Explicit regions and evaluated surfaces are required, including clean controls')
    surfaces=set(annotations['evaluated_surface_ids'])
    mapping=annotations.get('surface_mapping',{})
    predicted=[]; excluded=[]
    for region in assessment.get('damage_regions',[]):
        surface=mapping.get(region['surface_id'],region['surface_id'])
        if surface not in surfaces:
            excluded.append(dict(id=region['id'],reason='surface not independently annotated')); continue
        predicted.append({**region,'surface_id':surface})
    references=annotations['regions']
    for regions in (predicted,references):
        ids=[r.get('id') for r in regions]
        if any(not identity for identity in ids) or len(set(ids))!=len(ids):
            raise ValueError('Damage region IDs must be nonempty and unique')
        for region in regions:
            for key in ('length_m','area_m2'):
                value=region.get(key)
                if value is not None and (not np.isfinite(value) or value<0 or (key=='area_m2' and value==0)):
                    raise ValueError('Damage metric extents must be finite and nonnegative with positive area')
    if any(r['surface_id'] not in surfaces for r in references):
        raise ValueError('Reference region outside evaluated surface set')
    def geometry(region):
        polygon=shape(region['surface_geometry'])
        if not polygon.is_valid or polygon.is_empty or polygon.area<=0 or not np.isfinite(polygon.bounds).all():
            raise ValueError('Damage annotation geometry must be finite with positive area')
        if region['class_name'] not in CLASSES: raise ValueError('Unsupported annotated damage class')
        return polygon
    p=[geometry(r) for r in predicted]; t=[geometry(r) for r in references]
    costs=np.ones((len(p),len(t)))
    for i,a in enumerate(p):
        for j,b in enumerate(t):
            if predicted[i]['surface_id']==references[j]['surface_id'] and CLASSES[predicted[i]['class_name']]==CLASSES[references[j]['class_name']]:
                costs[i,j]=1-a.intersection(b).area/a.union(b).area
    row,col=linear_sum_assignment(costs)
    matches=[]
    for i,j in zip(row,col):
        if 1-costs[i,j]<minimum_match_iou: continue
        length=references[j].get('length_m')
        estimate=predicted[i].get('length_m')
        reference_area=references[j].get('area_m2')
        if reference_area is None: reference_area=float(t[j].area)
        matches.append(dict(prediction=predicted[i]['id'],reference=references[j]['id'],
            class_name=CLASSES[references[j]['class_name']],surface_id=references[j]['surface_id'],
            intersection_over_union=float(1-costs[i,j]),
            predicted_area_m2=float(p[i].area),reference_area_m2=float(reference_area),
            reference_area_source='independent measured area' if references[j].get('area_m2') is not None else 'independent annotation polygon',
            annotation_polygon_area_m2=float(t[j].area),
            area_absolute_error_m2=float(abs(p[i].area-reference_area)),
            width_absolute_error_m=float(abs((p[i].bounds[2]-p[i].bounds[0])-(t[j].bounds[2]-t[j].bounds[0]))),
            height_absolute_error_m=float(abs((p[i].bounds[3]-p[i].bounds[1])-(t[j].bounds[3]-t[j].bounds[1]))),
            length_absolute_error_m=float(abs(estimate-length)) if estimate is not None and length is not None else None))
    matched_p={m['prediction'] for m in matches}; matched_t={m['reference'] for m in matches}
    observed=assessment.get('damage_assessment',{}).get('surfaces_evaluated')
    unobserved=sorted(surfaces-{mapping.get(s,s) for s in observed}) if observed is not None else None
    classes={}
    for label in ('water_staining','cracking'):
        tp=sum(m['class_name']==label for m in matches)
        pc=sum(CLASSES[r['class_name']]==label for r in predicted)
        tc=sum(CLASSES[r['class_name']]==label for r in references)
        classes[label]=dict(true_positives=tp,false_positives=pc-tp,false_negatives=tc-tp,
                           precision=tp/pc if pc else None,recall=tp/tc if tc else None)
    return dict(version='independent-damage-score-v1',status='scored' if assessment.get('damage_assessment_status') not in {'not_evaluated','failed'} else 'inference_not_evaluated',
                classes=classes,matches=matches,
                missed_regions=sorted(r['id'] for r in references if r['id'] not in matched_t),
                phantom_regions=sorted(r['id'] for r in predicted if r['id'] not in matched_p),
                excluded_predictions=excluded,evaluated_surfaces=len(surfaces),
                unobserved_annotated_surfaces=unobserved,
                clean_control_surfaces=sorted(surfaces-{r['surface_id'] for r in references}),
                match_iou=minimum_match_iou,accuracy_validated=False,
                caveat='IoU is an association setting, not an assessment tolerance. No numeric damage acceptance threshold is supplied. Surface mapping is evaluation-only; uv origins and directions must match the independent annotation.')
