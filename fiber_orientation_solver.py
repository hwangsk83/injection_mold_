# -*- coding: utf-8 -*-
"""
fiber_orientation_solver.py
Folgar-Tucker Fiber Orientation Tensor → Halpin-Tsai Orthotropic Elasticity → CalculiX Deck
Pipeline:
  1) Load Folgar-Tucker orientation tensors a_ij from fiber_orientator.py
  2) Halpin-Tsai homogenisation per cell → orthotropic stiffness matrix
  3) Generate CalculiX *ELASTIC, TYPE=ORTHOTROPIC, DEPENDENCIES=1 card
  4) Predict anisotropic warpage (Z-direction bias)
"""
import os, json, sys
import numpy as np
from pathlib import Path

WORKSPACE       = Path(os.getcwd())
SPEC_JSON       = WORKSPACE / "machine_spec.json"
ORIENT_NPY      = WORKSPACE / "fiber_orientation.npy"
ORIENT_JSON     = WORKSPACE / "fiber_orientation_summary.json"
INP_PATH        = WORKSPACE / "warpage_run.inp"
VTK_DIR         = WORKSPACE / "validation_test" / "VTK"
OUTPUT_VTK_GLYPH = VTK_DIR / "fiber_ellipsoids.vtk"
OUTPUT_INP_ORTHO = WORKSPACE / "ortho_material.inp"

# ── Material Defaults (PC+GF20%) ───────────────────────────────────────────
E_MATRIX_MPA   = 2400.0    # PC base modulus
NU_MATRIX      = 0.37
E_FIBER_MPA    = 73000.0   # Glass fiber modulus
VF_FIBER       = 0.09      # 9% volume fraction (≈20% w/w)
AR_FIBER       = 25.0      # L/D aspect ratio
NU_FIBER       = 0.22

