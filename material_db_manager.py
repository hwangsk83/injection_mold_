#!/usr/bin/env python3
"""
material_db_manager.py — Central Material Library Management System

Maintains a unified Material_Library.json with physical property validation,
cross-material comparison, and backward-compatible delegation to
material_manager.py for all persistent I/O.
"""
import os, sys, json
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import material_manager as mm

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
LIBRARY_JSON = WORKSPACE / "Material_Library.json"
DB_JSON = WORKSPACE / "material_db.json"

# Physical validation bounds
VALIDATION_BOUNDS = {
    "n": (0.1, 0.9),
    "D1": (1e6, 1e18),
    "b1m": (1e-6, 1e-2),
    "Tg_K": (100.0, 600.0),
    "Tm_K": (300.0, 700.0),
    "Cp_J_kgK": (500.0, 5000.0),
    "k_W_mK": (0.05, 1.0),
    "E_MPa": (100.0, 100000.0),
    "CTE_1_K": (1e-6, 1e-3),
}

# Property keys used for radar chart comparison
COMPARISON_PROPS = [
    ("Tg", "Tg", "K"),
    ("Density", "density", "g/cm³"),
    ("Cp", "Cp_poly", "J/kg·K"),
    ("Thermal Conductivity", "k_poly", "W/m·K"),
    ("Young's Modulus", "YoungsModulus", "MPa"),
    ("CTE", "CTE", "/K"),
    ("n (Power-law index)", "n", "-"),
    ("D1 (Viscosity scale)", "D1", "Pa·s"),
]


def _load_flat_db() -> Dict[str, Any]:
    """Load flat merged DB via material_manager."""
    return mm.load_material_db()


def _save_flat_db(db: Dict[str, Any]) -> bool:
    """Save flat DB via material_manager."""
    return mm.save_material_db(db)


def promote_to_library(overwrite: bool = False) -> bool:
    """
    Promote material_db.json to Material_Library.json with unified schema.
    Returns True if library was created/updated.
    """
    if LIBRARY_JSON.exists() and not overwrite:
        return False

    flat_db = _load_flat_db()
    library = {
        "schema_version": "2.0",
        "description": "Unified Material Library for Injection Mold Flow",
        "materials": [],
    }

    for mfg, grades in flat_db.items():
        for grade, props in grades.items():
            key = f"{mfg}/{grade}"
            entry = {
                "key": key,
                "manufacturer": mfg,
                "grade": grade,
                "is_synthetic": mfg == "Synthetic_AI" or props.get("is_synthetic", False),
            }
            # Copy sub-blocks
            for block in ["CrossWLF", "Tait", "Thermal", "Mechanical", "Additives"]:
                if block in props:
                    entry[block] = props[block]

            # Compute derived density from Tait b1m
            tait = props.get("Tait", {})
            b1m = tait.get("b1m", 0.0009)
            entry["density"] = round(1.0 / b1m, 4) if b1m > 0 else 1.2

            library["materials"].append(entry)

    with open(LIBRARY_JSON, "w", encoding="utf-8") as f:
        json.dump(library, f, indent=4)
    print(f"[MATERIAL_DB_MANAGER] Material_Library.json created with {len(library['materials'])} entries")
    return True


def _load_library() -> Dict[str, Any]:
    """Load Material_Library.json or promote if missing."""
    if not LIBRARY_JSON.exists():
        promote_to_library()
    try:
        with open(LIBRARY_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"materials": []}


def _find_entry(key: str) -> Optional[Dict[str, Any]]:
    """Find a material entry by its key (mfg/grade)."""
    lib = _load_library()
    for entry in lib.get("materials", []):
        if entry.get("key") == key:
            return entry
    return None


def list_all_materials() -> List[str]:
    """Return flat list of 'mfg/grade' strings."""
    lib = _load_library()
    return [entry["key"] for entry in lib.get("materials", [])]


