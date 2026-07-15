#!/usr/bin/env python3
# multiscale_homogenizer.py - 나노 복합재 멀티스케일 균질화
import os
import json
import numpy as np
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"

def homogenize_nanocomposite():
    print("[MULTISCALE HOMOGENIZER] Executing RVE Halpin-Tsai homogenization for Carbon Nanotubes (CNT)...")
    
    # 1. Input variables (1wt% CNT filler volume fraction = 0.62%)
    filler_volume_fraction = 0.0062
    filler_aspect_ratio = 150.0
    
    # Material properties of PC matrix and Carbon Nanotube (CNT) filler
    E_matrix = 2200.0 # MPa
    E_filler = 1000000.0 # MPa (1 TPa CNT stiffness)
    
    # Halpin-Tsai RVE non-linear homogenization equations:
    # eta = (E_f / E_m - 1) / (E_f / E_m + xi)
    # xi = 2 * aspect_ratio
    # E_composite = E_m * (1 + xi * eta * vf) / (1 - eta * vf)
    xi = 2.0 * filler_aspect_ratio
    eta = ((E_filler / E_matrix) - 1.0) / ((E_filler / E_matrix) + xi)
    
    E_composite_L = E_matrix * (1.0 + xi * eta * filler_volume_fraction) / (1.0 - eta * filler_volume_fraction)
    
    print(f"  Homogenized RVE RVE Matrix E: {E_matrix} MPa -> Composite E_L: {E_composite_L:.2f} MPa")
    
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception: pass
        
    specs["nanocomposite_homogenization"] = {
        "filler_type": "Carbon Nanotube (CNT)",
        "filler_volume_fraction": filler_volume_fraction,
        "filler_aspect_ratio": filler_aspect_ratio,
        "homogenized_longitudinal_modulus_mpa": round(float(E_composite_L), 2),
        "stiffness_enhancement_ratio": round(float(E_composite_L / E_matrix), 4),
        "status": "SUCCESS"
    }
    
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    print("[SUCCESS] Multiscale Halpin-Tsai homogenization completed.")
    return True

if __name__ == "__main__":
    homogenize_nanocomposite()
