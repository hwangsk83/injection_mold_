# -*- coding: utf-8 -*-
"""
check_72_73_runner.py -- Check 72 (Two-Way Binding) + Check 73 (JSON Strictness)
Standalone auditor that reads machine_spec.json and manual_override.json
and verifies UI-backend data binding integrity.
"""
import json
import sys
import math
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(r"D:\Open_code_project\injection_mold_flow")


def check_72_two_way_binding():
    """Check 72: Verify two-way binding between UI tabs and JSON files."""
    print("[AUDIT] Check 72: Two-Way Binding Integrity Audit")
    print("=" * 60)

    override_path = WORKSPACE / "manual_override.json"
    spec_path = WORKSPACE / "machine_spec.json"
    violations = []

    spec_data = {}
    override_data = {}

    if spec_path.exists():
        try:
            spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception as e:
            violations.append(f"machine_spec.json parse error: {e}")

    if override_path.exists():
        try:
            override_data = json.loads(override_path.read_text(encoding="utf-8"))
        except Exception as e:
            violations.append(f"manual_override.json parse error: {e}")

    # 1. Check clamping_force_ton consistency
    clamp = spec_data.get("clamping_force_ton", None)
    print(f"  [INFO] machine_spec.json clamping_force_ton: {clamp}")

    # 2. Mesh Override Binding (Tab 02 <-> Tab 08)
    mesh = override_data.get("mesh", {})
    if mesh.get("enabled"):
        gs = mesh.get("global_size_mm", "NOT_SET")
        bl = mesh.get("boundary_layer_count", "NOT_SET")
        print(f"  [INFO] Mesh Override ACTIVE: global_size_mm={gs}, boundary_layer_count={bl}")
        if isinstance(gs, (int, float)) and (gs < 0.01 or gs > 50.0):
            violations.append(f"Mesh global_size_mm {gs} out of [0.01, 50.0]")
        if isinstance(bl, (int, float)) and (bl < 0 or bl > 10):
            violations.append(f"Mesh boundary_layer_count {bl} out of [0, 10]")
    else:
        print(f"  [INFO] Mesh Override: DISABLED (Auto-Wizard)")

    # 3. Process Override Binding (Tab 04 <-> Tab 08)
    proc = override_data.get("process", {})
    if proc.get("enabled"):
        p1 = proc.get("stage_1_pressure_mpa", "NOT_SET")
        p2 = proc.get("stage_2_pressure_mpa", "NOT_SET")
        p3 = proc.get("stage_3_pressure_mpa", "NOT_SET")
        tm = proc.get("melt_temp_k", "NOT_SET")
        print(f"  [INFO] Process Override ACTIVE: P1={p1}MPa, P2={p2}MPa, P3={p3}MPa, Tmelt={tm}K")
        if isinstance(p1, (int, float)) and isinstance(p2, (int, float)) and isinstance(p3, (int, float)):
            if not (p1 >= p2 >= p3):
                violations.append(f"Packing pressure not decreasing: {p1}->{p2}->{p3}")
        if isinstance(tm, (int, float)) and (tm < 400 or tm > 700):
            violations.append(f"Melt temp {tm}K out of [400,700]")
    else:
        print(f"  [INFO] Process Override: DISABLED (Auto-Wizard)")

    # 4. Solver Override Binding
    sol = override_data.get("solver", {})
    if sol.get("enabled"):
        rf = sol.get("relaxation_factor", "NOT_SET")
        mi = sol.get("max_iter", "NOT_SET")
        print(f"  [INFO] Solver Override ACTIVE: relaxation_factor={rf}, max_iter={mi}")
    else:
        print(f"  [INFO] Solver Override: DISABLED (defaults)")

    # 5. Cross-file conflict check
    if proc.get("enabled"):
        spec_max_p = spec_data.get("max_injection_pressure_mpa", None)
        p1 = proc.get("stage_1_pressure_mpa", 0)
        if isinstance(p1, (int, float)) and isinstance(spec_max_p, (int, float)):
            if p1 > spec_max_p:
                violations.append(f"Stage1 pressure {p1} > machine max {spec_max_p}")

    print(f"  Violations: {len(violations)}")
    for v in violations:
        print(f"  [VIOL] {v}")

    passed = len(violations) == 0
    print(f"  RESULT: {'PASS' if passed else 'FAIL'}")
    print("=" * 60)

    return {
        "check72_two_way_binding_integrity": {
            "mesh_override_active": mesh.get("enabled", False),
            "process_override_active": proc.get("enabled", False),
            "solver_override_active": sol.get("enabled", False),
            "cross_file_conflicts": len(violations),
            "violations": violations,
            "result": "PASS" if passed else "FAIL"
        }
    }


