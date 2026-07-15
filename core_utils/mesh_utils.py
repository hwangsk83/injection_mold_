# -*- coding: utf-8 -*-
"""
core_utils.mesh_utils -- trimesh Common Operations
===================================================
Replaces repeated trimesh pattern across 10+ files.

Usage:
    from core_utils.mesh_utils import load_stl, compute_bounds, is_watertight
"""

import numpy as np
from pathlib import Path
from typing import Optional, Tuple


def load_stl(path, default=None):
    """Load an STL via trimesh. Returns mesh or default on failure."""
    p = Path(path)
    if not p.exists():
        return default
    try:
        import trimesh
        return trimesh.load(str(p))
    except Exception:
        return default


def compute_bounds(mesh) -> Tuple[np.ndarray, np.ndarray]:
    """Get (min, max) bounds from trimesh object."""
    if hasattr(mesh, 'bounds') and mesh.bounds is not None:
        return mesh.bounds[0].copy(), mesh.bounds[1].copy()
    if hasattr(mesh, 'vertices') and len(mesh.vertices) > 0:
        v = np.asarray(mesh.vertices)
        return v.min(axis=0), v.max(axis=0)
    return np.zeros(3), np.zeros(3)


def compute_projected_area(mesh, axis: str = 'xy') -> float:
    """Compute projected area on given plane (xy, xz, yz)."""
    try:
        import shapely.geometry as geom
    except ImportError:
        return 0.0
    bounds = compute_bounds(mesh)
    if axis == 'xy':
        dx = bounds[1][0] - bounds[0][0]
        dy = bounds[1][1] - bounds[0][1]
        return dx * dy
    elif axis == 'xz':
        dx = bounds[1][0] - bounds[0][0]
        dz = bounds[1][2] - bounds[0][2]
        return dx * dz
    else:  # yz
        dy = bounds[1][1] - bounds[0][1]
        dz = bounds[1][2] - bounds[0][2]
        return dy * dz


def is_watertight(mesh) -> bool:
    """Check if mesh is watertight (0 boundary edges)."""
    if mesh is None:
        return False
    try:
        return mesh.is_watertight
    except AttributeError:
        return True


def count_free_edges(mesh) -> int:
    """Count boundary edges (non-watertight check)."""
    if mesh is None:
        return 0
    try:
        edges = mesh.edges_unique
        edge_neighbors = mesh.edges_sparse
        free = sum(1 for e in range(len(edges)) if len(edge_neighbors[e].data) < 2)
        return free
    except Exception:
        return 0


def compute_bbox_volume(mesh) -> float:
    """Volume of axis-aligned bounding box."""
    bmin, bmax = compute_bounds(mesh)
    extents = bmax - bmin
    return float(np.prod(extents))


def get_bbox_center(mesh) -> np.ndarray:
    """Center point of bounding box."""
    bmin, bmax = compute_bounds(mesh)
    return (bmin + bmax) / 2.0


# ===================================================================
# In-Memory I/O Acceleration: Multi-Insert STL Boolean Operations
# ===================================================================

