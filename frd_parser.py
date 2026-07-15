#!/usr/bin/env python3
# frd_parser.py - CalculiX Nodal frd Post-Processor Parser
import os
import re
import json
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
FRD_PATH = WORKSPACE / "warpage_run.frd"
SPEC_JSON = WORKSPACE / "machine_spec.json"

def parse_frd_results():
    print("="*60)
    print("  frd_parser.py: CalculiX frd Output Post-Processor")
    print("="*60)
    
    if not FRD_PATH.exists():
        print(f"[ERROR] FRD result file {FRD_PATH.name} is missing.")
        return False
        
    try:
        content = FRD_PATH.read_text(encoding="utf-8")
        
        # We need to find block containing displacements under "DISP" field
        lines = content.splitlines()
        disp_card_idx = -1
        stress_card_idx = -1
        
        for i, line in enumerate(lines):
            if "DISP" in line:
                disp_card_idx = i
            elif "STRESS" in line:
                stress_card_idx = i
                
        if disp_card_idx == -1:
            print("[ERROR] Nodal DISP card is missing from frd result file.")
            return False
            
        # Parse nodal displacements (Uz)
        uz_values = []
        for line in lines[disp_card_idx+2:]:
            if line.strip().startswith("-3"):
                break
            parts = line.split()
            if len(parts) >= 4:
                try:
                    uz = float(parts[3]) # Uz is in 4th col
                    uz_values.append(uz)
                except ValueError:
                    pass
                    
        # Parse nodal stresses (Von Mises)
        stress_values = []
        if stress_card_idx != -1:
            for line in lines[stress_card_idx+2:]:
                if line.strip().startswith("-3"):
                    break
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        stress = float(parts[1]) # Von Mises stress is in 2nd col
                        stress_values.append(stress)
                    except ValueError:
                        pass
                        
        # CalculiX displacements are typically in standard dimensions (m), convert back to mm for Z-warpage
        # Simulated Uz is max ~ 0.52mm (0.52e-3 m). Convert back to mm:
        max_uz_m = max([abs(val) for val in uz_values]) if uz_values else 0.0
        # If the values are extremely small (e.g. e-3 scale), convert to mm:
        max_uz_mm = max_uz_m * 1000.0 if max_uz_m < 0.1 else max_uz_m
        
        max_stress = max(stress_values) if stress_values else 0.0
        
        print(f"[SUCCESS] Calculated Peak Z-Warpage: {max_uz_mm:.3f} mm")
        print(f"[SUCCESS] Calculated Max Von Mises Stress: {max_stress:.2f} MPa")
        
        # Save metrics to machine_spec.json for Streamlit dashboard
        specs = {}
        if SPEC_JSON.exists():
            try:
                with open(SPEC_JSON, "r", encoding="utf-8") as f:
                    specs = json.load(f)
            except Exception:
                pass
                
        specs["max_warpage_displacement_mm"] = max_uz_mm
        specs["max_residual_stress_mpa"] = max_stress
        with open(SPEC_JSON, "w", encoding="utf-8") as f:
            json.dump(specs, f, indent=4)
            
        return True
    except Exception as e:
        print(f"[ERROR] FRD post-processing failed: {e}")
        return False

if __name__ == "__main__":
    parse_frd_results()
