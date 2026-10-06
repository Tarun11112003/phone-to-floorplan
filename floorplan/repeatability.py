"""Compare independently captured plans using the surveyed wall identities."""
from __future__ import annotations

import numpy as np

from .benchmark import evaluate_polygons


def _wall_lengths_by_reference(plan, truth):
    evaluation=evaluate_polygons(plan,truth)
    rooms={r['id']:r for r in plan['rooms']}
    references={r['id']:r for r in truth['rooms']}
    output={}
    for match in evaluation['room_matches']:
        actual=rooms[match['prediction']]
        reference=references[match['reference']]
        a=np.asarray(actual['corners'],dtype=float)
        b=np.asarray(reference['corners'],dtype=float)
        if len(a)!=len(b):
            continue
        rotation=np.asarray(evaluation['alignment']['rotation'])
        translation=np.asarray(evaluation['alignment']['translation_m'])
        a=a@rotation+translation
        variants=[np.roll(order,offset,axis=0) for order in (a,a[::-1]) for offset in range(len(a))]
        matched=min(variants,key=lambda candidate:np.sum((candidate-b)**2))
        lengths=np.linalg.norm(np.roll(matched,-1,axis=0)-matched,axis=1)
        for edge,length in enumerate(lengths):
            output[(reference['id'],edge)]=float(length)
    return output,evaluation


def evaluate_repeatability(first,second,truth):
    """Score two plans; separate agreement from correctness against independent truth.

    Callers must supply two *independent physical captures*. This function cannot
    prove capture independence from plans alone; retain raw input hashes externally.
    """
    a,eval_a=_wall_lengths_by_reference(first,truth)
    b,eval_b=_wall_lengths_by_reference(second,truth)
    refs={}
    for room in truth['rooms']:
        corners=np.asarray(room['corners'],dtype=float)
        for edge,length in enumerate(np.linalg.norm(np.roll(corners,-1,axis=0)-corners,axis=1)):
            refs[(room['id'],edge)]=float(length)
    walls=[]
    for room_id,edge in sorted(refs):
        key=(room_id,edge)
        left,right=a.get(key),b.get(key)
        threshold=max(.01,.005*refs[key])  # Provisional interpretation of "1 cm or 0.5%".
        difference=abs(left-right) if left is not None and right is not None else None
        walls.append(dict(room_id=room_id,edge_index=edge,first_m=left,second_m=right,
                          reference_m=refs[key],difference_m=difference,threshold_m=threshold,
                          pass_gate=difference is not None and difference<=threshold))
    heights=[]
    a_rooms={m['reference']:next(r for r in first['rooms'] if r['id']==m['prediction']) for m in eval_a['room_matches']}
    b_rooms={m['reference']:next(r for r in second['rooms'] if r['id']==m['prediction']) for m in eval_b['room_matches']}
    for room in truth['rooms']:
        room_id=room['id']
        first_h=a_rooms.get(room_id,{}).get('ceiling_height_m')
        second_h=b_rooms.get(room_id,{}).get('ceiling_height_m')
        measured=room.get('ceiling_height_m')
        spread=abs(first_h-second_h) if first_h is not None and second_h is not None else None
        bias_a=abs(first_h-measured) if first_h is not None and measured is not None else None
        bias_b=abs(second_h-measured) if second_h is not None and measured is not None else None
        heights.append(dict(room_id=room_id,first_m=first_h,second_m=second_h,reference_m=measured,
                            spread_m=spread,first_error_m=bias_a,second_error_m=bias_b,
                            repeat_pass=spread is not None and spread<=.01,
                            accuracy_pass=bias_a is not None and bias_b is not None and max(bias_a,bias_b)<=.015))
    return dict(evaluator_version='assignment-repeatability-provisional-v1',
                wall_repeatability=dict(gate='pass' if walls and all(w['pass_gate'] for w in walls) else 'fail',measurements=walls),
                ceiling_repeatability=dict(gate='pass' if heights and all(h['repeat_pass'] for h in heights) else 'fail',measurements=heights),
                ceiling_accuracy=dict(gate='pass' if heights and all(h['accuracy_pass'] for h in heights) else 'fail'),
                capture_independence_verified=False,
                caveat='Attach distinct raw-capture hashes and survey records before asserting physical repeatability')
