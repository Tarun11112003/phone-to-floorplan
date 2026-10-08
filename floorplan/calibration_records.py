"""Build calibration residuals from frozen outputs and independent measurements."""
import json
from pathlib import Path

import numpy as np

from .contracts import validate_assessment
from .provenance import sha256


def build_records(cases,root):
    root=Path(root); records=[]; issues=[]; sources=[]; producers=set(); tiers=set()
    seen=set()
    for case in cases:
        directory=root/case['run']; reference_path=root/case['reference']
        assessment=validate_assessment(json.loads((directory/'assessment.json').read_text(encoding='utf-8')))
        ledger=json.loads((directory/'run.json').read_text(encoding='utf-8'))
        reference=json.loads(reference_path.read_text(encoding='utf-8'))
        if ledger.get('code_changed_during_run') is not False: raise ValueError('Calibration needs an unchanged-source frozen run')
        if assessment['property_id']!=reference['property_id']: raise ValueError('Calibration survey property mismatch')
        fingerprint=ledger.get('measurement_producer_fingerprint')
        if not fingerprint: raise ValueError('Calibration run has no producer identity')
        producers.add(fingerprint); tiers.add(assessment['tier'])
        values={m['id']:m for m in reference['measurements']}
        if len(values)!=len(reference['measurements']): raise ValueError('Duplicate independent measurement IDs')
        mapping=case.get('measurement_mapping',{})
        for measurement in assessment['measurements']:
            target=values.get(mapping.get(measurement['id'],measurement['id']))
            if measurement['value'] is None or target is None or target.get('value') is None:
                issues.append(dict(run=case['run'],measurement=measurement['id'],reason='missing estimate or independent measurement')); continue
            if target['unit']!=measurement['unit'] or target['kind']!=measurement['kind']:
                raise ValueError('Calibration measurement units/kinds differ from independent truth')
            if not np.isfinite([measurement['value'],target['value']]).all(): raise ValueError('Calibration measurements must be finite')
            key=(assessment['capture_id'],measurement['id'])
            if key in seen: raise ValueError('Duplicate calibration run/measurement record')
            seen.add(key)
            records.append(dict(property_id=assessment['property_id'],tier=assessment['tier'],
                kind=measurement['kind'],unit=measurement['unit'],estimate=measurement['value'],reference=target['value'],
                measurement_id=measurement['id'],capture_id=assessment['capture_id'],producer_fingerprint=fingerprint))
        sources.append(dict(run=case['run'],run_sha256=sha256(directory/'run.json'),
                            assessment_sha256=sha256(directory/'assessment.json'),reference=case['reference'],
                            reference_sha256=sha256(reference_path)))
    if len(producers)!=1 or len(tiers)!=1:
        raise ValueError('Build one calibration dataset per frozen tier/producer configuration')
    return dict(version='artifact-calibration-records-v1',records=records,sources=sources,
                producer_fingerprint=next(iter(producers)),tier=next(iter(tiers)),
                complete=bool(records) and not issues,issues=issues,
                note='Truth correspondence is evaluation-only. Property identity and independent survey authenticity still require review.')