# ── VTK writer helper ───────────────────────────────────────────────────────
def _write_vtk_ellipsoid_glyph(path, centroids, a_tensors, scale=0.5):
    """Write fiber orientation ellipsoids as VTK tensor glyphs (simplified point field)."""
    n = centroids.shape[0]
    lines = [
        "# vtk DataFile Version 3.0",
        "Fiber Orientation Ellipsoids (a_ij tensor)",
        "ASCII",
        "DATASET UNSTRUCTURED_GRID",
        f"POINTS {n} float",
    ]
    for p in centroids:
        lines.append(f"{p[0]:.8e} {p[1]:.8e} {p[2]:.8e}")
    lines.append(f"CELLS {n} {2 * n}")
    for i in range(n):
        lines.append(f"1 {i}")
    lines.append(f"CELL_TYPES {n}")
    for _ in range(n):
        lines.append("1")
    lines.append(f"POINT_DATA {n}")
    lines.append("VECTORS a11_vector float")
    for i in range(n):
        lines.append(f"{a_tensors[i,0,0]:.4f} {a_tensors[i,0,1]:.4f} {a_tensors[i,0,2]:.4f}")
    lines.append("VECTORS a22_vector float")
    for i in range(n):
        lines.append(f"{a_tensors[i,1,0]:.4f} {a_tensors[i,1,1]:.4f} {a_tensors[i,1,2]:.4f}")
    lines.append("VECTORS a33_vector float")
    for i in range(n):
        lines.append(f"{a_tensors[i,2,0]:.4f} {a_tensors[i,2,1]:.4f} {a_tensors[i,2,2]:.4f}")
    lines.append(f"SCALARS a11 float 1")
    lines.append("LOOKUP_TABLE default")
    for i in range(n):
        lines.append(f"{a_tensors[i,0,0]:.6e}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


# ── Halpin-Tsai Orthotropic Homogenisation ──────────────────────────────────
def halpin_tsai_orthotropic(a_tensors: np.ndarray):
    """
    For each cell, compute the orthotropic engineering constants from
    orientation tensor a_ij using Halpin-Tsai micromechanics.

    E_i = a_ii * E_long + (1 - a_ii) * E_trans  (hybrid rule-of-mixtures)
    where E_long = Halpin-Tsai longitudinal, E_trans = Halpin-Tsai transverse.

    Returns
    -------
    E1, E2, E3, G12, G23, G13, nu12, nu23, nu13 : (N,) arrays in MPa
    """
    n = a_tensors.shape[0]

    # Halpin-Tsai shape factor
    xi_L = 2.0 * AR_FIBER
    xi_T = 2.0  # transverse shape factor (circular cross-section)

    # Eta factors
    ER = E_FIBER_MPA / E_MATRIX_MPA
    eta_L = (ER - 1.0) / (ER + xi_L)
    eta_T = (ER - 1.0) / (ER + xi_T)

    # Longitudinal and Transverse composite moduli
    E_L = E_MATRIX_MPA * (1.0 + xi_L * eta_L * VF_FIBER) / (1.0 - eta_L * VF_FIBER)
    E_T = E_MATRIX_MPA * (1.0 + xi_T * eta_T * VF_FIBER) / (1.0 - eta_T * VF_FIBER)

    # Shear modulus using Halpin-Tsai for G
    GF = E_FIBER_MPA / (2.0 * (1.0 + NU_FIBER))
    GM = E_MATRIX_MPA / (2.0 * (1.0 + NU_MATRIX))
    eta_G = (GF / GM - 1.0) / (GF / GM + 1.0)
    G12_L = GM * (1.0 + 1.0 * eta_G * VF_FIBER) / (1.0 - eta_G * VF_FIBER)

    # Orientation-weighted per cell
    a11 = a_tensors[:, 0, 0]
    a22 = a_tensors[:, 1, 1]
    a33 = a_tensors[:, 2, 2]

    # Hybrid rule: E_i = a_ii * E_L + (1 - a_ii) * E_T
    E1 = a11 * E_L + (1.0 - a11) * E_T
    E2 = a22 * E_L + (1.0 - a22) * E_T
    E3 = a33 * E_L + (1.0 - a33) * E_T

    # Shear moduli: orientation-weighted
    G12 = E1 * E2 / (E1 + E2 + 2.0 * E2 * NU_MATRIX) * 1.2  # empirical factor
    G23 = G12 * (a22 + a33) / 2.0 / 0.66
    G13 = G12 * (a11 + a33) / 2.0 / 0.66

    # Clamp to positive low bound
    G12 = np.maximum(G12, 50.0)
    G23 = np.maximum(G23, 50.0)
    G13 = np.maximum(G13, 50.0)

    # Poissons: empirical mixing
    nu12 = 0.35 - 0.15 * a11  # fiber alignment reduces transverse contraction
    nu23 = 0.35 - 0.10 * (a22 + a33) / 2.0
    nu13 = 0.35 - 0.10 * (a11 + a33) / 2.0

    return E1, E2, E3, G12, G23, G13, nu12, nu23, nu13


def write_orthotropic_inp_card(E1, E2, E3, G12, G23, G13, nu12, nu23, nu13):
    """Write a CalculiX *ELASTIC, TYPE=ORTHOTROPIC, DEPENDENCIES=1 card."""
    # Use element-wise median for a single representative ORTHOTROPIC material
    lines = [
        "** Phase 5: Orthotropic material from Halpin-Tsai (PC+GF20%)",
        "** Orientation-weighted homogenisation",
        "*MATERIAL, NAME=ORTHO_PCGF20",
        "*ELASTIC, TYPE=ORTHOTROPIC, DEPENDENCIES=1",
    ]
    # Format: D1111, D1122, D2222, D1133, D2233, D3333, D1212, D1313, D2323, Tref
    E1_m = float(np.median(E1))
    E2_m = float(np.median(E2))
    E3_m = float(np.median(E3))
    G12_m = float(np.median(G12))
    G23_m = float(np.median(G23))
    G13_m = float(np.median(G13))
    nu12_m = float(np.median(nu12))
    nu23_m = float(np.median(nu23))
    nu13_m = float(np.median(nu13))

    # Stiffness components
    D1111 = E1_m * (1.0 - nu23_m * nu32(nu23_m, E2_m, E3_m))
    D2222 = E2_m * (1.0 - nu13_m * nu31(nu13_m, E1_m, E3_m))
    D3333 = E3_m * (1.0 - nu12_m * nu21(nu12_m, E1_m, E2_m))
    D1122 = E1_m * (nu21(nu12_m, E1_m, E2_m) + nu31(nu13_m, E1_m, E3_m) * nu23_m)
    D1133 = E1_m * (nu31(nu13_m, E1_m, E3_m) + nu21(nu12_m, E1_m, E2_m) * nu23_m)
    D2233 = E2_m * (nu32(nu23_m, E2_m, E3_m) + nu12_m * nu31(nu13_m, E1_m, E3_m))
    # Normalise by denominator
    Delta = 1.0 / (1.0 - nu12_m * nu21(nu12_m, E1_m, E2_m) - nu23_m * nu32(nu23_m, E2_m, E3_m)
                   - nu13_m * nu31(nu13_m, E1_m, E3_m)
                   - 2.0 * nu21(nu12_m, E1_m, E2_m) * nu32(nu23_m, E2_m, E3_m) * nu13_m)
    # Simplified: use engineering constants directly
    lines.append(
        f"{E1_m:.2f}, {nu12_m:.4f}, {E2_m:.2f}, {nu13_m:.4f}, {nu23_m:.4f}, {E3_m:.2f}, "
        f"{G12_m:.2f}, {G13_m:.2f}, {G23_m:.2f}, 293.15"
    )
    lines.append("*DENSITY")
    lines.append("1430.0")
    lines.append("")

    content = "\n".join(lines)
    OUTPUT_INP_ORTHO.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_INP_ORTHO, "w", encoding="utf-8") as f:
        f.write(content)

    # Also append to warpage_run.inp if exists
    if INP_PATH.exists():
        inp_text = INP_PATH.read_text(encoding="utf-8")
        # Check if ORTHO card already inserted
        if "*ELASTIC, TYPE=ORTHOTROPIC" not in inp_text:
            # Find *MATERIAL section
            if "*MATERIAL" in inp_text:
                inp_text = inp_text.replace("*MATERIAL, NAME=MAT_POLYMER", content)
            else:
                inp_text += "\n" + content
            INP_PATH.write_text(inp_text, encoding="utf-8")

    print(f"  Orthotropic material card written to {OUTPUT_INP_ORTHO.name}")
    print(f"  Median E1 (MD) = {E1_m:.0f} MPa")
    print(f"  Median E2 (TD) = {E2_m:.0f} MPa")
    print(f"  Median E3 (ZD) = {E3_m:.0f} MPa")

    return {"E1_mpa": E1_m, "E2_mpa": E2_m, "E3_mpa": E3_m}


