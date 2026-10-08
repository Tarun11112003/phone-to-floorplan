import sqlite3

import numpy as np

from scripts.experiments.experimental_video_bridge import bridge_diagnostics, shortest_bridge


def test_intermediate_view_must_reach_both_original_groups():
    nodes = ['a', 'b', 'c', 'd', 'bridge1', 'bridge2']
    pairs = [('a','b'), ('c','d'), ('b','bridge1'), ('bridge2','c')]
    assert shortest_bridge(nodes, pairs, {'a','b'}, {'c','d'}) == []
    pairs.append(('bridge1','bridge2'))
    assert shortest_bridge(nodes, pairs, {'a','b'}, {'c','d'}) == ['b','bridge1','bridge2','c']


def test_bridges_outside_target_groups_do_not_count_as_target_connection():
    assert shortest_bridge(['a','b','c'], [('a','c')], {'a'}, {'b'}) == []


def test_verified_bridge_residual_uses_original_keypoint_pixel_coordinates(tmp_path):
    original, candidate = tmp_path/'original.db', tmp_path/'candidate.db'
    for database, extra in ((original, False), (candidate, True)):
        with sqlite3.connect(database) as conn:
            conn.execute('CREATE TABLE images (image_id INTEGER, name TEXT)')
            conn.execute('CREATE TABLE keypoints (image_id INTEGER, rows INTEGER, cols INTEGER, data BLOB)')
            conn.execute('CREATE TABLE two_view_geometries (pair_id INTEGER, rows INTEGER, config INTEGER, data BLOB, F BLOB)')
            conn.executemany('INSERT INTO images VALUES (?,?)',[(1,'a'),(2,'b'),(3,'c'),(4,'d')]+([(5,'bridge')] if extra else []))
            f = np.array([[0.,0.,0.],[0.,0.,-1.],[0.,1.,0.]])
            matches = np.array([[0,0],[1,1]], dtype=np.uint32)
            for a,b in [(1,2),(3,4)]+([(2,5),(3,5)] if extra else []):
                conn.execute('INSERT INTO two_view_geometries VALUES (?,?,?,?,?)',
                             (a*2147483647+b,2,3,matches.tobytes(),f.tobytes()))
            for identifier in range(1,6 if extra else 5):
                points = np.array([[10.,20.],[30.,40.]],dtype=np.float32)
                if identifier==5:
                    points[:,1]+=[0.,1.]
                conn.execute('INSERT INTO keypoints VALUES (?,?,?,?)',(identifier,2,2,points.tobytes()))
    result=bridge_diagnostics(candidate,original,{'bridge'})
    assert result['target_groups_connected']
    assert result['added_view_verified_pair_count']==2
    assert result['shortest_verified_bridge_path']==['b','bridge','c']
    assert all(row['sampson_residual_available'] for row in result['bridge_pair_consistency'])
    assert all(np.isclose(row['max_sampson_px'],1/np.sqrt(2)) for row in result['bridge_pair_consistency'])
