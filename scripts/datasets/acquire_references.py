"""Acquire separate reference assets and an unseen ICL sequence."""
import argparse
import csv
import json
from pathlib import Path
from prepare_arkit import BASE, download


def acquire(root):
    records=[]
    arkit=root/'arkitscenes'
    metadata=json.loads((arkit/'SOURCE.json').read_text())
    records.append(download(BASE+'/raw/laser_scanner_point_clouds/laser_scanner_point_clouds_mapping.csv',arkit/'references'/'mapping.csv'))
    rows=list(csv.DictReader((arkit/'references'/'mapping.csv').open()))
    for scene in metadata['scenes']:
        visit=str(int(float(scene['visit_id'])))
        matches=[r for r in rows if str(int(float(r['visit_id'])))==visit]
        # One scanner station per selected venue, explicit coverage limitation.
        for entry in matches[:1]:
            scan=str(int(float(entry['laser_scanner_point_clouds_id'])))
            for suffix in ('.ply','_pose.txt'):
                name=scan+suffix
                records.append(download(f'{BASE}/raw/laser_scanner_point_clouds/{visit}/{name}',arkit/'references'/visit/name))
                (arkit/'references'/'SOURCE.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    for name in ('living_room_traj1_frei_png.tar.gz',):
        records.append(download('https://www.doc.ic.ac.uk/~ahanda/'+name,root/'icl_nuim'/name))
    (root/'reference_acquisition.json').write_text(json.dumps(records,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('root',type=Path)
    acquire(parser.parse_args().root)