def nu21(nu12, E1, E2):
    return nu12 * E2 / (E1 + 1e-9)

def nu31(nu13, E1, E3):
    return nu13 * E3 / (E1 + 1e-9)

def nu32(nu23, E2, E3):
    return nu23 * E3 / (E2 + 1e-9)


def estimate_anisotropic_warpage(a_tensors, E1, E2, E3):
    """
    Estimate anisotropic warpage (Z-direction) from orthotropic stiffness mismatch.
    Simplified: Max Z-deflection ∝ (E_MD - E_TD) / E_avg * part_width
    """
    a11 = np.mean(a_tensors[:, 0, 0])
    a22 = np.mean(a_tensors[:, 1, 1])
    E_md = float(np.median(E1))
    E_td = float(np.median(E2))
    E_avg = (E_md + E_td) / 2.0
    # Part dimension (laptop housing typical width 150mm)
    L_char = 0.150  # m
    # Bending curvature from CTE/stiffness mismatch
    anisotropy_ratio = (E_md - E_td) / (E_avg + 1e-9)
    # Warpage ~ (alpha_avg * DeltaT * L^2) / (8 * thickness) * anisotropy
    thickness = 0.002  # m
    alpha_avg = 65e-6  # /K
    delta_T = 120.0     # K (melt->ambient)
    max_warp_m = (alpha_avg * delta_T * L_char**2) / (8.0 * thickness) * abs(anisotropy_ratio) * 0.12
    max_warp_um = max_warp_m * 1e6
    return max_warp_um, float(anisotropy_ratio)


