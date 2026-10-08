"""Audit benchmark composition and raw identities; metadata is not accuracy proof."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .provenance import sha256


def audit_manifest(document,root):
    root=Path(root).resolve()
    issues=[]; verified=[]; capture_ids=set(); evidence={}
    def issue(requirement,message): issues.append(dict(requirement=requirement,message=message))
    def resolve(relative):
        path=(root/relative).resolve()
        if not path.is_relative_to(root): raise ValueError('Benchmark asset escapes the bundle root')
        return path
    properties=document.get('properties',[])
    property_ids=[p['property_id'] for p in properties]
    if len(property_ids)!=len(set(property_ids)): issue('REQ-42','Duplicate property IDs')
    split=document.get('split',{})
    parts=[set(split.get(key,[])) for key in ('development_property_ids','calibration_property_ids','held_out_property_ids')]
    if any(parts[i]&parts[j] for i in range(3) for j in range(i)): issue('REQ-42','Development/calibration/audit splits overlap')
    composition_ok=False; damage_ok=False; repeat_ok=False
    for prop in properties:
        rooms=prop.get('rooms',[]); room_ids={r['room_id'] for r in rooms}
        captures=prop.get('captures',[])
        if sum(not r.get('is_connector',False) for r in rooms)>=3 and any(r.get('is_connector') for r in rooms):
            composition_ok=True
        tiers={c.get('tier') for c in captures if not c.get('independent_repeat_of')}
        if tiers!={'photos','video','lidar'}: issue('REQ-21',f"{prop['property_id']}: same-property three-tier captures missing")
        by_id={c['capture_id']:c for c in captures}
        for capture in captures:
            cid=capture['capture_id']
            if cid in capture_ids: issue('REQ-42',f'Duplicate capture ID: {cid}')
            capture_ids.add(cid)
            for field in ('device_model','capture_app','capture_app_version'):
                if not capture.get(field): issue('REQ-06',f'{cid}: {field} missing')
            hashes=capture.get('raw_files_sha256',{})
            if not hashes: issue('REQ-38',f'{cid}: no raw capture hashes')
            actual={}
            for relative,expected in hashes.items():
                path=resolve(relative)
                if not path.is_file(): issue('REQ-38',f'{cid}: asset missing: {relative}'); continue
                actual[relative]=sha256(path)
                if actual[relative]!=expected: issue('REQ-38',f'{cid}: hash mismatch: {relative}')
            if actual and len(actual)==len(hashes) and actual==hashes:
                evidence[cid]=hashlib.sha256(''.join(sorted(actual.values())).encode()).hexdigest()
                verified.append(cid)
            if capture.get('tier')=='photos':
                folders=capture.get('room_photo_folders',[])
                if {f['room_id'] for f in folders}!=room_ids: issue('REQ-02',f'{cid}: photo folders do not cover every room')
                if any(not 2<=f.get('image_count',0)<=8 for f in folders): issue('REQ-02',f'{cid}: expected 2–8 stills per room')
                if capture.get('depth_or_pose_inputs') is not False: issue('REQ-02',f'{cid}: strict input provenance missing')
                for folder in folders:
                    path=resolve(folder['relative_path'])
                    count=sum(p.suffix.lower() in {'.jpg','.jpeg','.png','.heic','.heif'} for p in path.iterdir()) if path.is_dir() else 0
                    if count!=folder.get('image_count'): issue('REQ-02',f'{cid}: actual folder count differs from declaration')
        for capture in captures:
            original=by_id.get(capture.get('independent_repeat_of'))
            if original is None: continue
            a,b=original['capture_id'],capture['capture_id']
            shared=set(capture.get('room_ids',[])) & set(original.get('room_ids',room_ids))
            if original.get('tier')==capture.get('tier') and shared and capture.get('started_independently') is True and a in evidence and b in evidence and evidence[a]!=evidence[b]:
                repeat_ok=True
            else: issue('REQ-22',f'{b}: independent same-tier repeat evidence incomplete or identical')
        damage=prop.get('damage_room',{})
        if damage.get('furnished') is True and damage.get('room_id') in room_ids and len(set(damage.get('staged_classes',[])))>=2:
            damage_ok=True
        for name,relative in prop.get('truth_files',{}).items():
            if not resolve(relative).is_file(): issue('REQ-23',f"{prop['property_id']}: missing truth {name}")
        if not prop.get('truth_files'): issue('REQ-23',f"{prop['property_id']}: no independent survey files")
        consumer=prop.get('consumer_comparison',{})
        if not consumer.get('app_name') or not consumer.get('app_version') or len(set(consumer.get('room_ids',[])))!=2:
            issue('REQ-30',f"{prop['property_id']}: named/versioned two-room consumer comparison missing")
        if not consumer.get('raw_files_sha256'): issue('REQ-38',f"{prop['property_id']}: original consumer export hash missing")
        for relative,expected in consumer.get('raw_files_sha256',{}).items():
            path=resolve(relative)
            if not path.is_file() or sha256(path)!=expected:
                issue('REQ-38',f"{prop['property_id']}: consumer export missing or hash mismatch: {relative}")
    if not composition_ok: issue('REQ-19','Need three non-connector rooms plus a separate connector')
    if not damage_ok: issue('REQ-20','Need a furnished surveyed room with two staged classes')
    if not repeat_ok: issue('REQ-22','No verified distinct raw-hash same-tier room repeat')
    conditions={condition for prop in properties for condition in prop.get('challenge_conditions',[])}
    for condition in ('mirrors','glass','wet_look','low_light'):
        if condition not in conditions: issue('REQ-40',f'Missing labelled condition: {condition}')
    return dict(version='benchmark-composition-audit-v1',metadata_ready=not issues,accuracy_validated=False,
                issues=issues,verified_capture_ids=verified,
                caveat='Hashes identify submitted files, not physical identity or accuracy. Survey quality and declarations require review.')