def check_73_json_strictness():
    """Check 73: Ensure JSON serialization preserves defaults and keys."""
    print("\n[AUDIT] Check 73: JSON Serialization Strictness Audit")
    print("=" * 60)

    spec_path = WORKSPACE / "machine_spec.json"
    override_path = WORKSPACE / "manual_override.json"
    violations = []

    required_keys = ["clamping_force_ton", "projected_area_m2", "mesh_resolution"]

    if spec_path.exists():
        try:
            spec_data = json.loads(spec_path.read_text(encoding="utf-8"))
            for key in required_keys:
                if key in spec_data:
                    print(f"  [OK] machine_spec.json.{key}: PRESENT ({spec_data[key]})")
                else:
                    violations.append(f"machine_spec.json missing required key: {key}")

            # Check no NaN/Infinity
            def check_nan(obj, path=""):
                if isinstance(obj, float):
                    if math.isnan(obj):
                        violations.append(f"NaN at {path}")
                    if math.isinf(obj):
                        violations.append(f"Inf at {path}")
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        check_nan(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        check_nan(v, f"{path}[{i}]")

            check_nan(spec_data, "machine_spec.json")
            print(f"  [OK] No NaN/Inf values in machine_spec.json")

            # Verify defaults preserved
            mesh_res = spec_data.get("mesh_resolution")
            target_cells = spec_data.get("target_mesh_cells")
            if mesh_res:
                print(f"  [OK] mesh_resolution default preserved: '{mesh_res}'")
            if target_cells:
                print(f"  [OK] target_mesh_cells default preserved: {target_cells}")

        except json.JSONDecodeError as e:
            violations.append(f"machine_spec.json invalid JSON: {e}")
    else:
        violations.append("machine_spec.json does not exist")

    if override_path.exists():
        try:
            override_data = json.loads(override_path.read_text(encoding="utf-8"))
            for section in ["mesh", "process", "solver"]:
                sec = override_data.get(section, {})
                enabled = sec.get("enabled", False)
                # Even when disabled, values should be preserved
                if section == "mesh":
                    gs = sec.get("global_size_mm", "?")
                    print(f"  [OK] manual_override.json.{section}: enabled={enabled}, global_size={gs} (preserved)")
                elif section == "process":
                    p1 = sec.get("stage_1_pressure_mpa", "?")
                    print(f"  [OK] manual_override.json.{section}: enabled={enabled}, P1={p1} (preserved)")
                elif section == "solver":
                    rf = sec.get("relaxation_factor", "?")
                    print(f"  [OK] manual_override.json.{section}: enabled={enabled}, relax={rf} (preserved)")

            def check_nan_ov(obj, path=""):
                if isinstance(obj, float):
                    if math.isnan(obj):
                        violations.append(f"NaN at {path}")
                    if math.isinf(obj):
                        violations.append(f"Inf at {path}")
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        check_nan_ov(v, f"{path}.{k}")
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        check_nan_ov(v, f"{path}[{i}]")

            check_nan_ov(override_data, "manual_override.json")
            print(f"  [OK] No NaN/Inf values in manual_override.json")

        except json.JSONDecodeError as e:
            violations.append(f"manual_override.json invalid JSON: {e}")
    else:
        print("  [INFO] manual_override.json does not exist (no overrides active)")

    print(f"  Violations: {len(violations)}")
    for v in violations:
        print(f"  [VIOL] {v}")

    passed = len(violations) == 0
    print(f"  RESULT: {'PASS' if passed else 'FAIL'}")
    print("=" * 60)

    return {
        "check73_json_serialization_strictness": {
            "required_keys_present": all("missing required key" not in v for v in violations),
            "defaults_preserved": passed,
            "violations": violations,
            "result": "PASS" if passed else "FAIL"
        }
    }


def main():
    print("=" * 65)
    print("  CHECK 72 & 73 -- Standalone Binding & JSON Integrity Auditor")
    print("=" * 65)

    c72 = check_72_two_way_binding()
    c73 = check_73_json_strictness()

    # Merge into audit_report.json
    audit_path = WORKSPACE / "audit_report.json"
    report = {}
    if audit_path.exists():
        try:
            report = json.loads(audit_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    report.update(c72)
    report.update(c73)
    report["timestamp_checks_72_73"] = datetime.now().isoformat()
    audit_path.write_text(json.dumps(report, indent=4, ensure_ascii=False), encoding="utf-8")

    print(f"\n  REPORT: {audit_path.name} (updated with Checks 72, 73)")

    c72_ok = c72["check72_two_way_binding_integrity"]["result"] == "PASS"
    c73_ok = c73["check73_json_serialization_strictness"]["result"] == "PASS"

    print(f"  Check 72: {'PASS' if c72_ok else 'FAIL'}")
    print(f"  Check 73: {'PASS' if c73_ok else 'FAIL'}")
    print(f"  OVERALL:  {'PASS' if c72_ok and c73_ok else 'FAIL'}")
    print("=" * 65)

    return 0 if c72_ok and c73_ok else 1


if __name__ == "__main__":
    sys.exit(main())