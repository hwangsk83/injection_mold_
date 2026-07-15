# -*- coding: utf-8 -*-
"""
fast_melt_front_advisor.py
Fast Melt Front Propagation Simulator — Flow Resistance & Filling Index
Models:
  - Reduced-order fast-fill simulation on coarse mesh
  - Geodesic flow length estimation from candidate gate nodes
  - Hagen-Poiseuille pressure drop approximation
  - Filling Index tensor => identifies late-fill zones
"""
import os, json, math, sys
import numpy as np
from pathlib import Path
from scipy.spatial import KDTree
import trimesh

WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"
STL_PATH  = WORKSPACE / "validation_test" / "constant" / "triSurface" / "case_model.stl"
FILLING_JSON = WORKSPACE / "filling_index.json"

# Material defaults (PC+GF20%)
ETA_VISCOSITY  = 320.0     # Pa·s (Cross-WLF at 280C, 1000/s)
RHO_MELT       = 1200.0    # kg/m3
U_INJECTION    = 0.25      # m/s


def sample_candidate_nodes(mesh, n_candidates=50):
    """
    Sample n candidate gate positions from mesh vertices.
    Uses farthest-point sampling to spread candidates evenly.
    """
    verts = mesh.vertices
    rng = np.random.default_rng(42)
    if len(verts) <= n_candidates:
        return np.arange(len(verts)), verts

    # Farthest-point sampling
    idx = [rng.integers(0, len(verts))]
    tree = KDTree(verts)
    for _ in range(1, n_candidates):
        dists, _ = tree.query(verts[idx])
        farthest = int(np.argmax(np.min(dists, axis=0)))
        idx.append(farthest)
    return np.array(idx), verts[idx]


def compute_flow_parameters(mesh, candidate_idx, candidate_coords):
    """
    For each candidate gate, compute:
    - Flow length (max geodesic distance to any surface node)
    - Pressure drop (Hagen-Poiseuille)
    - Flow balance index
    """
    verts = mesh.vertices
    tree = KDTree(verts)
    n_candidates = len(candidate_idx)
    results = []

    # Characteristic thickness from bounding box
    thickness = (verts.max(axis=0) - verts.min(axis=0))[2]
    if thickness <= 0:
        thickness = 0.0012  # default 1.2mm

    for i, (cidx, coord) in enumerate(zip(candidate_idx, candidate_coords)):
        # Flow length = max distance from candidate to any other vertex
        dists, _ = tree.query(coord[np.newaxis, :], k=len(verts))
        flow_length = float(np.max(dists))

        # Normalised flow length [0,1]
        flow_len_norm = flow_length / (np.max(dists) + 1e-9)

        # Hagen-Poiseuille pressure drop: ΔP = 12·η·L·U / h²
        delta_p = 12.0 * ETA_VISCOSITY * flow_length * U_INJECTION / (thickness**2 + 1e-12)
        delta_p_norm = delta_p / 1e8  # normalise to 100 MPa scale

        # Wall shear stress at gate
        tau_w = ETA_VISCOSITY * U_INJECTION / (thickness * 0.5 + 1e-12)

        # Filling time estimate: t_fill = V_part / (A_gate * U)
        # Assume pin gate area = pi * (1mm)^2
        A_gate = math.pi * 0.001**2
        V_part = mesh.volume if mesh.volume > 0 else (0.150*0.075*0.0012)
        t_fill = V_part / (A_gate * U_INJECTION + 1e-12)

        results.append({
            "candidate_id": int(i + 1),
            "vertex_idx": int(cidx),
            "coord_mm": [round(float(coord[0])*1000, 4),
                         round(float(coord[1])*1000, 4),
                         round(float(coord[2])*1000, 4)],
            "coord_m": [round(float(coord[0]), 6),
                        round(float(coord[1]), 6),
                        round(float(coord[2]), 6)],
            "flow_length_m": round(flow_length, 6),
            "flow_length_norm": round(float(flow_len_norm), 4),
            "delta_P_Pa": round(delta_p, 2),
            "delta_P_MPa": round(delta_p / 1e6, 4),
            "tau_wall_Pa": round(tau_w, 2),
            "fill_time_s": round(t_fill, 4),
        })

    return results


