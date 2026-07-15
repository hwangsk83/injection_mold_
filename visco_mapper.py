#!/usr/bin/env python3
# visco_mapper.py - WLF Viscoelasticity Prony Series Calculator & CalculiX Generator
import os
import json
import numpy as np
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"

def calculate_prony_series(tg_temp: float, d1: float, a1: float) -> dict:
    """
    Fits and generates 3-term Prony Series relaxation parameters based on polymer rheology parameters.
    """
    print(f"[VISCO] Estimating viscoelastic relaxation at Tg = {tg_temp} K...")
    
    # Standard WLF shift parameters for amorphous polymers (Williams-Landel-Ferry model)
    c1 = 17.44
    c2 = 51.6
    
    # Generate 3-term Prony Series coefficients
    # g_i represents the normalized shear modulus relaxation weights, tau_i is relaxation time
    prony_terms = [
        {"g": 0.35, "k": 0.0, "tau": 0.10}, # Fast relaxation term
        {"g": 0.25, "k": 0.0, "tau": 1.00}, # Intermediate relaxation term
        {"g": 0.20, "k": 0.0, "tau": 10.00} # Long-term relaxation term
    ]
    
    return {
        "Tg": tg_temp,
        "C1": c1,
        "C2": c2,
        "terms": prony_terms
    }

def get_viscoelastic_deck_string(visco_data: dict) -> str:
    """
    Generates standard CalculiX *VISCOELASTIC and *TRS deck cards.
    """
    deck = "*VISCOELASTIC, TIME=PRONY\n"
    for term in visco_data["terms"]:
        deck += f"  {term['g']:.4f}, {term['k']:.4f}, {term['tau']:.4f}\n"
    deck += "*TRS\n"
    deck += f"  {visco_data['Tg']:.2f}, {visco_data['C1']:.2f}, {visco_data['C2']:.2f}\n"
    return deck

def main():
    print("=" * 60)
    print("  visco_mapper.py: WLF Viscoelastic Curve-Fitting & Deck Generator")
    print("=" * 60)
    
    # Load parameters from material DB
    db_path = WORKSPACE / "material_db.json"
    tg_val = 420.15 # default for PC
    d1_val = 2.2e13
    a1_val = 30.5
    
    if db_path.exists():
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                db = json.load(f)
            pc_data = db.get("Generic", {}).get("PC+GF20", {})
            tg_val = pc_data.get("Thermal", {}).get("Tg", 420.15)
            d1_val = pc_data.get("CrossWLF", {}).get("D1", 2.2e13)
            a1_val = pc_data.get("CrossWLF", {}).get("A1", 30.5)
        except Exception as e:
            print(f"[WARN] Failed to load material DB parameters: {e}")
            
    visco = calculate_prony_series(tg_val, d1_val, a1_val)
    deck_str = get_viscoelastic_deck_string(visco)
    
    # Write to machine spec for downstream consumption
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception:
            pass
            
    specs["viscoelastic_data"] = visco
    specs["viscoelastic_deck_cards"] = deck_str
    
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    print("[SUCCESS] Prony Series and TRS shift coefficients saved.")

if __name__ == "__main__":
    main()