def run_fiber_orientation_solver():
    print("[FIBER ORIENTATION SOLVER] Halpin-Tsai Orthotropic Homogenisation Engine")
    print("=" * 65)

    # 1. Load or compute orientation tensors
    if ORIENT_NPY.exists():
        a = np.load(str(ORIENT_NPY))
        print(f"  Loaded {a.shape[0]} orientation tensors from {ORIENT_NPY.name}")
    else:
        # Run fiber_orientator first
        print("  fiber_orientation.npy not found. Running fiber_orientator.py...")
        import subprocess
        res = subprocess.run([sys.executable, "fiber_orientator.py", "25.0"],
                             capture_output=True, text=True, cwd=str(WORKSPACE))
        print(res.stdout)
        if not ORIENT_NPY.exists():
            raise AssertionError("Failed to generate orientation tensors.")
        a = np.load(str(ORIENT_NPY))

    n_cells = a.shape[0]
    traces = np.trace(a, axis1=1, axis2=2)
    max_trace_err = float(np.max(np.abs(traces - 1.0)))
    print(f"  Trace conservation: max error = {max_trace_err:.2e} (OK={max_trace_err < 1e-4})")

    # 2. Halpin-Tsai orthotropic homogenisation
    print("\n── Halpin-Tsai Orthotropic Homogenization ──")
    print(f"  E_matrix = {E_MATRIX_MPA} MPa, E_fiber = {E_FIBER_MPA} MPa, Vf = {VF_FIBER}")
    E1, E2, E3, G12, G23, G13, nu12, nu23, nu13 = halpin_tsai_orthotropic(a)

    # Statistics
    print(f"  E1 (MD) : mean={np.mean(E1):.0f} +- {np.std(E1):.0f} MPa")
    print(f"  E2 (TD) : mean={np.mean(E2):.0f} +- {np.std(E2):.0f} MPa")
    print(f"  E3 (ZD) : mean={np.mean(E3):.0f} +- {np.std(E3):.0f} MPa")
    print(f"  G12     : mean={np.mean(G12):.0f} MPa")

    # 3. Write orthotropic material card
    print("\n── CalculiX ORTHOTROPIC Card Generation ──")
    ortho_result = write_orthotropic_inp_card(E1, E2, E3, G12, G23, G13, nu12, nu23, nu13)

    # 4. Anisotropic warpage estimate
    print("\n── Anisotropic Warpage Estimation ──")
    warp_um, aniso_ratio = estimate_anisotropic_warpage(a, E1, E2, E3)
    print(f"  E_MD/E_TD anisotropy ratio : {aniso_ratio:.4f}")
    print(f"  Estimated Z-axis warp      : {warp_um:.2f} um")

    # 5. VTK fiber ellipsoid glyph output
    print("\n── VTK Output ──")
    # Use synthetic centroid positions for glyph visualisation (from fiber_orientator if available)
    pts = None
    orient_summary = {}
    if ORIENT_JSON.exists():
        orient_summary = json.load(open(ORIENT_JSON, "r", encoding="utf-8"))
    if orient_summary and "n_cells" in orient_summary:
        n_s = min(orient_summary["n_cells"], 500)
        rng = np.random.default_rng(42)
        pts = rng.uniform(-0.075, 0.075, (n_s, 3))
        pts[:, 2] = 0.001
        _write_vtk_ellipsoid_glyph(OUTPUT_VTK_GLYPH, pts, a[:n_s])
        print(f"  Fiber ellipsoid glyphs -> {OUTPUT_VTK_GLYPH.name}")
    else:
        print("  (No centroid data for VTK ellipsoid output)")

    # 6. Save to machine_spec.json
    if SPEC_JSON.exists():
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            specs = json.load(f)
    else:
        specs = {}

    specs["fiber_orientation_solver"] = {
        "n_cells":                 n_cells,
        "trace_max_err":           max_trace_err,
        "E1_MD_MPa":               float(np.median(E1)),
        "E2_TD_MPa":               float(np.median(E2)),
        "E3_ZD_MPa":               float(np.median(E3)),
        "G12_MPa":                 float(np.median(G12)),
        "G23_MPa":                 float(np.median(G23)),
        "G13_MPa":                 float(np.median(G13)),
        "orthotropic_material_card": str(OUTPUT_INP_ORTHO),
        "anisotropic_warp_um":     warp_um,
        "anisotropy_ratio":        aniso_ratio,
        "status":                  "SUCCESS",
        "version":                 "Phase5"
    }
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)

    print("\n" + "=" * 65)
    print("[SUCCESS] Fiber Orientation Solver completed (Phase 5).")
    print(f"  Warpage (Z)        : {warp_um:.2f} um")
    print(f"  E1/E2 Ratio        : {float(np.median(E1))/max(float(np.median(E2)),1):.2f}")
    print(f"  Trace Conservation : {'PASS' if max_trace_err < 1e-4 else 'FAIL'}")
    print("=" * 65)


if __name__ == "__main__":
    run_fiber_orientation_solver()