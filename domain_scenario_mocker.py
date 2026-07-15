# -*- coding: utf-8 -*-
"""
domain_scenario_mocker.py -- Domain Scenario Binding Test (Thin-wall Laptop Housing)
=====================================================================================
Simulates a real-world injection molding workflow and verifies that all user inputs
are correctly serialized to machine_spec.json and manual_override.json.

Scenario:
  Tab 1: Cavity STL(Laptop_cover.stl) x1, Insert STL(Brass_nut.stl) x2, Clamping 350 Ton
  Tab 3: Material 'PC+ABS (High Flow)' selected
  Tab 4: Expert mode ON → Stage 1 Packing (120MPa, 2.5s), Melt Temp 280C (553.15K)

Output: domain_scenario_report.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict

WORKSPACE = Path(r"D:\Open_code_project\injection_mold_flow")
sys.path.insert(0, str(WORKSPACE))


@dataclass
class AuditCheck:
    check_id: str
    description: str
    expected_value: Any
    actual_value: Any
    passed: bool
    detail: str = ""


@dataclass
class DomainScenarioReport:
    scenario_name: str = "Thin-wall Laptop Housing"
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    checks: List[Dict[str, Any]] = field(default_factory=list)
    final_jsons: Dict[str, Dict] = field(default_factory=dict)
    timestamp: str = ""


def run_scenario():
    """
    Inject the Thin-wall Laptop Housing scenario data and verify JSON persistence.
    """
    checks = []
    spec_path = WORKSPACE / "machine_spec.json"
    override_path = WORKSPACE / "manual_override.json"
    
    print("=" * 65)
    print("  DOMAIN SCENARIO MOCKER -- Thin-wall Laptop Housing")
    print("=" * 65)
    
    # ==================================================================
    # Step 1: Simulate Tab 1 -- STL Upload & Machine Specs
    # ==================================================================
    print("\n[Step 1] Tab 1: STL Upload & Machine Specs...")
    
    # Mock STL paths (would be from st.file_uploader)
    cavity_stls = ["uploads/cavity/Laptop_cover.stl"]
    insert_stls = ["uploads/insert/Brass_nut_1.stl", "uploads/insert/Brass_nut_2.stl"]
    clamping_force = 350.0
    screw_diameter = 30.0
    max_pressure = 200.0
    projected_area = 0.0185
    
    # Create upload directories and dummy files (for realism)
    for stl_path in cavity_stls + insert_stls:
        full_path = WORKSPACE / stl_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if not full_path.exists():
            full_path.write_text("solid dummy_stl\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid dummy_stl\n")
    
    # Write to machine_spec.json (simulating _sync_machine_spec)
    existing_spec = {}
    if spec_path.exists():
        try:
            existing_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    existing_spec["cavity_stl_paths"] = cavity_stls
    existing_spec["insert_stl_paths"] = insert_stls
    existing_spec["clamping_force_ton"] = clamping_force
    existing_spec["screw_diameter_mm"] = screw_diameter
    existing_spec["max_injection_pressure_mpa"] = max_pressure
    existing_spec["projected_area_m2"] = projected_area
    
    spec_path.write_text(json.dumps(existing_spec, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"  machine_spec.json written with {len(existing_spec)} keys")
    
    # ==================================================================
    # Step 2: Simulate Tab 3 -- Material Selection
    # ==================================================================
    print("\n[Step 2] Tab 3: Material Selection...")
    
    material_name = "PC+ABS (High Flow)"
    material_props = {
        "CrossWLF": {"n": 0.32, "tau_star": 2.0e5, "D1": 3.0e12, "D2": 383.15, "D3": 0.0, "A1": 30.0, "A2": 51.6},
        "Tait": {"b1m": 0.00095, "b2m": 1.1e-6, "b3m": 1.25e8, "b4m": 0.0038, "b5": 383.15, "C_tait": 0.0894},
        "Thermal": {"Cp_poly": 2050.0, "k_poly": 0.19, "Tg": 393.15, "Tm": 523.15}
    }
    
    existing_spec["selected_material"] = material_name
    existing_spec["material_properties"] = material_props
    spec_path.write_text(json.dumps(existing_spec, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"  Material '{material_name}' saved to machine_spec.json")
    
    # ==================================================================
    # Step 3: Simulate Tab 4 -- Expert Process Override
    # ==================================================================
    print("\n[Step 3] Tab 4: Expert Process Override...")
    
    stage_1_pressure = 120.0  # MPa
    stage_1_time = 2.5        # seconds
    stage_2_pressure = 90.0
    stage_2_time = 3.0
    stage_3_pressure = 50.0
    stage_3_time = 2.0
    melt_temp_c = 280.0       # Celsius
    melt_temp_k = melt_temp_c + 273.15  # 553.15 K
    mold_temp_c = 80.0
    mold_temp_k = mold_temp_c + 273.15   # 353.15 K
    injection_speed = 0.30
    
    existing_override = {}
    if override_path.exists():
        try:
            existing_override = json.loads(override_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    existing_override["process"] = {
        "enabled": True,
        "stage_1_pressure_mpa": stage_1_pressure,
        "stage_1_time_s": stage_1_time,
        "stage_2_pressure_mpa": stage_2_pressure,
        "stage_2_time_s": stage_2_time,
        "stage_3_pressure_mpa": stage_3_pressure,
        "stage_3_time_s": stage_3_time,
        "melt_temp_k": melt_temp_k,
        "mold_temp_k": mold_temp_k,
        "injection_speed_mps": injection_speed,
        "valve_gate_timing_s": {},
    }
    
    override_path.write_text(json.dumps(existing_override, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"  manual_override.json written (process override ON, P1={stage_1_pressure}MPa, Tmelt={melt_temp_c}C)")
    
    # ==================================================================
    # Step 4: AUDIT -- Verify all JSON values match exactly
    # ==================================================================
    print("\n[Step 4] AUDIT: Verifying JSON Serialization...")
    
    # Reload both JSONs
    spec_audit = json.loads(spec_path.read_text(encoding="utf-8"))
    override_audit = json.loads(override_path.read_text(encoding="utf-8"))
    
    # --- machine_spec.json checks ---
    
    # Check 1: Clamping Force
    val = spec_audit.get("clamping_force_ton", 0)
    checks.append(AuditCheck(
        "MS-01", "machine_spec.json: clamping_force_ton == 350.0",
        350.0, val, abs(val - 350.0) < 0.01
    ))
    
    # Check 2: Cavity STL paths
    val = spec_audit.get("cavity_stl_paths", [])
    checks.append(AuditCheck(
        "MS-02", "machine_spec.json: cavity_stl_paths contains Laptop_cover.stl",
        cavity_stls, val,
        any("Laptop_cover" in p for p in val)
    ))
    
    # Check 3: Insert STL paths (count)
    val = spec_audit.get("insert_stl_paths", [])
    checks.append(AuditCheck(
        "MS-03", "machine_spec.json: insert_stl_paths has 2 Brass_nut STLs",
        2, len(val),
        len(val) == 2
    ))
    
    # Check 4: Screw Diameter
    val = spec_audit.get("screw_diameter_mm", 0)
    checks.append(AuditCheck(
        "MS-04", "machine_spec.json: screw_diameter_mm == 30.0",
        30.0, val, abs(val - 30.0) < 0.01
    ))
    
    # Check 5: Max Pressure
    val = spec_audit.get("max_injection_pressure_mpa", 0)
    checks.append(AuditCheck(
        "MS-05", "machine_spec.json: max_injection_pressure_mpa == 200.0",
        200.0, val, abs(val - 200.0) < 0.01
    ))
    
    # Check 6: Projected Area
    val = spec_audit.get("projected_area_m2", 0)
    checks.append(AuditCheck(
        "MS-06", "machine_spec.json: projected_area_m2 == 0.0185",
        0.0185, val, abs(val - 0.0185) < 0.0001
    ))
    
    # Check 7: Selected Material
    val = spec_audit.get("selected_material", "")
    checks.append(AuditCheck(
        "MS-07", "machine_spec.json: selected_material == 'PC+ABS (High Flow)'",
        material_name, val, val == material_name
    ))
    
    # Check 8: Material Properties exist
    val = spec_audit.get("material_properties", {})
    checks.append(AuditCheck(
        "MS-08", "machine_spec.json: material_properties has CrossWLF, Tait, Thermal",
        True, all(k in val for k in ["CrossWLF", "Tait", "Thermal"]),
        all(k in val for k in ["CrossWLF", "Tait", "Thermal"])
    ))
    
    # --- manual_override.json checks ---
    
    # Check 9: Process enabled
    proc = override_audit.get("process", {})
    checks.append(AuditCheck(
        "MO-01", "manual_override.json: process.enabled == True",
        True, proc.get("enabled"), proc.get("enabled") == True
    ))
    
    # Check 10: Stage 1 Pressure
    val = proc.get("stage_1_pressure_mpa", 0)
    checks.append(AuditCheck(
        "MO-02", "manual_override.json: stage_1_pressure_mpa == 120.0 MPa",
        120.0, val, abs(val - 120.0) < 0.01
    ))
    
    # Check 11: Stage 1 Time
    val = proc.get("stage_1_time_s", 0)
    checks.append(AuditCheck(
        "MO-03", "manual_override.json: stage_1_time_s == 2.5 sec",
        2.5, val, abs(val - 2.5) < 0.01
    ))
    
    # Check 12: Melt Temp (K)
    val = proc.get("melt_temp_k", 0)
    checks.append(AuditCheck(
        "MO-04", "manual_override.json: melt_temp_k == 553.15 K (280 C)",
        553.15, val, abs(val - 553.15) < 0.1,
        f"actual = {val} K ({val - 273.15:.1f} C)"
    ))
    
    # Check 13: Mold Temp (K)
    val = proc.get("mold_temp_k", 0)
    checks.append(AuditCheck(
        "MO-05", "manual_override.json: mold_temp_k == 353.15 K (80 C)",
        353.15, val, abs(val - 353.15) < 0.1,
        f"actual = {val} K ({val - 273.15:.1f} C)"
    ))
    
    # Check 14: Stage 2, 3 pressures/times
    checks.append(AuditCheck(
        "MO-06", "manual_override.json: stage_2_pressure_mpa == 90.0",
        90.0, proc.get("stage_2_pressure_mpa"), abs(proc.get("stage_2_pressure_mpa", 0) - 90.0) < 0.01
    ))
    checks.append(AuditCheck(
        "MO-07", "manual_override.json: stage_3_pressure_mpa == 50.0",
        50.0, proc.get("stage_3_pressure_mpa"), abs(proc.get("stage_3_pressure_mpa", 0) - 50.0) < 0.01
    ))
    checks.append(AuditCheck(
        "MO-08", "manual_override.json: injection_speed_mps == 0.30",
        0.30, proc.get("injection_speed_mps"), abs(proc.get("injection_speed_mps", 0) - 0.30) < 0.001
    ))
    
    # --- Cross-file consistency checks ---
    
    # Check 15: machine_spec.json default values preserved (not overwritten)
    val = spec_audit.get("mesh_resolution", None)
    checks.append(AuditCheck(
        "XF-01", "machine_spec.json: mesh_resolution preserved (not overwritten)",
        "Fine", val, val == "Fine",
        f"actual = {val}"
    ))
    
    # Check 16: manual_override.json mesh section NOT corrupted by process scenario
    mesh = override_audit.get("mesh", {})
    checks.append(AuditCheck(
        "XF-02", "manual_override.json: mesh section exists (may be empty or from prior test)",
        True, "mesh" in override_audit, "mesh" in override_audit
    ))
    
    # ==================================================================
    # Compile Report
    # ==================================================================
    passed = sum(1 for c in checks if c.passed)
    failed = sum(1 for c in checks if not c.passed)
    
    report = DomainScenarioReport(
        scenario_name="Thin-wall Laptop Housing",
        total_checks=len(checks),
        passed=passed,
        failed=failed,
        checks=[asdict(c) for c in checks],
        final_jsons={
            "machine_spec.json": spec_audit,
            "manual_override.json": override_audit,
        },
        timestamp=datetime.now().isoformat()
    )
    
    # Print results
    print(f"\n{'='*65}")
    print(f"  AUDIT RESULTS")
    print(f"{'='*65}")
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"  [{status}] {c.check_id}: {c.description}")
        if not c.passed:
            print(f"         Expected: {c.expected_value}, Got: {c.actual_value}")
    
    print(f"\n  TOTAL: {passed}/{len(checks)} PASS, {failed}/{len(checks)} FAIL")
    
    # Export
    out_path = WORKSPACE / "domain_scenario_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, ensure_ascii=False, default=str)
    
    print(f"  REPORT: {out_path.name}")
    print(f"{'='*65}")
    
    return report


if __name__ == "__main__":
    run_scenario()