#!/usr/bin/env python3
# underfill_capillary_solver.py - 언더필(Underfill) 모세관 표면장력 유동 솔버
import os
import json
import numpy as np
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"

def solve_underfill_capillary():
    print("[UNDERFILL SOLVER] Starting capillary creeping flow microfluidic simulation...")
    
    # Washburn Capillary Filling kinetics model:
    # L^2 = (gamma * h * cos(theta) * t) / (3 * eta)
    # gamma (surface tension of underfill) = 0.035 N/m
    # h (micro gap thickness) = 50 microns = 50e-6 m
    # theta (dynamic contact angle) = 35 degrees
    # eta (creeping flow viscosity) = 0.15 Pa-s
    # t (flow time) = 2.0 s
    gamma = 0.035 # N/m
    gap_h = 50e-6 # m
    theta_rad = np.radians(35.0)
    viscosity_eta = 0.15 # Pa-s
    t_seconds = 2.0
    
    flow_distance_squared = (gamma * gap_h * np.cos(theta_rad) * t_seconds) / (3.0 * viscosity_eta)
    flow_distance_mm = np.sqrt(flow_distance_squared) * 1000.0 # convert to mm
    
    print(f"  Dynamic Contact Angle: 35.0 deg, Capillary Flow Distance in 2.0s: {flow_distance_mm:.4f} mm")
    
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception: pass
        
    specs["underfill_capillary"] = {
        "surface_tension_n_m": gamma,
        "gap_thickness_m": gap_h,
        "dynamic_contact_angle_deg": 35.0,
        "flow_distance_2s_mm": round(float(flow_distance_mm), 6),
        "status": "SUCCESS"
    }
    
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    print("[SUCCESS] Underfill capillary solver run finished.")
    return True

if __name__ == "__main__":
    solve_underfill_capillary()
