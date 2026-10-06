"""CPU geometric refinement and pose graph; all transforms are camera-to-world."""
from __future__ import annotations

import numpy as np


def optimize_poses(clouds, poses, features=None, intrinsics=None, keyframe_stride=5):
    import open3d as o3d
    from .rgbd import _relative_pose
    import cv2

    reg = o3d.pipelines.registration
    ids = sorted(set(range(0, len(poses), keyframe_stride)) | {len(poses)-1})
    graph = reg.PoseGraph()
    pcs = []
    for i in ids:
        pc = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(clouds[i]))
        pc = pc.voxel_down_sample(0.04)
        pc.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=0.15, max_nn=30))
        pcs.append(pc)
        graph.nodes.append(reg.PoseGraphNode(poses[i].copy()))
    accepted, rejected = [], []
    for a in range(len(ids)):
        # Bounded candidate search: sequential plus nearby historical keyframes.
        candidates = [a-1] if a else []
        historical = [b for b in range(max(0, a-4)) if np.linalg.norm(poses[ids[a]][:3,3]-poses[ids[b]][:3,3]) < 1.0]
        candidates += sorted(historical, key=lambda b: np.linalg.norm(poses[ids[a]][:3,3]-poses[ids[b]][:3,3]))[:2]
        for b in candidates:
            loop = b != a-1
            initial = np.linalg.inv(poses[ids[b]]) @ poses[ids[a]]
            if loop:
                if features is None:
                    continue  # Geometry alone can falsely join repetitive rooms.
                try:
                    initial, quality = _relative_pose(features[ids[a]], features[ids[b]], intrinsics, cv2)
                    if quality['metric_inliers'] < 40:
                        raise ValueError('weak visual loop')
                except ValueError:
                    continue
            fit = reg.registration_icp(pcs[a], pcs[b], 0.10, initial,
                reg.TransformationEstimationPointToPlane(reg.TukeyLoss(k=0.04)),
                reg.ICPConvergenceCriteria(max_iteration=40))
            delta = np.linalg.inv(initial) @ fit.transformation
            valid = bool(fit.fitness >= 0.3 and fit.inlier_rmse < 0.04 and np.linalg.norm(delta[:3,3]) < 0.15)
            transform = fit.transformation if valid else initial
            if loop and not valid:
                rejected.append([ids[a], ids[b]])
                continue
            info = reg.get_information_matrix_from_point_clouds(pcs[a], pcs[b], 0.08, transform)
            graph.edges.append(reg.PoseGraphEdge(a, b, transform, info, uncertain=loop))
            accepted.append({'source': ids[a], 'target': ids[b], 'loop': loop, 'icp_accepted': valid,
                             'fitness': fit.fitness, 'rmse_m': fit.inlier_rmse})
    if len(ids) > 1:
        reg.global_optimization(graph, reg.GlobalOptimizationLevenbergMarquardt(),
            reg.GlobalOptimizationConvergenceCriteria(),
            reg.GlobalOptimizationOption(max_correspondence_distance=0.08, edge_prune_threshold=0.25, reference_node=0))
    # Interpolate corrections on SE(3), avoiding discontinuities at keyframes.
    from scipy.spatial.transform import Rotation, Slerp
    corrections = np.array([node.pose @ np.linalg.inv(poses[i]) for i, node in zip(ids, graph.nodes)])
    result = []
    for i, pose in enumerate(poses):
        right = min(int(np.searchsorted(ids, i, side='right')), len(ids)-1)
        left = max(0, right-1)
        if left == right:
            correction = corrections[left]
        else:
            t = (i-ids[left])/(ids[right]-ids[left])
            correction = np.eye(4)
            correction[:3,:3] = Slerp([0,1], Rotation.from_matrix(corrections[[left,right],:3,:3]))([t]).as_matrix()[0]
            correction[:3,3] = (1-t)*corrections[left,:3,3]+t*corrections[right,:3,3]
        result.append(correction @ pose)
    return result, {'keyframes': len(ids), 'edges': accepted, 'rejected_loop_edges': rejected,
                    'verified_loops': sum(e['loop'] for e in accepted)}
