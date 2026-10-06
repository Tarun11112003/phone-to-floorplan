"""Explicit uncalibrated envelopes and property-held-out conformal calibration."""
from __future__ import annotations

import math
import numpy as np


def engineering_interval(value, radius, unit):
    if value is None:
        return None
    if not np.isfinite([value,radius]).all() or radius<0:
        raise ValueError('Interval values must be finite with nonnegative radius')
    return dict(lower=max(0.,float(value-radius)),upper=float(value+radius),unit=unit,
                confidence=.95,calibrated=False,
                method='geometric perturbation envelope; nominal coverage unverified',
                caveat='Pose bias, model bias and occlusion are not statistically calibrated')


def fit_calibration(records,confidence=.95):
    """One calibration score per property to avoid treating correlated walls as IID."""
    if not 0<confidence<1:
        raise ValueError('confidence must be between zero and one')
    groups={}
    properties=set()
    for row in records:
        if not row.get('property_id'):
            raise ValueError('Each calibration record requires an independent property ID')
        values=[row['estimate'],row['reference']]
        if not np.isfinite(values).all(): raise ValueError('Calibration values must be finite')
        key=f"{row['tier']}:{row['kind']}:{row['unit']}"
        scores=groups.setdefault(key,{})
        property_id=str(row['property_id']); properties.add(property_id)
        scores[property_id]=max(scores.get(property_id,0.),abs(float(values[0]-values[1])))
    quantiles={}
    for key,scores in groups.items():
        n=len(scores); rank=math.ceil((n+1)*confidence)
        quantiles[key]=dict(property_count=n,rank=rank,
                            radius=sorted(scores.values())[rank-1] if rank<=n else None,
                            status='finite_sample_quantile' if rank<=n else 'insufficient_independent_properties')
    return dict(version='property-split-conformal-v1',confidence=confidence,
                calibration_property_ids=sorted(properties),groups=quantiles,
                assumption='Exchangeable independent development and deployment properties; held-out audit still required')


def calibrated_interval(value,tier,kind,unit,property_id,calibration):
    if property_id in calibration['calibration_property_ids']:
        raise ValueError('Cannot claim held-out calibration on a development property')
    group=calibration['groups'].get(f'{tier}:{kind}:{unit}',{})
    if value is None or group.get('radius') is None:
        return None
    radius=group['radius']
    return dict(lower=max(0.,float(value-radius)),upper=float(value+radius),unit=unit,
                confidence=calibration['confidence'],calibrated=True,
                method=calibration['version'],calibration_properties=group['property_count'],
                caveat=calibration['assumption'])