def compute_filling_index(mesh, candidate_params):
    """
    Compute Filling Index tensor for each surface element.
    FI = 1 - (t_fill_local / t_fill_max)  -> [0,1]
    Low FI (<0.3) = late-fill zone (weldline risk).
    """
    verts = mesh.vertices
    faces = mesh.faces
    n_faces = len(faces)

    # For each face, compute minimum flow length from any candidate
    face_centroids = mesh.triangles_center
    min_flow_len = np.full(n_faces, np.inf)

    for cp in candidate_params:
        c = np.array(cp["coord_m"])
        dists = np.linalg.norm(face_centroids - c, axis=1)
        # Add tortuosity factor (1.3x straight-line for real flow path)
        dists *= 1.3
        min_flow_len = np.minimum(min_flow_len, dists)

    # Filling time per cell: t = L / U_injection
    t_local = min_flow_len / U_INJECTION
    t_max = np.max(t_local) if np.max(t_local) > 0 else 1.0
    FI = 1.0 - (t_local / t_max)

    # Identify late-fill zones (FI < 0.3)
    late_fill_mask = FI < 0.3
    n_late = int(np.sum(late_fill_mask))

    # Write VTK for visualisation
    vtk_path = WORKSPACE / "validation_test" / "VTK" / "filling_index.vtk"
    _write_filling_index_vtk(vtk_path, face_centroids, FI, late_fill_mask)

    return {
        "face_centroids": face_centroids.tolist(),
        "FI_tensor": FI.tolist(),
        "late_fill_mask": late_fill_mask.tolist(),
        "n_late_fill_faces": n_late,
        "total_faces": n_faces,
        "late_fill_ratio": round(n_late / max(n_faces, 1), 4),
        "vtk_filling_index": str(vtk_path),
    }


def _write_filling_index_vtk(path, centroids, FI, late_mask):
    """Write Filling Index as VTK point cloud."""
    n = centroids.shape[0]
    lines = [
        "# vtk DataFile Version 3.0",
        "Filling Index (FI) field",
        "ASCII",
        "DATASET UNSTRUCTURED_GRID",
        f"POINTS {n} float",
    ]
    for p in centroids:
        lines.append(f"{p[0]:.8e} {p[1]:.8e} {p[2]:.8e}")
    lines.append(f"CELLS {n} {2*n}")
    for i in range(n):
        lines.append(f"1 {i}")
    lines.append(f"CELL_TYPES {n}")
    for _ in range(n):
        lines.append("1")
    lines.append(f"POINT_DATA {n}")
    lines.append("SCALARS Filling_Index float 1")
    lines.append("LOOKUP_TABLE default")
    for fi in FI:
        lines.append(f"{fi:.6f}")
    lines.append("SCALARS Late_Fill_Flag int 1")
    lines.append("LOOKUP_TABLE default")
    for lm in late_mask:
        lines.append("1" if lm else "0")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Filling Index VTK -> {path.name}")


def run_fast_fill_advisor():
    """
    Main entry point:
    1. Load mesh
    2. Sample candidate gate nodes
    3. Compute flow parameters per candidate
    4. Compute Filling Index tensor
    5. Save to filling_index.json + machine_spec.json
    """
    print("[FAST MELT FRONT ADVISOR] Reduced-Order Flow Propagation Simulator")
    print("=" * 65)

    # 1. Load mesh
    if STL_PATH.exists():
        mesh = trimesh.load(str(STL_PATH))
    else:
        mesh = trimesh.creation.box(extents=[0.150, 0.075, 0.0012])
    print(f"  Mesh: {len(mesh.vertices)} nodes, {len(mesh.faces)} faces")

    # 2. Sample candidate gate nodes (50 points)
    n_candidates = 50
    cidx, ccoords = sample_candidate_nodes(mesh, n_candidates)
    print(f"  Sampled {n_candidates} candidate gate nodes")

    # 3. Flow parameters for each candidate
    print(f"\n── Flow Parameters (top 5 of {n_candidates} candidates) ──")
    params = compute_flow_parameters(mesh, cidx, ccoords)
    for p in params[:5]:
        print(f"  Candidate {p['candidate_id']:2d}: "
              f"L={p['flow_length_m']*1000:.1f}mm "
              f"dP={p['delta_P_MPa']:.2f}MPa "
              f"t_fill={p['fill_time_s']:.2f}s "
              f"coord=({p['coord_mm'][0]:.1f},{p['coord_mm'][1]:.1f})mm")

    # 4. Filling Index tensor
    print(f"\n── Filling Index Tensor ──")
    fi_result = compute_filling_index(mesh, params)
    print(f"  Late-fill faces (FI<0.3): {fi_result['n_late_fill_faces']}/{fi_result['total_faces']} "
          f"({fi_result['late_fill_ratio']*100:.1f}%)")

    # 5. Save
    fi_config = {
        "n_candidates": n_candidates,
        "candidates": params,
        "filling_index": fi_result,
        "material_viscosity_pa_s": ETA_VISCOSITY,
        "injection_speed_mps": U_INJECTION,
        "status": "SUCCESS",
        "version": "Phase8"
    }
    with open(FILLING_JSON, "w", encoding="utf-8") as f:
        json.dump(fi_config, f, indent=4)
    print(f"\n  Filling index saved -> {FILLING_JSON.name}")

    if SPEC_JSON.exists():
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            specs = json.load(f)
    else:
        specs = {}

    specs["fast_melt_front_advisor"] = fi_config
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)

    print("\n" + "=" * 65)
    print("[SUCCESS] Fast Melt Front Advisor completed (Phase 8).")
    print(f"  Candidates analysed: {n_candidates}")
    print(f"  Late-fill ratio    : {fi_result['late_fill_ratio']*100:.1f}%")
    print("=" * 65)

    return params, fi_result


if __name__ == "__main__":
    run_fast_fill_advisor()