#!/usr/bin/env python3
# material_manager.py - Dual-track Material Database Manager with Partitioning
import os
import re
import json
import copy
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
DB_JSON = WORKSPACE / "material_db.json"

DEFAULT_DB: Dict[str, Any] = {
    "Generic": {
        "ABS": {
            "CrossWLF": {
                "n": 0.35, "tau_star": 2.8e5, "D1": 3.8e11, "D2": 263.15, "D3": 0.0, "A1": 28.5, "A2": 51.6
            },
            "Tait": {
                "b1m": 0.001, "b2m": 1.0e-6, "b3m": 1.2e8, "b4m": 0.004, "b5": 263.15,
                "b6": 0.0, "b7": 0.0, "b8": 0.0, "b9": 0.0, "C_tait": 0.0894
            },
            "Thermal": {
                "Cp_poly": 2100.0, "k_poly": 0.18, "Tg": 378.15, "Tm": 513.15
            },
            "Mechanical": {
                "YoungsModulus": 2400.0,
                "PoissonsRatio": 0.35,
                "CTE": 8.0e-5
            }
        },
        "PC": {
            "CrossWLF": {
                "n": 0.30, "tau_star": 1.8e5, "D1": 2.4e13, "D2": 413.15, "D3": 0.0, "A1": 31.2, "A2": 51.6
            },
            "Tait": {
                "b1m": 0.0009, "b2m": 1.2e-6, "b3m": 1.3e8, "b4m": 0.0035, "b5": 413.15,
                "b6": 0.0, "b7": 0.0, "b8": 0.0, "b9": 0.0, "C_tait": 0.0894
            },
            "Thermal": {
                "Cp_poly": 2000.0, "k_poly": 0.20, "Tg": 423.15, "Tm": 573.15
            },
            "Mechanical": {
                "YoungsModulus": 2200.0,
                "PoissonsRatio": 0.37,
                "CTE": 6.5e-5
            }
        }
    }
}

COMPOSITE_MATERIALS: Dict[str, Any] = {
    "Generic": {
        "PC+GF20": {
            "CrossWLF": {
                "n": 0.32, "tau_star": 1.95e5, "D1": 2.0e13, "D2": 413.15, "D3": 0.0, "A1": 30.8, "A2": 51.6
            },
            "Tait": {
                "b1m": 8.8e-4, "b2m": 1.1e-6, "b3m": 1.35e8, "b4m": 3.4e-3, "b5": 413.15,
                "b6": 0.0, "b7": 0.0, "b8": 0.0, "b9": 0.0, "C_tait": 0.0894
            },
            "Thermal": {
                "Cp_poly": 1850.0, "k_poly": 0.26, "Tg": 423.15, "Tm": 573.15
            },
            "Mechanical": {
                "YoungsModulus": 5800.0,
                "PoissonsRatio": 0.33,
                "CTE": 3.2e-5
            },
            "Additives": {
                "filler_type": "Fiber",
                "filler_name": "GlassFiber",
                "weight_fraction": 0.20,
                "volume_fraction": 0.112,
                "aspect_ratio": 25.0,
                "filler_modulus_MPa": 72000.0,
                "filler_CTE": 5.0e-6,
                "filler_poisson": 0.20,
                "matrix_grade": "PC"
            }
        },
        "ABS+Talc15": {
            "CrossWLF": {
                "n": 0.34, "tau_star": 2.65e5, "D1": 3.2e11, "D2": 263.15, "D3": 0.0, "A1": 28.2, "A2": 51.6
            },
            "Tait": {
                "b1m": 9.5e-4, "b2m": 9.5e-7, "b3m": 1.25e8, "b4m": 3.8e-3, "b5": 263.15,
                "b6": 0.0, "b7": 0.0, "b8": 0.0, "b9": 0.0, "C_tait": 0.0894
            },
            "Thermal": {
                "Cp_poly": 1950.0, "k_poly": 0.22, "Tg": 378.15, "Tm": 513.15
            },
            "Mechanical": {
                "YoungsModulus": 3800.0,
                "PoissonsRatio": 0.35,
                "CTE": 5.5e-5
            },
            "Additives": {
                "filler_type": "Flake",
                "filler_name": "Talc",
                "weight_fraction": 0.15,
                "volume_fraction": 0.073,
                "aspect_ratio": 5.0,
                "filler_modulus_MPa": 60000.0,
                "filler_CTE": 8.0e-6,
                "filler_poisson": 0.25,
                "matrix_grade": "ABS"
            }
        }
    }
}

