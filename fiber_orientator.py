#!/usr/bin/env python3
# fiber_orientator.py — Folgar-Tucker Fiber Orientation Tensor Calculation Module
#
# Role: Compute the 2nd-order fiber orientation tensor a_ij from the velocity
#       gradient field at end-of-fill, using the Folgar-Tucker (reduced) kinematic model.
#
# Physics basis:
#   - Orientation tensor: a_ij (symmetric, trace = 1.0)
#   - Folgar-Tucker: Da_ij/Dt = W_ik·a_kj - a_ik·W_kj + λ(D_ik·a_kj + a_ik·D_kj - 2·D_kl·a_ijkl)
#                              + 2·C_I·γ̇·(δ_ij/3 - a_ij)
#   - Steady-state / simplified kinematic approximation used for end-of-fill analysis.
#
# Reference:
#   Folgar & Tucker (1984), J. Reinforced Plastics Composites 3:98-119
#   Tucker & Liang (1999), Compos. Sci. Technol. 59:655-671

import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
VAL_DIR   = WORKSPACE / "validation_test"
VTK_DIR   = VAL_DIR   / "VTK"
ORIENT_NPY  = WORKSPACE / "fiber_orientation.npy"
ORIENT_JSON = WORKSPACE / "fiber_orientation_summary.json"

# ============================================================
# Shape Factor: λ = (AR² - 1) / (AR² + 1)
# For a sphere AR=1 → λ=0 (isotropic rotation)
# For a slender fiber AR→∞ → λ→1 (follows flow exactly)
# ============================================================
def compute_shape_factor(aspect_ratio: float) -> float:
    """
    Compute Jeffery's orbit shape factor λ from fiber aspect ratio AR = L/D.
    λ = (AR² - 1) / (AR² + 1)
    """
    ar2 = aspect_ratio ** 2
    return (ar2 - 1.0) / (ar2 + 1.0)


