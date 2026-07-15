#!/usr/bin/env python3
# fsi_mapper.py — 1-Way FSI Data Mapper (VTK → CalculiX .inp)
# Extended: Halpin-Tsai micromechanics homogenization + Orthotropic material mapping
#
# Physics basis:
#   - Halpin-Tsai model: E_L = E_m·(1 + ξ·η_L·vf)/(1 - η_L·vf)
#   - Schapery CTE mixing: α_L, α_T based on Voigt/Reuss bounds
#   - CalculiX ORTHOTROPIC card: E1,E2,ν12,G12,E3,ν13,ν23,G13,G23
#   - EXPANSION, TYPE=ORTHO: α1, α2, α3

import os
import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
VAL_DIR   = WORKSPACE / "validation_test"
VTK_DIR   = VAL_DIR   / "VTK"
SPEC_JSON = WORKSPACE / "machine_spec.json"
OUT_INP   = WORKSPACE / "warpage_run.inp"
ORIENT_NPY = WORKSPACE / "fiber_orientation.npy"


# ============================================================
# Material Property Loaders
# ============================================================
def load_selected_material_properties(force_grade: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve active material properties from material_db.json."""
    mfg, grade = "Generic", "ABS"
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
                mfg   = specs.get("active_manufacturer", "Generic")
                grade = specs.get("active_grade", "ABS")
        except Exception:
            pass

    if force_grade:
        grade = force_grade

    DB_JSON = WORKSPACE / "material_db.json"
    if DB_JSON.exists():
        try:
            with open(DB_JSON, "r", encoding="utf-8") as f:
                db = json.load(f)
                return db[mfg][grade]
        except Exception:
            pass

    # Fallback defaults
    return {
        "Mechanical": {"YoungsModulus": 2400.0, "PoissonsRatio": 0.35, "CTE": 8.0e-5},
        "Thermal":    {"Tg": 378.15}
    }


# ============================================================
# Halpin-Tsai Micromechanics Homogenisation
# ============================================================
def halpin_tsai_homogenize(
    E_m: float,
    E_f: float,
    nu_m: float,
    vf: float,
    ar: float
) -> Dict[str, float]:
    """
    Halpin-Tsai composite model for unidirectional fiber reinforcement.

    Longitudinal (MD) modulus:
        E_L = E_m · (1 + ξ_L · η_L · vf) / (1 - η_L · vf)
        ξ_L = 2 · AR   (longitudinal reinforcement efficiency)
        η_L = (E_f/E_m - 1) / (E_f/E_m + ξ_L)

    Transverse (TD) modulus:
        E_T = E_m · (1 + ξ_T · η_T · vf) / (1 - η_T · vf)
        ξ_T = 2   (transverse: circular cross-section fibres)
        η_T = (E_f/E_m - 1) / (E_f/E_m + ξ_T)

    Shear modulus (in-plane):
        G_m = E_m / (2·(1+ν_m))
        G_12 = G_m · (1 + ξ_G · η_G · vf) / (1 - η_G · vf)
        ξ_G = 1
        η_G = (G_f/G_m - 1) / (G_f/G_m + ξ_G)

    Poisson ratio (rule of mixtures):
        ν_12 = ν_m · (1-vf) + ν_f · vf

    Parameters
    ----------
    E_m  : matrix (resin) Young's modulus [MPa]
    E_f  : filler Young's modulus [MPa]
    nu_m : matrix Poisson's ratio
    vf   : filler volume fraction (0–1)
    ar   : fiber aspect ratio L/D

    Returns
    -------
    dict with E_L, E_T, G_12, G_13, G_23, nu_12, nu_13, nu_23
    """
    # --- Longitudinal (MD) ---
    xi_L  = 2.0 * ar
    eta_L = (E_f / E_m - 1.0) / (E_f / E_m + xi_L)
    E_L   = E_m * (1.0 + xi_L * eta_L * vf) / (1.0 - eta_L * vf)

    # --- Transverse (TD) ---
    xi_T  = 2.0
    eta_T = (E_f / E_m - 1.0) / (E_f / E_m + xi_T)
    E_T   = E_m * (1.0 + xi_T * eta_T * vf) / (1.0 - eta_T * vf)

    # --- Shear modulus ---
    G_m  = E_m / (2.0 * (1.0 + nu_m))
    # Approximate fiber shear modulus (isotropic glass): G_f = E_f/(2*(1+nu_f))
    nu_f = 0.20   # typical for E-glass
    G_f  = E_f / (2.0 * (1.0 + nu_f))
    xi_G  = 1.0
    eta_G = (G_f / G_m - 1.0) / (G_f / G_m + xi_G)
    G_12  = G_m * (1.0 + xi_G * eta_G * vf) / (1.0 - eta_G * vf)
    G_13  = G_12   # transverse isotropy: G_13 ≈ G_12
    G_23  = G_m    # matrix-dominated (fibers don't reinforce this plane much)

    # --- Poisson ratios (rule of mixtures) ---
    nu_12 = nu_m * (1.0 - vf) + nu_f * vf
    nu_13 = nu_12   # transverse isotropy
    nu_23 = nu_m    # matrix-dominated

    return {
        "E_L":   E_L,
        "E_T":   E_T,
        "G_12":  G_12,
        "G_13":  G_13,
        "G_23":  G_23,
        "nu_12": nu_12,
        "nu_13": nu_13,
        "nu_23": nu_23
    }


# ============================================================
# CTE Homogenisation — Schapery Model
# ============================================================
def cte_homogenize(
    alpha_m: float,
    alpha_f: float,
    E_m: float,
    E_f: float,
    nu_m: float,
    vf: float
) -> Tuple[float, float]:
    """
    Compute composite CTE using Schapery's model.

    Longitudinal (MD) CTE — dominated by fiber (lower CTE):
        α_L = (α_m·E_m·(1-vf) + α_f·E_f·vf) / (E_m·(1-vf) + E_f·vf)
              [Voigt rule weighted by stiffness]

    Transverse (TD) CTE — matrix dominated (higher CTE):
        α_T = (1+ν_m)·α_m·(1-vf) + (1+ν_f)·α_f·vf - ν_12·α_L
              [Schapery's transverse formula]

    Physical constraint: α_L < α_T  (fiber restrains MD shrinkage)

    Parameters
    ----------
    alpha_m : matrix CTE [1/K]
    alpha_f : filler CTE [1/K]
    E_m     : matrix modulus [MPa]
    E_f     : filler modulus [MPa]
    nu_m    : matrix Poisson's ratio
    vf      : volume fraction

    Returns
    -------
    (alpha_L, alpha_T) — longitudinal and transverse CTE [1/K]
    """
    vm = 1.0 - vf
    nu_f = 0.20

    # Longitudinal CTE (Schapery longitudinal)
    alpha_L = (alpha_m * E_m * vm + alpha_f * E_f * vf) / (E_m * vm + E_f * vf)

    # Effective Poisson (rule of mixtures for ν_12)
    nu_12 = nu_m * vm + nu_f * vf

    # Transverse CTE (Schapery transverse)
    alpha_T = ((1.0 + nu_m) * alpha_m * vm
               + (1.0 + nu_f) * alpha_f * vf
               - nu_12 * alpha_L)

    # Safety clamp: ensure physically correct ordering
    # If somehow alpha_T < alpha_L due to numerical effects, apply floor
    if alpha_T < alpha_L:
        alpha_T = alpha_L * 1.05   # small transverse excess (5% minimum)

    return float(alpha_L), float(alpha_T)


# ============================================================
# Orientation-Dependent Orthotropic Constants
# ============================================================
def map_orientation_to_orthotropic(
    a_ij: np.ndarray,           # (3, 3) orientation tensor for one cell
    E_L: float,
    E_T: float,
    nu_m: float,
    G_12: float,
    G_13: float,
    G_23: float,
    nu_12: float,
    nu_13: float,
    nu_23: float,
    alpha_L: float,
    alpha_T: float
) -> Dict[str, float]:
    """
    Map the local orientation tensor a_ij to cell-specific orthotropic elastic constants.

    Linear interpolation between perfectly-aligned (a11=1) and isotropic (a11=1/3):
        E_eff_dir = a_dir · E_L + (1 - a_dir) · E_T

    This reflects that cells with high a11 (aligned fibers) are stiff in MD,
    while cells with low a11 (random fibers) approach isotropic response.

    CTE mapping (inverse: fibers reduce CTE):
        α_eff_dir = a_dir · alpha_L + (1 - a_dir) · alpha_T
        Since alpha_L < alpha_T, high a_dir → low CTE (MD direction)

    Parameters
    ----------
    a_ij : (3,3) orientation tensor (diagonal entries a11, a22, a33)
    E_L, E_T     : UD composite longitudinal/transverse moduli [MPa]
    nu_m, G_*    : matrix shear and Poisson params
    alpha_L, alpha_T : UD CTE longitudinal/transverse [1/K]

    Returns
    -------
    dict of 9 orthotropic constants + 3 CTE directions
    """
    a11 = max(0.0, min(1.0, float(a_ij[0, 0])))
    a22 = max(0.0, min(1.0, float(a_ij[1, 1])))
    a33 = max(0.0, min(1.0, float(a_ij[2, 2])))

    # Normalise in case of floating-point drift
    s = a11 + a22 + a33
    if s > 1e-10:
        a11 /= s
        a22 /= s
        a33 /= s

    # Orientation-weighted moduli
    E11 = a11 * E_L + (1.0 - a11) * E_T
    E22 = a22 * E_L + (1.0 - a22) * E_T
    E33 = a33 * E_L + (1.0 - a33) * E_T

    # CTE (fibers reduce CTE in their direction)
    cte1 = a11 * alpha_L + (1.0 - a11) * alpha_T
    cte2 = a22 * alpha_L + (1.0 - a22) * alpha_T
    cte3 = a33 * alpha_L + (1.0 - a33) * alpha_T

    return {
        "E11": E11, "E22": E22, "E33": E33,
        "nu12": nu_12, "nu13": nu_13, "nu23": nu_23,
        "G12": G_12,  "G13": G_13,  "G23": G_23,
        "cte1": cte1, "cte2": cte2, "cte3": cte3
    }


# ============================================================
# Isotropic Fallback (original behaviour preserved)
# ============================================================
def _write_isotropic_material(f, E: float, nu: float, cte: float):
    """Write standard isotropic *ELASTIC and *EXPANSION cards."""
    f.write("*MATERIAL, NAME=POLYMER\n")
    f.write("*ELASTIC\n")
    f.write(f"  {E:.2f}, {nu:.4f}\n")
    f.write("*EXPANSION, TYPE=ISO\n")
    f.write(f"  {cte:.3e}\n")


def _write_orthotropic_material(f, ortho: Dict[str, float], mat_name: str = "POLYMER_ORTHO"):
    """
    Write CalculiX *ELASTIC, TYPE=ORTHOTROPIC and *EXPANSION, TYPE=ORTHO cards.
    With advanced viscoelastic Prony Series and temperature dependencies support.
    """
    # Load advanced nonlinear material toggle
    enable_visco = False
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f_spec:
                specs = json.load(f_spec)
                enable_visco = specs.get("advanced_nonlinear_material", False)
        except Exception:
            pass

    f.write(f"*MATERIAL, NAME={mat_name}\n")
    if enable_visco:
        f.write("*ELASTIC, TYPE=ORTHOTROPIC, DEPENDENCIES=1\n")
        # Write temperature-dependent orthotropic matrices: stiffness drops as temp rises
        for temp, scale in [(298.15, 1.0), (350.0, 0.85), (400.0, 0.50), (450.0, 0.15)]:
            f.write(f"  {ortho['E11']*scale:.4f}, {ortho['E22']*scale:.4f}, {ortho['nu12']:.6f}, "
                    f"{ortho['G12']*scale:.4f}, {ortho['E33']*scale:.4f}, {ortho['nu13']:.6f}, "
                    f"{ortho['nu23']:.6f}, {ortho['G13']*scale:.4f}, {ortho['G23']*scale:.4f}, {temp}\n")
        
        # Write WLF Prony Series Viscoelasticity
        f.write("*VISCOELASTIC, TIME=PRONY\n")
        f.write("  0.3500, 0.0000, 0.1000\n")
        f.write("  0.2500, 0.0000, 1.0000\n")
        f.write("  0.2000, 0.0000, 10.0000\n")
        f.write("*TRS\n")
        f.write("  423.15, 17.44, 51.60\n")
    else:
        f.write("*ELASTIC, TYPE=ORTHOTROPIC\n")
        f.write(f"  {ortho['E11']:.4f}, {ortho['E22']:.4f}, {ortho['nu12']:.6f}, "
                f"{ortho['G12']:.4f}, {ortho['E33']:.4f}, {ortho['nu13']:.6f}, "
                f"{ortho['nu23']:.6f}, {ortho['G13']:.4f}, {ortho['G23']:.4f}\n")
                
    f.write("*EXPANSION, TYPE=ORTHO\n")
    f.write(f"  {ortho['cte1']:.4e}, {ortho['cte2']:.4e}, {ortho['cte3']:.4e}\n")


# ============================================================
# Orthotropic FSI Mapping — Main Entry Point
# ============================================================
def run_orthotropic_fsi_mapping(material_grade: str = "PC+GF20") -> bool:
    """
    Extended FSI mapping that incorporates fiber orientation tensor and
    Halpin-Tsai homogenised orthotropic material constants.

    Steps:
    1. Load material properties (matrix + additive)
    2. Compute Halpin-Tsai UD composite constants
    3. Load fiber orientation tensors (from fiber_orientator.npy cache)
    4. Compute mean orientation tensor for representative .inp generation
    5. Write orthotropic Abaqus .inp deck
    """
    print("=" * 60)
    print(f"  fsi_mapper.py: Orthotropic FSI Mapping [{material_grade}]")
    print("=" * 60)

    # ---- 1. Load material properties ----
    props = load_selected_material_properties(force_grade=material_grade)
    mech  = props.get("Mechanical", {"YoungsModulus": 2400.0, "PoissonsRatio": 0.35, "CTE": 8.0e-5})
    addon = props.get("Additives", None)
    t_ref = props.get("Thermal", {}).get("Tg", 378.15)

    E_m   = mech["YoungsModulus"]
    nu_m  = mech["PoissonsRatio"]
    alpha_m = mech["CTE"]

    if addon is None:
        print(f"[WARN] No Additives found for {material_grade}. Falling back to isotropic mapping.")
        return run_fsi_mapping()   # legacy isotropic path

    E_f      = addon["filler_modulus_MPa"]
    alpha_f  = addon["filler_CTE"]
    vf       = addon["volume_fraction"]
    ar       = addon["aspect_ratio"]

    print(f"[INFO] Matrix: E_m={E_m} MPa, ν={nu_m}, α={alpha_m:.2e} /K")
    print(f"[INFO] Filler: E_f={E_f} MPa, α_f={alpha_f:.2e} /K, vf={vf:.3f}, AR={ar}")

    # ---- 2. Halpin-Tsai homogenisation ----
    ht = halpin_tsai_homogenize(E_m, E_f, nu_m, vf, ar)
    alpha_L, alpha_T = cte_homogenize(alpha_m, alpha_f, E_m, E_f, nu_m, vf)

    print(f"\n[Halpin-Tsai Results]")
    print(f"  E_L (MD) = {ht['E_L']:.2f} MPa")
    print(f"  E_T (TD) = {ht['E_T']:.2f} MPa")
    print(f"  G_12     = {ht['G_12']:.2f} MPa")
    print(f"\n[Schapery CTE Results]")
    print(f"  α_L (MD) = {alpha_L:.3e} /K  (fiber restrains → lower)")
    print(f"  α_T (TD) = {alpha_T:.3e} /K  (matrix dominant → higher)")

    # ---- 3. Load orientation tensors ----
    a_tensors = None
    if ORIENT_NPY.exists():
        try:
            a_tensors = np.load(str(ORIENT_NPY))
            print(f"[INFO] Loaded orientation tensors: {a_tensors.shape[0]} cells")
        except Exception as e:
            print(f"[WARN] Orientation tensor load failed: {e}")

    if a_tensors is None:
        print("[INFO] No orientation cache found. Running fiber_orientator...")
        try:
            import fiber_orientator as fo
            result = fo.compute_fiber_orientation(aspect_ratio=ar)
            a_tensors = result["a_tensors"]
        except Exception as e:
            print(f"[WARN] fiber_orientator failed: {e}. Using isotropic default.")
            # Create a uniform orientation tensor (slightly MD-biased for GF)
            N_dummy = 100
            a_tensors = np.zeros((N_dummy, 3, 3))
            a_tensors[:, 0, 0] = 0.50   # a11 (MD bias for GF)
            a_tensors[:, 1, 1] = 0.30   # a22
            a_tensors[:, 2, 2] = 0.20   # a33

    # ---- 4. Representative mean orientation tensor ----
    a_mean = np.mean(a_tensors, axis=0)
    a11_m, a22_m, a33_m = float(a_mean[0, 0]), float(a_mean[1, 1]), float(a_mean[2, 2])
    print(f"\n[INFO] Mean Orientation Tensor: a11={a11_m:.4f}, a22={a22_m:.4f}, a33={a33_m:.4f}")

    # ---- 5. Compute mean orthotropic constants ----
    ortho_mean = map_orientation_to_orthotropic(
        a_mean,
        ht["E_L"], ht["E_T"], nu_m,
        ht["G_12"], ht["G_13"], ht["G_23"],
        ht["nu_12"], ht["nu_13"], ht["nu_23"],
        alpha_L, alpha_T
    )

    print(f"\n[Orthotropic Constants (Mean Orientation)]")
    print(f"  E11 = {ortho_mean['E11']:.2f} MPa  [MD - highest]")
    print(f"  E22 = {ortho_mean['E22']:.2f} MPa  [TD]")
    print(f"  E33 = {ortho_mean['E33']:.2f} MPa  [ND]")
    print(f"  CTE1 = {ortho_mean['cte1']:.3e} /K  [MD - lowest]")
    print(f"  CTE2 = {ortho_mean['cte2']:.3e} /K  [TD]")
    print(f"  CTE3 = {ortho_mean['cte3']:.3e} /K  [ND]")

    # ---- 6. Load VTK mesh for nodes/elements ----
    vtk_files = sorted(
        VTK_DIR.glob("validation_test_*.vtk"),
        key=lambda f_: int(f_.stem.split("_")[-1]) if f_.stem.split("_")[-1].isdigit() else -1
    )
    if not vtk_files:
        print("[ERROR] No VTK files found. Cannot generate .inp mesh.")
        return False

    latest_vtk = vtk_files[-1]
    print(f"\n[INFO] Source VTK mesh: {latest_vtk.name}")

    try:
        import pyvista as pv
        mesh = pv.read(str(latest_vtk))
        pts     = mesh.points
        n_nodes = len(pts)

        try:
            cells = mesh.cells
        except AttributeError:
            cells = None

        t_arr = mesh.cell_data.get('T', np.ones(mesh.n_cells) * 450.0)

        # ---- 7. Write Orthotropic .inp deck ----
        print(f"[INFO] Writing Orthotropic Abaqus Input Deck: {OUT_INP.name}")
        with open(OUT_INP, "w", encoding="utf-8") as f:
            f.write("** warpage_run.inp — 1-Way FSI Orthotropic Abaqus Deck for Warpage Analysis\n")
            f.write(f"** Material: {material_grade} | Halpin-Tsai + Folgar-Tucker\n")
            f.write("** Generated automatically by fsi_mapper.py (Orthotropic Mode)\n")
            f.write("**\n")

            # Nodes
            f.write("*NODE\n")
            for idx, pt in enumerate(pts):
                f.write(f"  {idx+1}, {pt[0]:.6f}, {pt[1]:.6f}, {pt[2]:.6f}\n")

            # Elements
            f.write("*ELEMENT, TYPE=C3D8, ELSET=PART_BODY\n")
            elem_id = 1
            if cells is not None and len(cells) > 0:
                idx = 0
                while idx < len(cells):
                    cell_sz = int(cells[idx])
                    if cell_sz == 8:
                        el_nodes = cells[idx+1:idx+9] + 1
                        f.write(f"  {elem_id}, {el_nodes[0]}, {el_nodes[1]}, {el_nodes[2]}, {el_nodes[3]}, "
                                f"{el_nodes[4]}, {el_nodes[5]}, {el_nodes[6]}, {el_nodes[7]}\n")
                        elem_id += 1
                    idx += (cell_sz + 1)
            else:
                f.write("  1, 1, 2, 3, 4, 5, 6, 7, 8\n")
                elem_id = 2

            # Orthotropic Material Card
            f.write("**\n")
            f.write(f"** Material: {material_grade} — Halpin-Tsai homogenised orthotropic\n")
            f.write(f"** E11(MD)={ortho_mean['E11']:.1f}, E22={ortho_mean['E22']:.1f}, E33={ortho_mean['E33']:.1f} MPa\n")
            f.write(f"** CTE1={ortho_mean['cte1']:.3e}, CTE2={ortho_mean['cte2']:.3e} /K\n")
            _write_orthotropic_material(f, ortho_mean, mat_name="POLYMER_ORTHO")

            # Section assignment
            f.write("**\n")
            f.write("*SOLID SECTION, MATERIAL=POLYMER_ORTHO, ELSET=PART_BODY\n")
            f.write("\n")

            # Boundary Conditions: 3-2-1
            f.write("**\n")
            f.write("** Boundary Conditions: 3-2-1 Rigid Body Constraint\n")
            f.write("*BOUNDARY\n")
            f.write("  1, 1, 3, 0.0\n")
            f.write("  2, 2, 3, 0.0\n")
            f.write("  3, 3, 3, 0.0\n")

            # Thermal Loading
            # Compute thickness-wise midpoint and balance offsets to conserve mean temperature perfectly
            z_coords = pts[:, 2]
            z_mid = np.median(z_coords)
            raw_offsets = [7.5 if z_val > z_mid else -7.5 for z_val in z_coords]
            mean_offset = np.mean(raw_offsets)
            balanced_offsets = [o - mean_offset for o in raw_offsets]
            
            f.write("**\n")
            f.write("** Nodal Thermal Loading (VTK → INP mapped with asymmetric CHT Delta T)\n")
            f.write("*TEMPERATURE, INITIAL\n")
            for idx in range(n_nodes):
                cell_idx = min(idx, len(t_arr) - 1)
                t_base = float(t_arr[cell_idx])
                t_node = t_base + balanced_offsets[idx]
                f.write(f"  {idx+1}, {t_node:.2f}\n")

            f.write("*TEMPERATURE\n")
            for idx in range(n_nodes):
                cell_idx = min(idx, len(t_arr) - 1)
                t_base = float(t_arr[cell_idx])
                t_node = t_base + balanced_offsets[idx]
                f.write(f"  {idx+1}, {t_node:.2f}\n")

        print(f"[SUCCESS] Orthotropic INP generated. Nodes={n_nodes}, Elements={elem_id-1}")

        # ---- 8. Update machine_spec.json ----
        shrinkage_pct = mesh.cell_data.get('Shrinkage_Vol', np.ones(mesh.n_cells) * 2.0)
        max_u_mm = float(np.max(shrinkage_pct) * 0.25)

        specs: Dict[str, Any] = {}
        if SPEC_JSON.exists():
            try:
                with open(SPEC_JSON, "r", encoding="utf-8") as f:
                    specs = json.load(f)
            except Exception:
                pass

        specs["max_warpage_displacement_mm"] = max_u_mm
        specs["active_manufacturer"]  = "Generic"
        specs["active_grade"]         = material_grade
        specs["orthotropic_E11_MPa"]  = ortho_mean["E11"]
        specs["orthotropic_E22_MPa"]  = ortho_mean["E22"]
        specs["orthotropic_E33_MPa"]  = ortho_mean["E33"]
        specs["orthotropic_CTE1"]     = ortho_mean["cte1"]
        specs["orthotropic_CTE2"]     = ortho_mean["cte2"]
        specs["halpin_tsai_E_L"]      = ht["E_L"]
        specs["halpin_tsai_E_T"]      = ht["E_T"]
        specs["schapery_alpha_L"]     = alpha_L
        specs["schapery_alpha_T"]     = alpha_T
        specs["a11_mean"]             = a11_m
        specs["a22_mean"]             = a22_m
        specs["a33_mean"]             = a33_m

        with open(SPEC_JSON, "w", encoding="utf-8") as f:
            json.dump(specs, f, indent=4)

        return True

    except Exception as e:
        print(f"[ERROR] Orthotropic FSI mapping failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# Legacy Isotropic FSI Mapping (preserved for compatibility)
# ============================================================
def run_fsi_mapping() -> bool:
    """Original isotropic 1-Way FSI mapping (preserved for non-composite grades)."""
    print("=" * 60)
    print("  fsi_mapper.py: 1-Way CFD-to-FEM Load Transporter (Isotropic)")
    print("=" * 60)

    vtk_files = list(VTK_DIR.glob("validation_test_*.vtk"))
    if not vtk_files:
        print("[ERROR] No VTK files found under validation_test/VTK.")
        return False

    vtk_files.sort(key=lambda f: int(f.stem.split("_")[-1]) if f.stem.split("_")[-1].isdigit() else -1)
    latest_vtk = vtk_files[-1]
    print(f"[INFO] Source VTK mesh: {latest_vtk.name}")

    props = load_selected_material_properties()
    mech  = props.get("Mechanical", {"YoungsModulus": 2400.0, "PoissonsRatio": 0.35, "CTE": 8.0e-5})
    E     = mech["YoungsModulus"]
    nu    = mech["PoissonsRatio"]
    cte   = mech["CTE"]
    t_ref = props.get("Thermal", {}).get("Tg", 378.15)

    try:
        import pyvista as pv
        mesh   = pv.read(str(latest_vtk))
        pts    = mesh.points
        n_nodes = len(pts)

        try:
            cells = mesh.cells
        except AttributeError:
            cells = None

        t_arr = mesh.cell_data.get('T', np.ones(mesh.n_cells) * 450.0)

        print(f"[INFO] Writing Abaqus Input Deck: {OUT_INP.name}")
        with open(OUT_INP, "w", encoding="utf-8") as f:
            f.write("** warpage_run.inp - 1-Way FSI Abaqus Deck for Warpage Analysis\n")
            f.write("** Generated automatically by fsi_mapper.py\n")
            f.write("**\n")

            f.write("*NODE\n")
            for idx, pt in enumerate(pts):
                f.write(f"  {idx+1}, {pt[0]:.6f}, {pt[1]:.6f}, {pt[2]:.6f}\n")

            f.write("*ELEMENT, TYPE=C3D8, ELSET=PART_BODY\n")
            elem_id = 1
            if cells is not None and len(cells) > 0:
                idx = 0
                while idx < len(cells):
                    cell_sz = int(cells[idx])
                    if cell_sz == 8:
                        el_nodes = cells[idx+1:idx+9] + 1
                        f.write(f"  {elem_id}, {el_nodes[0]}, {el_nodes[1]}, {el_nodes[2]}, {el_nodes[3]}, "
                                f"{el_nodes[4]}, {el_nodes[5]}, {el_nodes[6]}, {el_nodes[7]}\n")
                        elem_id += 1
                    idx += (cell_sz + 1)
            else:
                f.write("  1, 1, 2, 3, 4, 5, 6, 7, 8\n")
                elem_id = 2

            f.write("**\n")
            f.write("*MATERIAL, NAME=POLYMER\n")
            f.write("*ELASTIC\n")
            f.write(f"  {E:.2f}, {nu:.4f}\n")
            f.write("*EXPANSION, TYPE=ISO\n")
            f.write(f"  {cte:.3e}\n")

            f.write("**\n")
            f.write("** Boundary Conditions: 3-2-1 Rigid Body Constraint\n")
            f.write("*BOUNDARY\n")
            f.write("  1, 1, 3, 0.0\n")
            f.write("  2, 2, 3, 0.0\n")
            f.write("  3, 3, 3, 0.0\n")

            # Thermal Loading
            # Compute thickness-wise midpoint and balance offsets to conserve mean temperature perfectly
            z_coords = pts[:, 2]
            z_mid = np.median(z_coords)
            raw_offsets = [7.5 if z_val > z_mid else -7.5 for z_val in z_coords]
            mean_offset = np.mean(raw_offsets)
            balanced_offsets = [o - mean_offset for o in raw_offsets]

            f.write("**\n")
            f.write("** Nodal Mapped Thermal & Volumetric Shrinkage Loading (with asymmetric CHT Delta T)\n")
            f.write("*TEMPERATURE, INITIAL\n")
            for idx in range(n_nodes):
                cell_idx = min(idx, len(t_arr) - 1)
                t_base = float(t_arr[cell_idx])
                t_node = t_base + balanced_offsets[idx]
                f.write(f"  {idx+1}, {t_node:.2f}\n")

            f.write("*TEMPERATURE\n")
            for idx in range(n_nodes):
                cell_idx = min(idx, len(t_arr) - 1)
                t_base = float(t_arr[cell_idx])
                t_node = t_base + balanced_offsets[idx]
                f.write(f"  {idx+1}, {t_node:.2f}\n")

        print(f"[SUCCESS] Isotropic FSI mapping done. Nodes={n_nodes}, Elements={elem_id-1}")

        shrinkage_pct = mesh.cell_data.get('Shrinkage_Vol', np.ones(mesh.n_cells) * 2.0)
        max_u_mm = float(np.max(shrinkage_pct) * 0.25)

        specs: Dict[str, Any] = {}
        if SPEC_JSON.exists():
            try:
                with open(SPEC_JSON, "r", encoding="utf-8") as f:
                    specs = json.load(f)
            except Exception:
                pass

        specs["max_warpage_displacement_mm"] = max_u_mm
        with open(SPEC_JSON, "w", encoding="utf-8") as f:
            json.dump(specs, f, indent=4)

        return True
    except Exception as e:
        print(f"[ERROR] FSI mapping failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    grade = sys.argv[1] if len(sys.argv) > 1 else "PC+GF20"
    success = run_orthotropic_fsi_mapping(material_grade=grade)
    sys.exit(0 if success else 1)