def load_partitioned_db() -> Dict[str, Any]:
    """Loads the database with dual partitions: Commercial_UDB_DB and Synthetic_AI_DB."""
    if not DB_JSON.exists():
        initial_db = {
            "Commercial_UDB_DB": _merge_composite_materials(DEFAULT_DB),
            "Synthetic_AI_DB": {
                "Synthetic_AI": {}
            }
        }
        with open(DB_JSON, "w", encoding="utf-8") as f:
            json.dump(initial_db, f, indent=4)
        return initial_db

    try:
        with open(DB_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Migrate old DB format to partitioned format
        if "Commercial_UDB_DB" not in data:
            migrated = {
                "Commercial_UDB_DB": data,
                "Synthetic_AI_DB": {
                    "Synthetic_AI": {}
                }
            }
            with open(DB_JSON, "w", encoding="utf-8") as f:
                json.dump(migrated, f, indent=4)
            return migrated
            
        return data
    except Exception as e:
        print(f"[WARN] Failed to load database partitions: {e}. Reverting to default.")
        return {
            "Commercial_UDB_DB": _merge_composite_materials(DEFAULT_DB),
            "Synthetic_AI_DB": {
                "Synthetic_AI": {}
            }
        }

def save_partitioned_db(raw_db: Dict[str, Any]) -> bool:
    """Saves raw partitioned DB representation to file."""
    try:
        with open(DB_JSON, "w", encoding="utf-8") as f:
            json.dump(raw_db, f, indent=4)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save partitioned database: {e}")
        return False

def load_material_db() -> Dict[str, Any]:
    """
    Downstream-compatible interface. Merges partitions into a unified flat view
    so that existing client scripts are completely unaffected.
    """
    raw_db = load_partitioned_db()
    merged = {}
    
    # Merge Commercial and Synthetic manufacturer subkeys
    for partition_name in ["Commercial_UDB_DB", "Synthetic_AI_DB"]:
        partition = raw_db.get(partition_name, {})
        for mfg, grades in partition.items():
            if mfg not in merged:
                merged[mfg] = {}
            for grade, props in grades.items():
                merged[mfg][grade] = props
                
    return merged

def save_material_db(flat_db: Dict[str, Any]) -> bool:
    """
    Saves flat DB format back into partitioned format by routing
    synthetic materials into Synthetic_AI_DB and commercial ones into Commercial_UDB_DB.
    """
    raw_db = load_partitioned_db()
    
    # Initialize clean partitions
    raw_db["Commercial_UDB_DB"] = {}
    raw_db["Synthetic_AI_DB"] = {}
    
    for mfg, grades in flat_db.items():
        for grade, props in grades.items():
            is_synthetic = props.get("is_synthetic", False) or mfg == "Synthetic_AI"
            partition_key = "Synthetic_AI_DB" if is_synthetic else "Commercial_UDB_DB"
            
            if mfg not in raw_db[partition_key]:
                raw_db[partition_key][mfg] = {}
            raw_db[partition_key][mfg][grade] = props
            
    return save_partitioned_db(raw_db)

def _merge_composite_materials(db: Dict[str, Any]) -> Dict[str, Any]:
    import copy
    result = copy.deepcopy(db)
    for mfg, grades in COMPOSITE_MATERIALS.items():
        if mfg not in result:
            result[mfg] = {}
        for grade, props in grades.items():
            result[mfg][grade] = props
    return result

def inject_composite_materials() -> bool:
    try:
        db = load_material_db()
        db = _merge_composite_materials(db)
        return save_material_db(db)
    except Exception as e:
        print(f"[ERROR] inject_composite_materials failed: {e}")
        return False

def get_additive_props(mfg: str = "Generic", grade: str = "PC+GF20") -> Optional[Dict[str, Any]]:
    try:
        db = load_material_db()
        return db[mfg][grade].get("Additives", None)
    except Exception:
        return None

def get_mechanical_props(mfg: str = "Generic", grade: str = "ABS") -> Dict[str, Any]:
    try:
        db = load_material_db()
        return db[mfg][grade].get("Mechanical", {
            "YoungsModulus": 2400.0, "PoissonsRatio": 0.35, "CTE": 8.0e-5
        })
    except Exception:
        return {"YoungsModulus": 2400.0, "PoissonsRatio": 0.35, "CTE": 8.0e-5}

def parse_material_file(file_path: str) -> Optional[Dict[str, Any]]:
    ext = Path(file_path).suffix.lower()
    parsed_data: Dict[str, Any] = {
        "CrossWLF": {}, "Tait": {}, "Thermal": {},
        "Mechanical": {"YoungsModulus": 2400.0, "PoissonsRatio": 0.35, "CTE": 8.0e-5}
    }
    try:
        if ext == ".xml":
            tree = ET.parse(file_path)
            root = tree.getroot()
            for prop in root.findall(".//Property"):
                name = prop.get("name", "")
                if "CrossWLF" in name or "Viscosity" in name:
                    for param in prop.findall("Parameter"):
                        parsed_data["CrossWLF"][param.get("name")] = float(param.get("value", 0))
                elif "Tait" in name or "PvT" in name:
                    for param in prop.findall("Parameter"):
                        parsed_data["Tait"][param.get("name")] = float(param.get("value", 0))
        return parsed_data
    except Exception:
        return None

if __name__ == "__main__":
    inject_composite_materials()
    print("[SUCCESS] Partitioned material manager ready and composite materials injected.")