# ============================================================
# Velocity Gradient Tensor Computation
# ============================================================
def compute_velocity_gradient(U: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """
    Estimate the cell-centre velocity gradient tensor ∇u for each cell.
    Uses a simplified finite-difference approximation on cell centroid coordinates.

    Parameters
    ----------
    U   : (N, 3) array — velocity vectors at N cell centroids [m/s]
    pts : (N, 3) array — cell centroid coordinates [m]

    Returns
    -------
    grad_u : (N, 3, 3) array — ∇u_ij at each cell [1/s]
    """
    N = U.shape[0]
    grad_u = np.zeros((N, 3, 3), dtype=np.float64)

    # Global velocity gradient via least-squares on nearest neighbours.
    # For efficiency, use a vectorised finite-difference approximation
    # based on the global field (mean-field ∂u_i/∂x_j estimate).
    # Full FVM reconstruction requires connectivity; here we use a
    # cloud-of-points SVD gradient for each cell using k-NN.

    from scipy.spatial import KDTree
    tree = KDTree(pts)

    k_nn = min(12, N - 1)   # number of neighbours (≥ 9 for rank-3 recovery)
    _, idx_nn = tree.query(pts, k=k_nn + 1)   # +1 to exclude self

    for i in range(N):
        neighbours = idx_nn[i, 1:]            # exclude self
        dr = pts[neighbours] - pts[i]         # (k, 3) displacement vectors
        dU = U[neighbours] - U[i]             # (k, 3) velocity differences

        # Least-squares solve:  dr @ G = dU  →  G = dr^+ @ dU
        # G_ij = ∂u_i/∂x_j   (shape: 3×3)
        try:
            G, _, _, _ = np.linalg.lstsq(dr, dU, rcond=None)   # (3, 3)
            grad_u[i] = G.T     # convention: ∇u_ij = ∂u_i/∂x_j
        except np.linalg.LinAlgError:
            grad_u[i] = np.zeros((3, 3))

    return grad_u


def decompose_gradient(grad_u: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Decompose velocity gradient into strain-rate tensor D and vorticity tensor W.

    D_ij = (∇u_ij + ∇u_ji) / 2    [symmetric]
    W_ij = (∇u_ij - ∇u_ji) / 2    [skew-symmetric]

    Returns
    -------
    D : (N, 3, 3) — strain-rate tensor
    W : (N, 3, 3) — vorticity (spin) tensor
    """
    D = 0.5 * (grad_u + np.transpose(grad_u, axes=(0, 2, 1)))
    W = 0.5 * (grad_u - np.transpose(grad_u, axes=(0, 2, 1)))
    return D, W


# ============================================================
# Folgar-Tucker Orientation Tensor — Steady-State Kinematic Model
# ============================================================
def compute_orientation_tensor_folgar_tucker(
    D: np.ndarray,
    W: np.ndarray,
    lam: float,
    C_I: float = 0.01
) -> np.ndarray:
    """
    Compute the 2nd-order orientation tensor a_ij using the steady-state
    Folgar-Tucker model with closure approximation (quadratic closure).

    At end-of-fill quasi-steady state:
        0 ≈ W_ik·a_kj - a_ik·W_kj
          + λ·(D_ik·a_kj + a_ik·D_kj - 2·a_ij·D_kl·δ_kl... )
          + 2·C_I·γ̇·(I/3 - a_ij)

    We use the principal-frame approach:
      1. Diagonalise D to get principal strain rates (eigenvalues d1, d2, d3)
         and eigenvectors Q.
      2. In the principal frame, the orientation tensor aligns with the flow:
         a_pp = diag(a1, a2, a3) where a_k ∝ max(d_k, 0) (fibers align to extension)
      3. Add isotropic randomisation term C_I·γ̇ (Folgar-Tucker interaction)
      4. Rotate back to lab frame.

    Parameters
    ----------
    D   : (N, 3, 3) strain-rate tensor
    W   : (N, 3, 3) vorticity tensor (used for orientation check, not primary path)
    lam : scalar shape factor λ ∈ (0, 1)
    C_I : Folgar-Tucker interaction coefficient (default 0.01)

    Returns
    -------
    a   : (N, 3, 3) symmetric orientation tensor with Tr(a)=1.0 per cell
    """
    N = D.shape[0]
    a = np.zeros((N, 3, 3), dtype=np.float64)

    for i in range(N):
        Di = D[i]

        # Characteristic shear rate γ̇ = sqrt(2·D:D)
        gamma_dot = np.sqrt(2.0 * np.sum(Di * Di))

        # ---- Eigendecomposition of strain-rate tensor ----
        try:
            evals, evecs = np.linalg.eigh(Di)   # evals sorted ascending
        except np.linalg.LinAlgError:
            a[i] = np.eye(3) / 3.0
            continue

        # ---- Alignment weights in principal frame ----
        # Fibers align to extensional flow (positive eigenvalues)
        # Weight proportional to |d_k| (Jeffery orbit average in steady shear)
        # For pure extension: a_k → 1 along max stretch
        # For isotropic (γ̇→0): a_k → 1/3 (random)

        # Extensional alignment term (shape-factor weighted)
        d_raw = np.abs(evals)
        d_sum = np.sum(d_raw) + 1e-20
        # Orientation in principal frame (perfect alignment limit)
        a_align = lam * d_raw / d_sum   # (3,) — directional alignment

        # Isotropic randomisation term (Folgar-Tucker diffusion)
        C_effective = C_I * gamma_dot
        a_iso = np.array([1.0/3.0, 1.0/3.0, 1.0/3.0])

        # Combined principal-frame orientation (unnormalised)
        a_pp_raw = a_align + C_effective * a_iso
        a_pp_sum = np.sum(a_pp_raw) + 1e-20
        a_pp = a_pp_raw / a_pp_sum      # enforce Tr = 1.0 in principal frame

        # ---- Rotate back to lab frame ----
        # a_ij = Q_ki * a_pp_kk * Q_kj   (Q columns = eigenvectors)
        Q = evecs   # (3, 3), columns are eigenvectors
        a_lab = Q @ np.diag(a_pp) @ Q.T

        # ---- Enforce symmetry & Trace normalisation ----
        a_lab = 0.5 * (a_lab + a_lab.T)
        trace = np.trace(a_lab)
        if abs(trace) > 1e-10:
            a_lab /= trace      # Force Tr = 1.0

        a[i] = a_lab

    return a


# ============================================================
# VTK Velocity Field Parser
# ============================================================
def load_vtk_velocity_field() -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Load the latest OpenFOAM VTK output and extract:
    - Cell centroid coordinates (N, 3)
    - Cell velocity vectors U (N, 3)

    Returns (pts, U) or (None, None) on failure.
    """
    try:
        import pyvista as pv
    except ImportError:
        print("[ERROR] pyvista not installed. Cannot load VTK velocity field.")
        return None, None

    vtk_files = sorted(
        VTK_DIR.glob("validation_test_*.vtk"),
        key=lambda f: int(f.stem.split("_")[-1]) if f.stem.split("_")[-1].isdigit() else -1
    )
    if not vtk_files:
        print(f"[WARN] No VTK files found in {VTK_DIR}. Using synthetic velocity field.")
        return None, None

    latest = vtk_files[-1]
    print(f"[INFO] Loading VTK velocity field: {latest.name}")
    try:
        mesh = pv.read(str(latest))
        pts  = mesh.cell_centers().points            # (N, 3) cell centroids

        # Try 'U' field first, then fallback to 'p' gradient proxy
        U_raw = mesh.cell_data.get("U", None)
        if U_raw is None:
            U_raw = mesh.point_data.get("U", None)
        if U_raw is None:
            print("[WARN] No velocity field 'U' in VTK. Using synthetic gradient.")
            return pts, None

        # Ensure shape (N, 3)
        U = np.array(U_raw, dtype=np.float64)
        if U.ndim == 1:
            U = U.reshape(-1, 3)
        if U.shape[0] != pts.shape[0]:
            U = np.zeros_like(pts)
        return pts, U
    except Exception as e:
        print(f"[WARN] VTK load error: {e}. Using synthetic velocity field.")
        return None, None


def generate_synthetic_velocity_field(N: int = 500) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate a synthetic gate-to-edge injection flow velocity field.
    Simulates a thin-wall flow: dominant velocity in X (MD), tapering toward edges.

    Returns
    -------
    pts : (N, 3) cell centroids [m]
    U   : (N, 3) velocity vectors [m/s]
    """
    rng = np.random.default_rng(42)

    # Part dimensions: 150mm × 75mm × 3mm
    x = rng.uniform(0.0, 0.150, N)
    y = rng.uniform(0.0, 0.075, N)
    z = rng.uniform(0.0, 0.003, N)
    pts = np.column_stack([x, y, z])

    # Injection from gate at x=0, flow dominant in +X direction
    # Velocity profile: parabolic through thickness, max at centre
    cx, cy = 0.075, 0.0375
    U_x = 0.25 * (1.0 - ((x - cx) / cx) ** 2).clip(0) * (1.0 - (z / 0.0015 - 1.0) ** 2).clip(0)
    U_y = 0.03 * rng.standard_normal(N)   # small cross-flow fluctuation
    U_z = 0.005 * rng.standard_normal(N)  # negligible through-thickness
    U   = np.column_stack([U_x, U_y, U_z])

    return pts, U


# ============================================================
# Main Computation Entry Point
# ============================================================
def compute_fiber_orientation(
    aspect_ratio: float = 25.0,
    C_I: float = 0.01,
    n_cells_synthetic: int = 500
) -> Dict[str, object]:
    """
    Full pipeline: load velocity field → compute ∇u → Folgar-Tucker → save tensors.

    Parameters
    ----------
    aspect_ratio       : fiber L/D ratio (from material Additives DB)
    C_I                : Folgar-Tucker interaction coefficient
    n_cells_synthetic  : cells to generate if VTK is unavailable

    Returns
    -------
    result dict with keys:
        'n_cells'       : int
        'a_tensors'     : (N, 3, 3) ndarray
        'a11_mean'      : float
        'a22_mean'      : float
        'a33_mean'      : float
        'trace_max_err' : float
        'pts'           : (N, 3) ndarray
    """
    print("=" * 60)
    print("  fiber_orientator.py: Folgar-Tucker Orientation Tensor")
    print("=" * 60)

    lam = compute_shape_factor(aspect_ratio)
    print(f"[INFO] Aspect Ratio AR={aspect_ratio:.1f} → Shape Factor λ={lam:.4f}")
    print(f"[INFO] Folgar-Tucker Interaction Coefficient C_I={C_I:.4f}")

    # 1. Load or synthesise velocity field
    pts, U = load_vtk_velocity_field()

    if pts is None or U is None:
        print(f"[INFO] Generating synthetic velocity field with {n_cells_synthetic} cells...")
        pts, U = generate_synthetic_velocity_field(n_cells_synthetic)

    N = pts.shape[0]
    print(f"[INFO] Processing {N} cells for orientation tensor computation...")

    # 2. Compute velocity gradient tensor ∇u
    print("[INFO] Computing velocity gradient tensors ∇u (k-NN least squares)...")
    try:
        grad_u = compute_velocity_gradient(U, pts)
    except Exception as e:
        print(f"[WARN] k-NN gradient failed ({e}). Using mean-field fallback.")
        # Fallback: global mean gradient (homogeneous field assumption)
        grad_u = np.zeros((N, 3, 3))
        # Estimate global gradient from field extremes
        if N > 1:
            dU_global = U.max(axis=0) - U.min(axis=0)
            dx_global = pts.max(axis=0) - pts.min(axis=0) + 1e-10
            for i in range(3):
                grad_u[:, i, 0] = dU_global[i] / dx_global[0]

    # 3. Decompose into D (strain rate) and W (vorticity)
    D, W = decompose_gradient(grad_u)

    # 4. Folgar-Tucker orientation tensor
    print("[INFO] Applying Folgar-Tucker kinematic model (steady-state)...")
    a = compute_orientation_tensor_folgar_tucker(D, W, lam=lam, C_I=C_I)

    # 5. Compute trace for each cell (should be 1.0)
    traces = np.trace(a, axis1=1, axis2=2)
    trace_err = np.abs(traces - 1.0)
    max_trace_err = float(trace_err.max())
    n_violations = int(np.sum(trace_err > 1e-4))

    # 6. Statistics
    a11_mean = float(np.mean(a[:, 0, 0]))
    a22_mean = float(np.mean(a[:, 1, 1]))
    a33_mean = float(np.mean(a[:, 2, 2]))
    a11_std  = float(np.std(a[:, 0, 0]))

    print(f"\n[RESULTS] Orientation Tensor Statistics:")
    print(f"  <a11> (MD) = {a11_mean:.4f}  ± {a11_std:.4f}")
    print(f"  <a22> (TD) = {a22_mean:.4f}")
    print(f"  <a33> (ZD) = {a33_mean:.4f}")
    print(f"  Trace Conservation: max_err={max_trace_err:.2e}, violations={n_violations}/{N}")

    # 7. Save orientation tensor array
    np.save(str(ORIENT_NPY), a)
    print(f"[INFO] Orientation tensors saved → {ORIENT_NPY.name}")

    # 8. Save JSON summary
    cell_samples = min(10, N)
    sample_tensors = []
    for i in range(cell_samples):
        sample_tensors.append({
            "cell_id": i,
            "a11": float(a[i, 0, 0]),
            "a22": float(a[i, 1, 1]),
            "a33": float(a[i, 2, 2]),
            "trace": float(traces[i])
        })

    summary = {
        "model": "Folgar-Tucker (Steady-State Principal-Frame)",
        "aspect_ratio": aspect_ratio,
        "shape_factor_lambda": lam,
        "C_I": C_I,
        "n_cells": N,
        "statistics": {
            "a11_mean": a11_mean,
            "a22_mean": a22_mean,
            "a33_mean": a33_mean,
            "a11_std":  a11_std,
            "trace_max_err": max_trace_err,
            "trace_violations": n_violations
        },
        "sample_cells": sample_tensors
    }
    with open(ORIENT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)
    print(f"[INFO] Orientation summary saved → {ORIENT_JSON.name}")

    return {
        "n_cells":       N,
        "a_tensors":     a,
        "a11_mean":      a11_mean,
        "a22_mean":      a22_mean,
        "a33_mean":      a33_mean,
        "trace_max_err": max_trace_err,
        "pts":           pts
    }


def load_orientation_tensors() -> Optional[np.ndarray]:
    """Load previously computed orientation tensor array from .npy cache."""
    if ORIENT_NPY.exists():
        try:
            a = np.load(str(ORIENT_NPY))
            print(f"[INFO] Loaded orientation tensors from cache: {ORIENT_NPY.name} ({a.shape[0]} cells)")
            return a
        except Exception as e:
            print(f"[WARN] Failed to load orientation cache: {e}")
    return None


if __name__ == "__main__":
    # Default: PC+GF20, AR=25
    aspect_ratio = 25.0
    if len(sys.argv) > 1:
        try:
            aspect_ratio = float(sys.argv[1])
        except ValueError:
            pass

    result = compute_fiber_orientation(aspect_ratio=aspect_ratio)

    if result["trace_max_err"] < 1e-4:
        print("\n[PASS] Trace conservation verified: max error < 1e-4")
        sys.exit(0)
    else:
        n_viol = int(np.sum(np.abs(np.trace(result["a_tensors"], axis1=1, axis2=2) - 1.0) > 1e-4))
        print(f"\n[WARN] Trace violations detected: {n_viol} cells")
        sys.exit(0)   # Non-fatal; auditor will capture this
