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


def fit_calibration(records,confidence=.95,*,producer_fingerprint=None,development_property_ids=(),audit_property_ids=()):
    """One calibration score per property to avoid treating correlated walls as IID."""
    if not 0<confidence<1:
        raise ValueError('confidence must be between zero and one')
    groups={}
    properties=set()
    for row in records:
        if row.get('producer_fingerprint') and producer_fingerprint!=row['producer_fingerprint']:
            raise ValueError('Calibration record producer fingerprint differs from the requested backend')
        if not row.get('property_id'):
            raise ValueError('Each calibration record requires an independent property ID')
        values=[row['estimate'],row['reference']]
        if not np.isfinite(values).all(): raise ValueError('Calibration values must be finite')
        key=f"{row['tier']}:{row['kind']}:{row['unit']}"
        scores=groups.setdefault(key,{})
        property_id=str(row['property_id']); properties.add(property_id)
        if property_id in set(map(str,development_property_ids))|set(map(str,audit_property_ids)):
            raise ValueError('Development, calibration and audit properties must be disjoint')
        if row['unit'] not in {'m','m2'} or row['tier'] not in {'photos','video','lidar','rgbd'}:
            raise ValueError('Invalid calibration tier or unit')
        scores[property_id]=max(scores.get(property_id,0.),abs(float(values[0]-values[1])))
    quantiles={}
    for key,scores in groups.items():
        n=len(scores); rank=math.ceil((n+1)*confidence)
        quantiles[key]=dict(property_count=n,rank=rank,
                            radius=sorted(scores.values())[rank-1] if rank<=n else None,
                            status='finite_sample_quantile' if rank<=n else 'insufficient_independent_properties')
    return dict(version='property-split-conformal-v2' if producer_fingerprint else 'property-split-conformal-v1',confidence=confidence,
                calibration_property_ids=sorted(properties),groups=quantiles,
                development_property_ids=sorted(map(str,development_property_ids)),
                audit_property_ids=sorted(map(str,audit_property_ids)),
                producer_fingerprint=producer_fingerprint,
                assumption='Exchangeable independent development and deployment properties; held-out audit still required')


def calibrated_interval(value,tier,kind,unit,property_id,calibration):
    if str(property_id) in calibration['calibration_property_ids'] or str(property_id) in calibration.get('development_property_ids',[]):
        raise ValueError('Cannot claim held-out calibration on a development property')
    group=calibration['groups'].get(f'{tier}:{kind}:{unit}',{})
    if value is None or group.get('radius') is None:
        return None
    radius=group['radius']
    if not np.isfinite([value,radius]).all() or radius<0 or not 0<calibration['confidence']<1:
        raise ValueError('Invalid calibration radius, confidence or estimate')
    return dict(lower=max(0.,float(value-radius)),upper=float(value+radius),unit=unit,
                confidence=calibration['confidence'],calibrated=True,
                method=calibration['version'],calibration_properties=group['property_count'],
                caveat=calibration['assumption'])


def apply_calibration(document,calibration,producer_fingerprint=None):
    """Replace envelopes after geometry/damage finish; never fill missing groups."""
    if producer_fingerprint is not None and calibration.get('producer_fingerprint')!=producer_fingerprint:
        raise ValueError('Calibration producer fingerprint differs from this measurement backend')
    if document['property_id'] in calibration['calibration_property_ids'] or document['property_id'] in calibration.get('development_property_ids',[]):
        raise ValueError('Cannot claim held-out calibration on a development property')
    missing=[]
    by_entity={}
    for measurement in document['measurements']:
        measurement['interval']=calibrated_interval(measurement['value'],document['tier'],measurement['kind'],
                                                   measurement['unit'],document['property_id'],calibration)
        by_entity[(measurement['entity_id'],measurement['kind'])]=measurement['interval']
        if measurement['value'] is not None and measurement['interval'] is None:
            missing.append(f"{document['tier']}:{measurement['kind']}:{measurement['unit']}")
    for region in document['damage_regions']:
        region['area_interval']=by_entity.get((region['id'],'area'))
        region['length_interval']=by_entity.get((region['id'],'length'))
    for item in document['scope_items']:
        kind='area' if item['unit']=='m2' else 'length'
        item['interval']=by_entity.get((item['source_region_id'],kind))
    complete=bool(document['measurements']) and not missing and all(m['value'] is not None for m in document['measurements'])
    document['calibration_status']=dict(status='applied' if complete else 'incomplete',confidence=calibration['confidence'],
                                      version=calibration['version'],missing_groups=sorted(set(missing)),
                                      producer_bound=producer_fingerprint is not None)
    if complete:
        document['missing_requirements']=[r for r in document['missing_requirements'] if r!='calibrated uncertainty']
    return document


def audit_calibration(records,calibration):
    """Report independent-property simultaneous coverage and exact sampling bounds."""
    from scipy.stats import beta
    grouped={}
    forbidden=set(calibration['calibration_property_ids'])|set(calibration.get('development_property_ids',[]))
    for record in records:
        property_id=str(record['property_id'])
        if property_id in forbidden: raise ValueError('Calibration audit overlaps fitted/development properties')
        if calibration.get('audit_property_ids') and property_id not in calibration['audit_property_ids']:
            raise ValueError('Audit property not in the frozen audit split')
        estimate,reference=record['estimate'],record['reference']
        if not np.isfinite([estimate,reference]).all(): raise ValueError('Audit values must be finite')
        key=f"{record['tier']}:{record['kind']}:{record['unit']}"
        properties=grouped.setdefault(key,{})
        properties[property_id]=max(properties.get(property_id,0.),abs(estimate-reference))
    output={}
    for key,properties in grouped.items():
        group=calibration['groups'].get(key,{})
        radius=group.get('radius')
        if radius is None:
            output[key]=dict(status='missing_finite_calibration',audit_properties=len(properties),coverage=None)
            continue
        covered=sum(error<=radius for error in properties.values()); total=len(properties)
        alpha=1-calibration['confidence']
        lower=float(beta.ppf(alpha/2,covered,total-covered+1)) if covered else 0.
        upper=float(beta.ppf(1-alpha/2,covered+1,total-covered)) if covered<total else 1.
        output[key]=dict(status='audited',audit_properties=total,covered_properties=covered,
                         simultaneous_coverage=covered/total,interval_full_width=2*radius,
                         coverage_sampling_interval=dict(lower=lower,upper=upper,confidence=calibration['confidence']),
                         property_max_errors=properties,
                         observed_nominal_coverage_met=covered/total>=calibration['confidence'])
    missing=sorted(set(calibration['groups'])-set(grouped))
    return dict(version='property-calibration-audit-v1',confidence=calibration['confidence'],groups=output,
                groups_without_audit=missing,accuracy_validated=False,
                caveat='Property counts, not correlated walls. Exchangeability is assumed; a small audit is not population coverage proof.')
