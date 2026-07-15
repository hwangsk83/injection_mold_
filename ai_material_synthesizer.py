#!/usr/bin/env python3
# ai_material_synthesizer.py - AI Property Synthesis Surrogate Model for Polymers
import os
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"

# Physical bounding box / clipping guardrails for numerical stability
PHYSICAL_LIMITS = {
    "CrossWLF": {
        "n": (0.15, 0.45),
        "tau_star": (1.0e4, 1.0e6),
        "D1": (1.0e8, 1.0e16),
        "D2": (200.0, 500.0),
        "D3": (0.0, 1.0e-5),
        "A1": (10.0, 50.0),
        "A2": (10.0, 100.0)
    },
    "Tait": {
        "b1m": (5.0e-4, 1.5e-3),
        "b2m": (1.0e-7, 5.0e-6),
        "b3m": (5.0e7, 5.0e8),
        "b4m": (1.0e-3, 1.0e-2),
        "b5": (200.0, 500.0),
        "C_tait": (0.05, 0.15)
    }
}

def clip_to_guardrails(category: str, params: Dict[str, float]) -> Dict[str, float]:
    """Clips the generated parameters to prevent solver divergence."""
    clipped = {}
    limits = PHYSICAL_LIMITS.get(category, {})
    for key, val in params.items():
        if key in limits:
            low, high = limits[key]
            clipped[key] = float(np.clip(val, low, high))
        else:
            clipped[key] = val
    return clipped

def synthesize_properties(
    resin_type: str, 
    melt_index: float, 
    density: float, 
    Tg: float, 
    yield_strength: float
) -> Dict[str, Any]:
    """
    Generates Cross-WLF and Modified Tait PvT parameters from basic TDS specs.
    Uses physical scaling law surrogate equations.
    """
    print(f"[AI SYNTHESIZER] Gauging surrogate properties for {resin_type}...")
    print(f"  Inputs: MI={melt_index}, Density={density}, Tg={Tg}K, YieldStrength={yield_strength}MPa")
    
    resin = resin_type.upper().strip()
    
    # 1. Base Resin Calibration Weights
    if "PC" in resin:
        base_n = 0.30
        base_tau = 1.8e5
        base_D1 = 2.4e13
        base_A1 = 31.2
        base_A2 = 51.6
        stress_optical_brewster = 3500.0
        YoungsModulus = 2200.0
        PoissonsRatio = 0.37
        CTE = 6.5e-5
    elif "ABS" in resin:
        base_n = 0.35
        base_tau = 2.8e5
        base_D1 = 3.8e11
        base_A1 = 28.5
        base_A2 = 51.6
        stress_optical_brewster = 2000.0
        YoungsModulus = 2400.0
        PoissonsRatio = 0.35
        CTE = 8.0e-5
    else:  # PP or default
        base_n = 0.38
        base_tau = 1.2e5
        base_D1 = 1.5e9
        base_A1 = 25.0
        base_A2 = 51.6
        stress_optical_brewster = 80.0
        YoungsModulus = 1300.0
        PoissonsRatio = 0.40
        CTE = 1.2e-4

    # 2. Cross-WLF Surrogate Interpolator
    # - Viscosity decreases as Melt Index increases (polymer chain length decreases)
    #   D1 represents zero-shear viscosity at glass transition reference.
    #   We scale D1 exponentially with MI: log10(D1) = log10(base_D1) - 0.2 * (MI - 10)
    log_D1 = np.log10(base_D1) - 0.15 * (melt_index - 10.0)
    syn_D1 = 10.0 ** log_D1
    
    # - Shear thinning index 'n' increases with higher MI (closer to Newtonian)
    syn_n = base_n + 0.005 * (melt_index - 10.0)
    
    # - Tg directly determines reference WLF temp D2
    syn_D2 = Tg
    
    cross_wlf = {
        "n": syn_n,
        "tau_star": base_tau - 1000.0 * (melt_index - 10.0),
        "D1": syn_D1,
        "D2": syn_D2,
        "D3": 0.0,
        "A1": base_A1 - 0.1 * (melt_index - 10.0),
        "A2": base_A2
    }
    cross_wlf = clip_to_guardrails("CrossWLF", cross_wlf)

    # 3. Modified Tait PvT Equation Parameters
    # - Melt specific volume b1m is inversely proportional to density (1/density)
    #   density in g/cm^3 -> specific volume in cm^3/g or m^3/kg
    #   We scale: b1m = 0.001 / density
    syn_b1m = 0.00105 / density
    syn_b2m = 1.2e-6 / density
    
    tait = {
        "b1m": syn_b1m,
        "b2m": syn_b2m,
        "b3m": 1.3e8 * (yield_strength / 60.0),
        "b4m": 0.0035 / density,
        "b5": Tg,
        "b6": 0.0,
        "b7": 0.0,
        "b8": 0.0,
        "b9": 0.0,
        "C_tait": 0.0894
    }
    tait = clip_to_guardrails("Tait", tait)

    # 4. Mechanical & Viscoelastic Elements
    thermal = {
        "Cp_poly": 2000.0,
        "k_poly": 0.20,
        "Tg": Tg,
        "Tm": Tg + 150.0
    }
    
    mechanical = {
        "YoungsModulus": float(np.clip(YoungsModulus * (yield_strength / 60.0), 1000.0, 10000.0)),
        "PoissonsRatio": PoissonsRatio,
        "CTE": CTE
    }

    viscoelastic = {
        "Tg": Tg,
        "C1": float(cross_wlf["A1"]),
        "C2": float(cross_wlf["A2"]),
        "terms": [
            {"g": 0.35, "k": 0.0, "tau": 0.1},
            {"g": 0.25, "k": 0.0, "tau": 1.0},
            {"g": 0.20, "k": 0.0, "tau": 10.0}
        ],
        "stress_optical_coefficient_Brewster": stress_optical_brewster
    }

    synthesized_data = {
        "Manufacturer": "Synthetic_AI",
        "Grade": f"{resin}_MI{melt_index}_D{density}",
        "resin_family": resin,
        "melt_index": melt_index,
        "density": density,
        "CrossWLF": cross_wlf,
        "Tait": tait,
        "Thermal": thermal,
        "Mechanical": mechanical,
        "Viscoelastic": viscoelastic,
        "is_synthetic": True
    }
    
    return synthesized_data

def run_synthetic_compilation():
    print("[AI SYNTHESIZER] Executing default surrogate compile step for PC...")
    # Default PC case: MI=10, Density=1.2, Tg=423, Yield=60
    synth_data = synthesize_properties("PC", 10.0, 1.2, 423.15, 60.0)
    
    # Save default synthetic data to spec for checks
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception:
            pass
            
    specs["synthetic_ai_material"] = synth_data
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    print("[SUCCESS] AI Material synthesis compile step completed successfully.")
    return synth_data

if __name__ == "__main__":
    run_synthetic_compilation()
