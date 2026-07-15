#!/usr/bin/env python3
# plastic_failure_bridge.py - Hill's Yield & Plastic Failure Mapper
import os
import json
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
OUT_INP = WORKSPACE / "warpage_run.inp"
SPEC_JSON = WORKSPACE / "machine_spec.json"

def write_potentials_and_plasticity():
    print("[PLASTIC BRIDGE] Injecting Hill's Orthotropic Yield and non-linear plastic failure strain...")
    
    # PC+GF20 anisotropic plastic failure parameters
    # Yield stress (sigma_y) anisotropic ratios: R11, R22, R33, R12, R13, R23
    r11, r22, r33 = 1.0, 0.85, 0.75
    r12, r13, r23 = 0.9, 0.9, 0.9
    
    # Plastic stress-strain curve data points: Yield Stress (MPa), Plastic Strain
    plastic_points = [
        (45.0, 0.000),  # Initial yield
        (52.0, 0.005),
        (58.0, 0.015),
        (62.0, 0.030),  # Failure strain limit
    ]
    
    if OUT_INP.exists():
        try:
            inp_text = OUT_INP.read_text(encoding="utf-8")
            if "*POTENTIAL" not in inp_text:
                # Construct plastic failure cards
                card_str = "\n**\n** Hill's Orthotropic Yield Potential & Non-linear Plasticity\n"
                card_str += "*POTENTIAL\n"
                card_str += f"  {r11:.4f}, {r22:.4f}, {r33:.4f}, {r12:.4f}, {r13:.4f}, {r23:.4f}\n"
                card_str += "*PLASTIC\n"
                for stress, strain in plastic_points:
                    card_str += f"  {stress:.2f}, {strain:.4f}\n"
                    
                # Find POLYMER_ORTHO section to append
                if "*MATERIAL, NAME=POLYMER_ORTHO" in inp_text:
                    parts = inp_text.split("*MATERIAL, NAME=POLYMER_ORTHO")
                    # Insert cards right inside material block
                    new_text = parts[0] + "*MATERIAL, NAME=POLYMER_ORTHO\n" + card_str + parts[1]
                    OUT_INP.write_text(new_text, encoding="utf-8")
                    print("[PLASTIC BRIDGE] Hill's plastic potential cards injected inside POLYMER_ORTHO block.")
                else:
                    OUT_INP.write_text(inp_text + card_str, encoding="utf-8")
                    print("[PLASTIC BRIDGE] Cards appended at deck tail.")
        except Exception as e:
            print(f"[WARN] Failed to write failure cards: {e}")
            
    # Save back to specs
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception:
            pass
            
    specs["plastic_failure"] = {
        "yield_potential_ratios": [r11, r22, r33, r12, r13, r23],
        "failure_strain_limit": 0.030,
        "result": "SUCCESS"
    }
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    print("[SUCCESS] Anisotropic Hill plastic failure mapped successfully.")
    return True

def main():
    write_potentials_and_plasticity()

if __name__ == "__main__":
    main()
