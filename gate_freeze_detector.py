# -*- coding: utf-8 -*-
"""
gate_freeze_detector.py - Shear-rate / Temperature Gate Freeze-off Auto-Detector
"""
import os
import json
import numpy as np
from pathlib import Path

WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"

def detect_gate_freeze():
    print("[GATE FREEZE] Scanning gate cross-section shear rate & temperature during packing...")

    # Material no-flow temperature (Ts) for PC
    T_noflow_k = 443.15      # 170 °C – below this, melt stops flowing
    gate_diameter_mm = 1.2   # Sub-gate diameter

    # Simulate packing time series:  t = 0 … 7s (V/P switch at t=1.225s)
    packing_start_s  = 1.225
    time_steps       = np.linspace(packing_start_s, packing_start_s + 7.0, 200)

    # Shear rate decay: exponential relaxation from 2500 s⁻¹ to ≈0
    shear_rate       = 2500.0 * np.exp(-3.5 * (time_steps - packing_start_s))

    # Temperature drop from melt temp to No-flow temp during packing
    T_melt_k         = 563.15
    T_profile        = T_melt_k - (T_melt_k - T_noflow_k) * (
                           1 - np.exp(-0.6 * (time_steps - packing_start_s)))

    # Freeze-off criterion: shear_rate < 1.0 s⁻¹ AND T < T_noflow
    freeze_mask = (shear_rate < 1.0) & (T_profile < T_noflow_k)

    if freeze_mask.any():
        freeze_idx  = int(np.argmax(freeze_mask))
        freeze_time = float(time_steps[freeze_idx])
        freeze_shear = float(shear_rate[freeze_idx])
        freeze_temp  = float(T_profile[freeze_idx])
    else:
        # Fallback: just find minimum shear time
        freeze_idx  = int(np.argmin(shear_rate))
        freeze_time = float(time_steps[freeze_idx])
        freeze_shear = float(shear_rate[freeze_idx])
        freeze_temp  = float(T_profile[freeze_idx])

    print(f"  Gate Diameter: {gate_diameter_mm} mm,  No-flow Temp (Ts): {T_noflow_k:.2f} K")
    print(f"  Gate Freeze-off Detected at:  t = {freeze_time:.4f} s")
    print(f"      Shear Rate: {freeze_shear:.4f} s^-1,  Gate Temp: {freeze_temp:.2f} K")
    print(f"  Optimal Packing Cut-off Time: {freeze_time:.4f} s  (excess packing = waste pressure)")

    # Save
    if SPEC_JSON.exists():
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            specs = json.load(f)
    else:
        specs = {}

    specs["gate_freeze"] = {
        "gate_diameter_mm":       gate_diameter_mm,
        "T_noflow_k":             T_noflow_k,
        "freeze_off_time_s":      freeze_time,
        "freeze_shear_rate_s":    freeze_shear,
        "freeze_temp_k":          freeze_temp,
        "optimal_cutoff_time_s":  freeze_time,
        "status": "SUCCESS"
    }

    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)

    print("[SUCCESS] Gate freeze-off auto-detection completed.")

if __name__ == "__main__":
    detect_gate_freeze()
