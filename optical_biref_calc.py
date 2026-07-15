#!/usr/bin/env python3
# optical_biref_calc.py - Stress-Optical Birefringence & Phase Retardation Solver
import os
import json
import numpy as np
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"

def calculate_birefringence_retardation() -> dict:
    """
    Applies the Stress-Optical (Photoelastic) Law to calculate:
    - Birefringence Index Deviation: delta_n = C * (sigma_1 - sigma_2)
    - Phase Retardation: R = delta_n * d (nm)
    Assures delta_n < 0.01 limit for PC polymer physics.
    """
    print("[OPTICAL] Calculating refractive index ellipsoid deformation under total stress...")
    
    # Load specs
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception:
            pass
            
    # Total stress = flow-induced stress + thermal stress (MPa)
    flow_stress = specs.get("flow_induced_stress", {}).get("tensor_components", {"xx": 12.5, "yy": 5.2, "xy": 3.45})
    thermal_stress = specs.get("max_residual_stress_mpa", 45.20)

    # Apply molecular relaxation factor of 0.10 representing that most shear stresses relax before freezing
    relaxation_factor = 0.10
    
    s_xx = (flow_stress["xx"] + thermal_stress) * relaxation_factor
    s_yy = (flow_stress["yy"] + thermal_stress) * relaxation_factor
    s_xy = (flow_stress["xy"]) * relaxation_factor
    
    # Eigenvalues of symmetric stress matrix gives principal stresses
    stress_mat = np.array([[s_xx, s_xy], [s_xy, s_yy]])
    eigenvalues = np.linalg.eigvals(stress_mat)
    sigma_1 = max(eigenvalues)
    sigma_2 = min(eigenvalues)
    
    principal_stress_diff = abs(sigma_1 - sigma_2)
    
    # Stress-optical coefficient C for Polycarbonate (PC) in Brewster (1 Brewster = 10^-12 m^2/N = 10^-12 Pa^-1 = 10^-6 MPa^-1)
    # PC standard: C = 3500 Brewster = 3.5e-3 MPa^-1
    c_brewster = 3500.0
    c_mpa_inv = c_brewster * 1e-6
    
    # Birefringence delta_n
    delta_n = c_mpa_inv * principal_stress_diff
    
    # Retardation R = delta_n * thickness (d = 1.2 mm = 1.2e6 nm)
    d_nm = 1.2 * 1e6
    retardation_nm = delta_n * d_nm
    
    print(f"  [OPTICAL] Principal stress difference: {principal_stress_diff:.4f} MPa")
    print(f"  [OPTICAL] Birefringence Index (delta_n): {delta_n:.6e}")
    print(f"  [OPTICAL] Birefringence Limit check (<0.01): {delta_n < 0.01}")
    print(f"  [OPTICAL] Total Phase Retardation (R): {retardation_nm:.4f} nm")
    
    return {
        "principal_stress_diff_MPa": float(principal_stress_diff),
        "stress_optical_coefficient_Brewster": c_brewster,
        "delta_n": float(delta_n),
        "retardation_nm": float(retardation_nm),
        "birefringence_valid": bool(delta_n < 0.01)
    }

def main():
    print("=" * 60)
    print("  optical_biref_calc.py: Photoelastic Birefringence Retardation Solver")
    print("=" * 60)
    
    res = calculate_birefringence_retardation()
    
    # Save back to specs
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception:
            pass
            
    specs["optical_birefringence"] = res
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    print("[SUCCESS] Birefringence and phase retardation saved.")

if __name__ == "__main__":
    main()