def get_material_props(key: str) -> Optional[Dict[str, Any]]:
    """Return unified dict of all properties for a material key."""
    entry = _find_entry(key)
    if not entry:
        return None
    # Flatten into unified structure
    unified = {
        "key": key,
        "manufacturer": entry.get("manufacturer", ""),
        "grade": entry.get("grade", ""),
        "is_synthetic": entry.get("is_synthetic", False),
    }
    # Extract comparison properties
    for label, prop_key, unit in COMPARISON_PROPS:
        val = _find_prop_in_entry(entry, prop_key)
        if val is not None:
            unified[label] = {"value": val, "unit": unit}

    # Include raw blocks
    for block in ["CrossWLF", "Tait", "Thermal", "Mechanical", "Additives"]:
        if block in entry:
            unified[block] = entry[block]

    return unified


def _find_prop_in_entry(entry: Dict[str, Any], prop_key: str) -> Optional[float]:
    """Search across all sub-blocks for a property key."""
    for block in ["CrossWLF", "Tait", "Thermal", "Mechanical", "Additives"]:
        sub = entry.get(block, {})
        if prop_key in sub:
            return sub[prop_key]
    # Direct key (e.g. density)
    if prop_key in entry:
        return entry[prop_key]
    return None


def compare_materials(key_a: str, key_b: str) -> Dict[str, Any]:
    """
    Compare two materials and return radar-chart compatible dict.
    Returns {material_a: ..., material_b: ..., properties: {prop: {key_a, key_b, diff, rel_diff}}}
    """
    a = get_material_props(key_a)
    b = get_material_props(key_b)
    if not a or not b:
        raise ValueError(f"Material not found: {key_a if not a else key_b}")

    props_out = {}
    for label, prop_key, unit in COMPARISON_PROPS:
        val_a = _find_prop_in_entry(a, prop_key)
        val_b = _find_prop_in_entry(b, prop_key)
        if val_a is not None and val_b is not None:
            diff = val_b - val_a
            rel_diff = diff / max(abs(val_a), 1e-12) * 100.0
            props_out[label] = {
                key_a: val_a,
                key_b: val_b,
                "diff": round(diff, 6),
                "rel_diff_pct": round(rel_diff, 2),
                "unit": unit,
            }
        else:
            props_out[label] = {
                key_a: val_a,
                key_b: val_b,
                "diff": None,
                "rel_diff_pct": None,
                "unit": unit,
            }

    return {
        "material_a": {"key": key_a, **a},
        "material_b": {"key": key_b, **b},
        "properties": props_out,
    }


def validate_material_props(cross_wlf: Dict[str, float], tait: Dict[str, float]) -> List[str]:
    """Validate Cross-WLF and Tait properties against physical bounds.
    Returns list of violation messages (empty = valid)."""
    violations = []

    n_val = cross_wlf.get("n", 0.3)
    if not (VALIDATION_BOUNDS["n"][0] <= n_val <= VALIDATION_BOUNDS["n"][1]):
        violations.append(f"Cross-WLF n={n_val} out of bounds {VALIDATION_BOUNDS['n']}")

    D1_val = cross_wlf.get("D1", 0)
    if not (VALIDATION_BOUNDS["D1"][0] <= D1_val <= VALIDATION_BOUNDS["D1"][1]):
        violations.append(f"Cross-WLF D1={D1_val:.2e} out of bounds {VALIDATION_BOUNDS['D1']}")

    b1m_val = tait.get("b1m", 0)
    if not (VALIDATION_BOUNDS["b1m"][0] <= b1m_val <= VALIDATION_BOUNDS["b1m"][1]):
        violations.append(f"Tait b1m={b1m_val:.6f} out of bounds {VALIDATION_BOUNDS['b1m']}")

    if cross_wlf.get("tau_star", 1e5) <= 0:
        violations.append(f"tau_star must be positive: {cross_wlf.get('tau_star')}")

    return violations


