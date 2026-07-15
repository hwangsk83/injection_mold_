import json
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
DB_JSON = WORKSPACE / "material_db.json"

with open(DB_JSON, "r", encoding="utf-8") as f:
    db = json.load(f)

# Inject dummy PC with mechanical properties
dummy_pc = {
    "CrossWLF": {
        "n": 0.28,
        "tau_star": 2.0e5,
        "D1": 1.5e13,
        "D2": 415.15,
        "D3": 0.0,
        "A1": 30.5,
        "A2": 51.6
    },
    "Tait": {
        "b1m": 0.00092,
        "b2m": 1.15e-6,
        "b3m": 1.35e8,
        "b4m": 0.0036,
        "b5": 415.15,
        "b6": 0.0,
        "b7": 0.0,
        "b8": 0.0,
        "b9": 0.0,
        "C_tait": 0.0894
    },
    "Thermal": {
        "Cp_poly": 2050.0,
        "k_poly": 0.19,
        "Tg": 420.15,
        "Tm": 568.15
    },
    "Mechanical": {
        "YoungsModulus": 2200.0,
        "PoissonsRatio": 0.37,
        "CTE": 6.5e-5
    }
}

db.setdefault("Lotte Chemical", {})["INFINO PC-1100"] = dummy_pc

with open(DB_JSON, "w", encoding="utf-8") as f:
    json.dump(db, f, indent=4)

print("[SUCCESS] Dummy PC resin successfully injected into material_db.json.")
