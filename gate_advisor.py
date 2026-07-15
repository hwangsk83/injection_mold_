# -*- coding: utf-8 -*-
"""
gate_advisor.py
Heuristic Gate Recommendation Engine — Top-3 Optimal Gate Positions
Scoring: S = w1*(1/FlowLen) + w2*WeldAvoid + w3*(1/dP)
with Critical Area (rib/boss/A-surface) weldline avoidance.
"""
import os, json, math
import numpy as np
from pathlib import Path
from scipy.spatial import KDTree
import trimesh

WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"
FILLING_JSON = WORKSPACE / "filling_index.json"
STL_PATH = WORKSPACE / "validation_test" / "constant" / "triSurface" / "case_model.stl"

# Scoring weights
W1_FLOW = 0.40   # flow balance importance
W2_WELD = 0.35   # weldline avoidance
W3_DP   = 0.25   # pressure drop minimisation


def load_filling_data():
    if FILLING_JSON.exists():
        with open(FILLING_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    print("[WARN] filling_index.json not found. Run fast_melt_front_advisor.py first.")
    return None


def define_critical_zones(mesh):
    """
    Define critical areas (A-Surface, rib/boss) that must avoid weldlines.
    Returns a KDTree for fast query of critical coordinates.
    """
    verts = mesh.vertices
    # A-Surface: top 30% of Z (exterior visible face)
    z_max = verts[:, 2].max()
    z_min = verts[:, 2].min()
    z_critical = z_min + 0.7 * (z_max - z_min)
    critical_mask = verts[:, 2] >= z_critical
    critical_pts = verts[critical_mask]

    if len(critical_pts) == 0:
        critical_pts = verts.copy()

    # Rib/boss regions: areas near centre with high curvature (simplified: centre region)
    cx = (verts[:, 0].max() + verts[:, 0].min()) / 2.0
    cy = (verts[:, 1].max() + verts[:, 1].min()) / 2.0
    centre_dist = np.sqrt((verts[:, 0] - cx)**2 + (verts[:, 1] - cy)**2)
    rib_mask = centre_dist < 0.02  # 20mm radius centre region
    rib_pts = verts[rib_mask]

    critical_all = np.vstack([critical_pts, rib_pts]) if len(rib_pts) > 0 else critical_pts
    tree = KDTree(critical_all)
    return tree, critical_all


def predict_weldlines(mesh, candidate_coords, candidate_idx):
    """
    Simplified weldline prediction: weldline forms where two flow fronts meet.
    For each pair of candidates, compute the meeting line.
    """
    verts = mesh.vertices
    weldline_pts = []
    opts = candidate_coords
    n_opts = len(opts)

    for i in range(n_opts):
        for j in range(i + 1, n_opts):
            if j >= n_opts:
                break
            mid = (opts[i] + opts[j]) / 2.0
            # Weldline is approximately at mid-point between gates
            weldline_pts.append(mid)

    if not weldline_pts:
        return np.zeros((0, 3))
    return np.array(weldline_pts)


def score_candidates(filling_data, mesh):
    """
    Score each candidate gate and return Top-3.
    S = w1*(1/FlowLen_norm) + w2*WeldAvoid + w3*(1/dP_norm)
    """
    if filling_data is None:
        return []

    candidates = filling_data.get("candidates", [])
    if not candidates:
        return []

    # Normalise flow length and pressure drop across all candidates
    flow_lens = np.array([c["flow_length_norm"] for c in candidates])
    dPs = np.array([c["delta_P_MPa"] for c in candidates])

    inv_flow = 1.0 / (flow_lens + 0.01)
    inv_dp = 1.0 / (dPs + 0.01)

    inv_flow_norm = inv_flow / (np.max(inv_flow) + 1e-9)
    inv_dp_norm = inv_dp / (np.max(inv_dp) + 1e-9)

    # Critical zones & weldline prediction
    crit_tree, crit_pts = define_critical_zones(mesh)
    candidate_coords = np.array([c["coord_m"] for c in candidates])
    candidate_idx = np.array([c["vertex_idx"] for c in candidates])
    weldline_pts = predict_weldlines(mesh, candidate_coords, candidate_idx)
    weld_tree = KDTree(weldline_pts) if len(weldline_pts) > 0 else None

    scored = []
    for i, c in enumerate(candidates):
        coord = np.array(c["coord_m"])

        # Weldline avoidance: check if candidate is far from critical zones
        dist_to_crit, _ = crit_tree.query(coord)
        weld_avoid = min(1.0, dist_to_crit / 0.05)  # normalise to 50mm

        # Penalty if weldline predicted on critical zone
        if weld_tree is not None:
            # Check if any weldline point is too close to critical zone
            weld_dists, _ = weld_tree.query(crit_pts)
            if np.min(weld_dists) < 0.01:  # 10mm from weldline -> penalty
                weld_avoid *= 0.3  # 70% penalty

        # Total score
        S = W1_FLOW * inv_flow_norm[i] + W2_WELD * weld_avoid + W3_DP * inv_dp_norm[i]

        scored.append({
            "candidate_id": c["candidate_id"],
            "coord_mm": c["coord_mm"],
            "coord_m": c["coord_m"],
            "scores": {
                "flow_balance": round(float(W1_FLOW * inv_flow_norm[i]), 4),
                "weld_avoidance": round(float(W2_WELD * weld_avoid), 4),
                "pressure_drop": round(float(W3_DP * inv_dp_norm[i]), 4),
                "total": round(float(S), 4),
            },
            "flow_length_mm": round(c["flow_length_m"] * 1000, 2),
            "delta_P_MPa": c["delta_P_MPa"],
        })

    # Sort by total score descending
    scored.sort(key=lambda x: x["scores"]["total"], reverse=True)
    return scored


def generate_reasoning(gate):
    """Generate human-readable recommendation reason."""
    s = gate["scores"]
    reasons = []
    if s["flow_balance"] > 0.15:
        reasons.append("optimal flow balance")
    if s["weld_avoidance"] > 0.1:
        reasons.append("avoids A-surface weldline")
    if s["pressure_drop"] > 0.1:
        reasons.append("minimal pressure drop")
    if gate["delta_P_MPa"] < 50:
        reasons.append("low cavity pressure")
    if gate["flow_length_mm"] < 100:
        reasons.append("short flow path")
    return ", ".join(reasons) if reasons else "balanced candidate"


def run_gate_advisor():
    print("[GATE ADVISOR] Heuristic Gate Recommendation Engine")
    print("=" * 65)

    filling_data = load_filling_data()
    if filling_data is None:
        print("  Running fast_melt_front_advisor.py first...")
        import subprocess
        subprocess.run([sys.executable, "fast_melt_front_advisor.py"], cwd=str(WORKSPACE))
        filling_data = load_filling_data()

    if STL_PATH.exists():
        mesh = trimesh.load(str(STL_PATH))
    else:
        mesh = trimesh.creation.box(extents=[0.150, 0.075, 0.0012])

    print(f"  Scoring {len(filling_data.get('candidates', []))} candidates...")
    scored = score_candidates(filling_data, mesh)

    if not scored:
        print("[FAIL] No candidates scored.")
        return

    top3 = scored[:3]
    print(f"\n── Top-3 Recommended Gate Positions ──")
    for i, g in enumerate(top3):
        s = g["scores"]
        reason = generate_reasoning(g)
        print(f"  #{i+1}: Gate {g['candidate_id']} "
              f"coord=({g['coord_mm'][0]:.1f},{g['coord_mm'][1]:.1f},{g['coord_mm'][2]:.2f})mm")
        print(f"       Score: {s['total']:.4f} "
              f"(flow={s['flow_balance']:.3f}, weld={s['weld_avoidance']:.3f}, dP={s['pressure_drop']:.3f})")
        print(f"       dP={g['delta_P_MPa']:.2f}MPa, L={g['flow_length_mm']:.1f}mm")
        print(f"       Reason: {reason}")
        print()

    # Save to machine_spec.json
    recommendation = {
        "top3": top3,
        "weights": {"w1_flow": W1_FLOW, "w2_weld": W2_WELD, "w3_dp": W3_DP},
        "total_candidates_analysed": len(scored),
        "status": "SUCCESS",
        "version": "Phase8",
    }
    if SPEC_JSON.exists():
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            specs = json.load(f)
    else:
        specs = {}
    specs["gate_advisor"] = recommendation
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)

    print("=" * 65)
    print("[SUCCESS] Gate Advisor completed (Phase 8).")
    print(f"  Top-3 gates recommended with reasoned scores.")
    print("=" * 65)
    return top3


if __name__ == "__main__":
    run_gate_advisor()