def register_material(
    manufacturer: str,
    grade: str,
    cross_wlf: Dict[str, float],
    tait: Dict[str, float],
    thermal: Optional[Dict[str, float]] = None,
    mechanical: Optional[Dict[str, float]] = None,
    additives: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Register a new material after validation. Returns True on success.
    Delegates to material_manager.save_material_db() for persistence.
    """
    violations = validate_material_props(cross_wlf, tait)
    if violations:
        raise ValueError(f"Material validation failed:\n" + "\n".join(violations))

    flat_db = _load_flat_db()
    if manufacturer not in flat_db:
        flat_db[manufacturer] = {}
    if grade in flat_db[manufacturer]:
        print(f"[WARN] Overwriting existing material: {manufacturer} / {grade}")

    entry = {
        "CrossWLF": cross_wlf,
        "Tait": tait,
        "Thermal": thermal or {
            "Cp_poly": 2000.0, "k_poly": 0.20, "Tg": 423.15, "Tm": 573.15
        },
        "Mechanical": mechanical or {
            "YoungsModulus": 2400.0, "PoissonsRatio": 0.35, "CTE": 6.5e-5
        },
    }
    if additives:
        entry["Additives"] = additives

    flat_db[manufacturer][grade] = entry
    ok = _save_flat_db(flat_db)
    if ok:
        promote_to_library(overwrite=True)
        print(f"[MATERIAL_DB_MANAGER] Registered {manufacturer} / {grade}")
    return ok


def generate_comparison_report(key_a: str, key_b: str) -> str:
    """Generate markdown comparison report between two materials."""
    comp = compare_materials(key_a, key_b)
    lines = []
    lines.append(f"# Material Comparison: {key_a} vs {key_b}")
    lines.append("")
    lines.append("| Property | Unit | {} | {} | Δ | Rel Δ (%) |".format(key_a, key_b))
    lines.append("|----------|------|------|------|-----|----------|")

    for label, prop_data in comp["properties"].items():
        unit = prop_data.get("unit", "-")
        va = prop_data.get(key_a, "N/A")
        vb = prop_data.get(key_b, "N/A")
        diff = prop_data.get("diff")
        rel = prop_data.get("rel_diff_pct")
        diff_str = f"{diff:+.4f}" if diff is not None else "N/A"
        rel_str = f"{rel:+.2f}%" if rel is not None else "N/A"
        va_str = f"{va:.4e}" if isinstance(va, (int, float)) else str(va)
        vb_str = f"{vb:.4e}" if isinstance(vb, (int, float)) else str(vb)
        lines.append(f"| {label} | {unit} | {va_str} | {vb_str} | {diff_str} | {rel_str} |")

    return "\n".join(lines)


def ai_synthesize_properties(density: float, melt_index: float, tensile_yield: float = 60.0,
                              family: str = "PC", tg: float = None):
    """
    AI Auto-Wizard: Synthesize Cross-WLF and Tait PvT parameters
    from minimal user input (density, melt index, tensile yield).

    Args:
        density: g/cm^3
        melt_index: MI (g/10min)
        tensile_yield: MPa
        family: resin family (PC, ABS, PP, PA66, POM, PEEK, etc.)
        tg: Glass transition temp (K). Auto-calculated if None.
    """
    if tg is None:
        family_tg = {"PC": 423.15, "ABS": 378.15, "PP": 263.15, "PA66": 323.15,
                      "POM": 213.15, "PEEK": 416.15, "PBT": 323.15, "PEI": 488.15,
                      "PMMA": 378.15, "PPS": 363.15, "LCP": 393.15, "PPSU": 493.15}
        tg = family_tg.get(family, 423.15)

    rho = density * 1000.0  # kg/m^3
    b1m = round(1.0 / rho, 6)

    family_params = {
        "PC":    {"n": 0.30, "A1": 31.2, "D2": 413.15, "A2": 51.6, "tau": 1.8e5,
                   "b2m": 1.2e-6, "b3m": 1.3e8, "b4m": 0.0035, "b5": 413.15, "C": 0.0894,
                   "Cp": 2000, "k": 0.20, "Tm": 573.15, "E0": 2200, "cte": 6.5e-5},
        "ABS":   {"n": 0.35, "A1": 28.5, "D2": 263.15, "A2": 51.6, "tau": 2.8e5,
                   "b2m": 1.0e-6, "b3m": 1.2e8, "b4m": 0.004, "b5": 263.15, "C": 0.0894,
                   "Cp": 2100, "k": 0.18, "Tm": 513.15, "E0": 2400, "cte": 8.0e-5},
        "PP":    {"n": 0.38, "A1": 26.0, "D2": 263.15, "A2": 51.6, "tau": 1.5e5,
                   "b2m": 1.5e-6, "b3m": 1.0e8, "b4m": 0.0045, "b5": 263.15, "C": 0.0894,
                   "Cp": 1900, "k": 0.22, "Tm": 433.15, "E0": 1500, "cte": 1.0e-4},
        "PA66":  {"n": 0.33, "A1": 29.0, "D2": 323.15, "A2": 51.6, "tau": 2.0e5,
                   "b2m": 1.0e-6, "b3m": 1.2e8, "b4m": 0.0038, "b5": 323.15, "C": 0.0894,
                   "Cp": 2050, "k": 0.26, "Tm": 533.15, "E0": 3200, "cte": 8.0e-5},
    }
    fp = family_params.get(family, family_params["PC"])

    # Estimate D1 from MI: Lower MI => higher D1 (higher viscosity)
    D1 = round(fp["tau"] * (1.0 / max(melt_index, 0.1)) ** fp["n"] * 1e7, 2)
    # Bound D1 to physical ranges per family
    D1_bounds = {"PC": (1e12, 1e15), "ABS": (1e10, 1e13), "PP": (1e8, 1e11), "PA66": (1e10, 1e13)}
    lo, hi = D1_bounds.get(family, (1e10, 1e14))
    D1 = max(lo, min(hi, D1))

    # Estimate E from tensile yield
    E_est = tensile_yield * 35.0  # approximate E/Y ratio
    E_est = max(100, min(100000, E_est))

    cross_wlf = {"n": fp["n"], "tau_star": fp["tau"], "D1": D1, "D2": fp["D2"],
                  "D3": 0, "A1": fp["A1"], "A2": fp["A2"]}
    tait = {"b1m": b1m, "b2m": fp["b2m"], "b3m": fp["b3m"], "b4m": fp["b4m"],
             "b5": fp["b5"], "b6": 0, "b7": 0, "b8": 0, "b9": 0, "C_tait": fp["C"]}
    thermal = {"Cp_poly": fp["Cp"], "k_poly": fp["k"], "Tg": tg, "Tm": fp["Tm"]}
    mechanical = {"YoungsModulus": round(E_est,1), "PoissonsRatio": 0.36, "CTE": fp["cte"]}

    return {"CrossWLF": cross_wlf, "Tait": tait, "Thermal": thermal, "Mechanical": mechanical}


def auto_register_synthetic(manufacturer: str, grade: str, density: float, melt_index: float,
                             tensile_yield: float = 60.0, family: str = "PC", tg: float = None) -> bool:
    """
    One-click: synthesize properties AND register the material in one call.
    Returns True on success.
    """
    props = ai_synthesize_properties(density, melt_index, tensile_yield, family, tg)
    return register_material(manufacturer, grade, props["CrossWLF"], props["Tait"],
                              props["Thermal"], props["Mechanical"])


if __name__ == "__main__":
    promote_to_library()
    mats = list_all_materials()
    print(f"[MATERIAL_DB_MANAGER] Available materials ({len(mats)}):")
    for m in mats:
        print(f"  - {m}")
    print("\nMaterial Library ready.")