def merge_stls_in_memory(stl_paths, debug=False):
    """
    여러 STL 파일을 디스크 I/O 없이 메모리 버퍼(io.BytesIO) 상에서
    읽어 trimesh.boolean.union 으로 순차 병합.

    Parameters
    ----------
    stl_paths : list of str or Path
        병합할 STL 파일 경로 목록
    debug : bool
        True일 경우 각 단계의 상태 출력

    Returns
    -------
    trimesh.Trimesh or None
        병합된 메시 (모든 입력이 유효하면)
    """
    import io
    try:
        import trimesh
    except ImportError:
        if debug:
            print("[merge_stls_in_memory] trimesh not available")
        return None

    meshes = []
    for p in stl_paths:
        path_obj = Path(p)
        if not path_obj.exists():
            if debug:
                print(f"  [SKIP] STL not found: {path_obj}")
            continue
        try:
            # 파일을 메모리 버퍼로 읽기 (디스크에서 읽기는 하지만, 중간 파일 쓰기는 없음)
            with open(path_obj, "rb") as f:
                raw_bytes = f.read()
            buf = io.BytesIO(raw_bytes)
            mesh = trimesh.load(buf, file_type="stl")
            if mesh is not None and len(mesh.vertices) > 0:
                meshes.append(mesh)
                if debug:
                    print(f"  [LOAD] {path_obj.name}: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
            else:
                if debug:
                    print(f"  [EMPTY] {path_obj.name}: mesh is empty or invalid")
        except Exception as e:
            if debug:
                print(f"  [ERROR] Failed to load {path_obj}: {e}")
            continue

    if len(meshes) == 0:
        if debug:
            print("[merge_stls_in_memory] No valid meshes to merge")
        return None

    if len(meshes) == 1:
        if debug:
            print("[merge_stls_in_memory] Only one mesh, no merge needed")
        return meshes[0]

    # 순차 Boolean Union (모든 메시를 하나로 병합)
    combined = meshes[0]
    for i, mesh in enumerate(meshes[1:], start=1):
        try:
            combined = trimesh.boolean.union([combined, mesh], engine="scad")
            if debug:
                print(f"  [UNION {i}/{len(meshes)-1}] verts={len(combined.vertices)}, faces={len(combined.faces)}")
        except Exception as e:
            if debug:
                print(f"  [UNION FAIL {i}] {e}, falling back to concatenation")
            # Boolean 실패 시 단순 concatenation 으로 fallback
            combined = trimesh.util.concatenate([combined, mesh])

    return combined


def export_mesh_to_buffer(mesh, file_type="stl"):
    """
    메시를 메모리 버퍼(io.BytesIO)로 직렬화.
    디스크 쓰기 없이 STL 바이너리 데이터를 반환.

    Parameters
    ----------
    mesh : trimesh.Trimesh
    file_type : "stl" or "obj"

    Returns
    -------
    io.BytesIO or None
    """
    import io
    if mesh is None:
        return None
    try:
        buf = io.BytesIO()
        if file_type == "stl":
            mesh.export(buf, file_type="stl")
        elif file_type == "obj":
            mesh.export(buf, file_type="obj")
        else:
            mesh.export(buf, file_type=file_type)
        buf.seek(0)
        return buf
    except Exception:
        return None


def save_combined_mold(mesh, output_path):
    """
    병합된 최종 메시를 디스크에 한 번만 저장.

    Parameters
    ----------
    mesh : trimesh.Trimesh
    output_path : str or Path
        저장할 파일 경로 (예: "combined_mold.stl")

    Returns
    -------
    bool : 저장 성공 여부
    """
    if mesh is None:
        return False
    try:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(p), file_type="stl")
        return True
    except Exception:
        return False


def pipeline_merge_inserts(stl_paths, output_path, debug=False):
    """
    완전한 In-Memory 가속화 파이프라인:
    STL 목록 -> 메모리 로드 -> Boolean Union -> 단일 파일 저장.

    디스크 중간 파일 쓰기 없이 combined_mold.stl 을 생성한다.

    Parameters
    ----------
    stl_paths : list of str or Path
    output_path : str or Path
    debug : bool

    Returns
    -------
    trimesh.Trimesh or None : 병합된 메시
    """
    if debug:
        print(f"[pipeline_merge_inserts] Merging {len(stl_paths)} STL files in-memory...")
        print(f"  Input: {[Path(p).name for p in stl_paths]}")
        print(f"  Output: {output_path}")

    combined = merge_stls_in_memory(stl_paths, debug=debug)

    if combined is not None:
        success = save_combined_mold(combined, output_path)
        if debug:
            if success:
                print(f"  [OK] Saved combined mold: {output_path}")
                print(f"  Stats: {len(combined.vertices)} verts, {len(combined.faces)} faces")
            else:
                print(f"  [FAIL] Could not save combined mold to {output_path}")
    else:
        if debug:
            print(f"  [FAIL] merge_stls_in_memory returned None")

    return combined


def estimate_memory_footprint(mesh):
    """
    메시의 대략적인 메모리 사용량 추정 (bytes).

    Parameters
    ----------
    mesh : trimesh.Trimesh

    Returns
    -------
    int : estimated bytes
    """
    if mesh is None:
        return 0
    est = 0
    if hasattr(mesh, "vertices") and mesh.vertices is not None:
        est += mesh.vertices.nbytes
    if hasattr(mesh, "faces") and mesh.faces is not None:
        est += mesh.faces.nbytes
    if hasattr(mesh, "vertex_normals") and mesh.vertex_normals is not None:
        est += mesh.vertex_normals.nbytes
    # 대략적인 오버헤드 20%
    est = int(est * 1.2)
    return est
