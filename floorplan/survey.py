"""Import independent survey tables for evaluation, never reconstruction."""
import csv
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon,mapping,shape

from .provenance import sha256


def load_survey(root, property_id):
    root=Path(root).resolve(); hashes={}; evidence={}
    def rows(name):
        path=root/name
        hashes[name]=sha256(path)
        with path.open(encoding='utf-8-sig',newline='') as stream:
            result=list(csv.DictReader(stream))
        if any(r.get('property_id')!=property_id for r in result):
            raise ValueError(f'{name}: mixed or incorrect property identities')
        return result
    def observed(row,field='truth_evidence_path'):
        relative=row.get(field)
        if not relative: raise ValueError(f'Missing independent evidence path: {field}')
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('Survey evidence must exist within the survey bundle')
        evidence[relative]=sha256(path)
    def number(row,key,positive=True):
        value=float(row[key])
        if not np.isfinite(value) or (value<=0 if positive else value<0):
            raise ValueError(f'Invalid surveyed {key}')
        return value
    def points(row,key,dimensions):
        value=np.asarray(json.loads(row[key]),float)
        if value.ndim!=2 or value.shape[1]!=dimensions or not np.isfinite(value).all():
            raise ValueError(f'Invalid surveyed {key} coordinates')
        return value
    rooms=[]; room_lookup={}; diagnostics=[]
    for row in rows('rooms.csv'):
        observed(row)
        if not row.get('measurement_method'): raise ValueError('Room measurement method missing')
        corners=points(row,'corners_xz_json',2)
        polygon=Polygon(corners)
        if not polygon.is_valid or polygon.area<=0: raise ValueError('Invalid surveyed room polygon')
        rid=row['room_id']
        if rid in room_lookup: raise ValueError('Duplicate surveyed room identity')
        room=dict(id=rid,label=row.get('label',rid),corners=corners.tolist(),
                  ceiling_height_m=number(row,'ceiling_height_m'),floor_area_m2=number(row,'floor_area_m2'),
                  wall_lengths_m=[None]*len(corners),metric_status='independent_survey')
        diagnostics.append(dict(room_id=rid,declared_area_minus_polygon_m2=room['floor_area_m2']-polygon.area))
        rooms.append(room); room_lookup[rid]=room
    if not rooms: raise ValueError('Survey requires populated rooms.csv, not a blank template')
    walls={}; surfaces=set()
    for row in rows('walls.csv'):
        observed(row)
        if not row.get('measurement_method'): raise ValueError('Wall measurement method missing')
        rid=row['room_id']; index=int(row['wall_index'])
        room=room_lookup[rid]
        if not 0<=index<len(room['corners']) or room['wall_lengths_m'][index] is not None:
            raise ValueError('Invalid or duplicated surveyed wall index')
        length=number(row,'length_m'); number(row,'height_m')
        room['wall_lengths_m'][index]=length
        key=(rid,row['wall_id'])
        if key in walls or row['surface_id'] in surfaces: raise ValueError('Duplicate surveyed wall/surface')
        walls[key]=row; surfaces.add(row['surface_id'])
        endpoints=points({'ends':json.dumps([json.loads(row['start_xyz_m_json']),json.loads(row['end_xyz_m_json'])])},'ends',3)
        diagnostics.append(dict(room_id=rid,wall_index=index,length_minus_endpoints_m=length-float(np.linalg.norm(endpoints[1]-endpoints[0]))))
    if any(any(v is None for v in r['wall_lengths_m']) for r in rooms):
        raise ValueError('Independent survey must measure every room wall')
    openings=[]; seen=set(); connections=[]
    for row in rows('openings.csv'):
        observed(row)
        if row['opening_id'] in seen: raise ValueError('Survey contains duplicate physical opening IDs')
        seen.add(row['opening_id'])
        if row['kind'] not in {'doorway','door','window'}: raise ValueError('Unknown surveyed opening kind')
        wall=walls[(row['room_id'],row['wall_id'])]
        ends=points({'ends':json.dumps([json.loads(row['start_xyz_m_json']),json.loads(row['end_xyz_m_json'])])},'ends',3)
        incident=[row['room_id']]
        if row.get('through_room_id'):
            if row['through_room_id'] not in room_lookup: raise ValueError('Opening links an unknown surveyed room')
            incident.append(row['through_room_id'])
        opening=dict(id=row['opening_id'],rooms=incident,kind=row['kind'],width_m=number(row,'width_m'),
                     height_m=number(row,'height_m'),segment=ends[:,[0,2]].tolist(),
                     attachments=[dict(room_id=row['room_id'],edge_index=int(wall['wall_index']))])
        openings.append(opening)
        if len(incident)==2: connections.append(dict(rooms=incident,width_m=opening['width_m'],opening_id=opening['id']))
    regions=[]; evaluated=set(); region_ids=set()
    for row in rows('damage_regions.csv'):
        observed(row)
        if row['surface_id'] not in surfaces: raise ValueError('Damage annotation links an unknown surveyed surface')
        evaluated.add(row['surface_id'])
        if row['class_name']=='clean_control': continue
        if not row.get('region_id') or row['region_id'] in region_ids:
            raise ValueError('Survey damage region IDs must be nonempty and unique')
        region_ids.add(row['region_id'])
        if row['class_name'] not in {'water_staining','cracking'}: raise ValueError('Unsupported survey damage class')
        polygon=Polygon(points(row,'surface_polygon_uv_m_json',2))
        if not polygon.is_valid or polygon.area<=0: raise ValueError('Invalid damage survey polygon')
        regions.append(dict(id=row['region_id'],surface_id=row['surface_id'],class_name=row['class_name'],
                            surface_geometry=mapping(polygon),area_m2=number(row,'area_m2'),
                            length_m=number(row,'length_m') if row.get('length_m') else None))
    raw=rows('raw_measurements.csv')
    if not raw: raise ValueError('Raw independent measurement readings are required')
    if not any(not row.get('exclusion_reason') for row in raw):
        raise ValueError('At least one nonexcluded raw independent reading is required')
    for row in raw:
        if row.get('exclusion_reason'): continue
        observed(row,'evidence_path'); number(row,'raw_reading')
        if row['unit'] not in {'m','cm','mm','m2'}: raise ValueError('Unknown raw survey units')
        if not all(row.get(k) for k in ('tool_name','tool_model','operator_id','measured_at_utc')):
            raise ValueError('Raw survey tool/operator/time metadata incomplete')
    measurements=[]
    def measure(entity,kind,value,unit,method='independent survey reading'):
        measurements.append(dict(id=f'{entity}:{kind}',entity_id=entity,kind=kind,value=value,unit=unit,method=method))
    for room in rooms:
        entity=f"room:{room['id']}"; height=room['ceiling_height_m']
        measure(entity,'ceiling_height',height,'m')
        measure(f'{entity}:floor','area',room['floor_area_m2'],'m2','surveyed floor area')
        measure(f'{entity}:ceiling','area',room['floor_area_m2'],'m2','horizontal ceiling projection from independently surveyed footprint; slope unavailable')
        for index,length in enumerate(room['wall_lengths_m']):
            wall=next(r for r in walls.values() if r['room_id']==room['id'] and int(r['wall_index'])==index)
            wall_height=number(wall,'height_m'); surface=f'{entity}:wall:{index}'
            deductions=sum(o['width_m']*o['height_m'] for o in openings
                if any(a['room_id']==room['id'] and a['edge_index']==index for a in o['attachments']))
            # Other shared wall faces need explicit survey association before
            # their net area can become a calibration reference.
            unresolved_shared=any(room['id'] in o['rooms'] and o['attachments'][0]['room_id']!=room['id'] for o in openings)
            measure(surface,'length',length,'m'); measure(surface,'height',wall_height,'m')
            measure(surface,'gross_area',length*wall_height,'m2','independent measured length × height')
            measure(surface,'net_area',None if unresolved_shared else max(0.,length*wall_height-deductions),'m2',
                    'independent measured wall area minus surveyed attached apertures; shared-face association required')
    for opening in openings:
        measure(f"opening:{opening['id']}",'width',opening['width_m'],'m')
        measure(f"opening:{opening['id']}",'height',opening['height_m'],'m')
    from shapely.ops import unary_union
    measure(f'property:{property_id}','footprint_area',float(unary_union([Polygon(r['corners']) for r in rooms]).area),
            'm2','union of independent surveyed polygons in one common property frame')
    for region in regions:
        extent=shape(region['surface_geometry']).bounds
        for kind,value,unit in [('area',region['area_m2'],'m2'),('width',extent[2]-extent[0],'m'),('height',extent[3]-extent[1],'m')]:
            measure(region['id'],kind,float(value),unit,'independent surface annotation')
        if region['length_m'] is not None: measure(region['id'],'length',region['length_m'],'m','independent crack centreline survey')
    truth=dict(property_id=property_id,rooms=rooms,openings=openings,connections=connections,measurements=measurements,
               provenance=dict(source='independent survey tables',truth_files_sha256=hashes,
                               evidence_sha256=evidence,consistency_diagnostics=diagnostics,
                               physical_identity_verified=False))
    annotations=(dict(property_id=property_id,regions=regions,evaluated_surface_ids=sorted(evaluated)) if evaluated else None)
    return dict(reference=truth,damage_annotations=annotations,raw_reading_count=len(raw),
                note='Checks data completeness/identity, not physical authenticity or acceptance. An empty damage CSV is unavailable annotation, not a clean room.')
