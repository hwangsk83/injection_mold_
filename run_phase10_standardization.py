#!/usr/bin/env python3
"""
run_phase10_standardization.py - Phase 10 Standardization Pipeline Orchestrator

Executes the complete standardization pipeline:
1. material_db_manager.py -> Material_Library.json
2. verification_framework.py -> V&V benchmark
3. report_generator.py -> Final Standard Technical Report
4. system_auditor.py -> Check 49 & 50 final stamp
"""
import os, sys, subprocess, json, time
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SCRIPTS = [
    ("material_db_manager.py", "Material Library Promotion"),
    ("verification_framework.py", "V&V Benchmark Verification"),
    ("report_generator.py", "Standard Technical Report Generation"),
    ("system_auditor.py", "Final Integrity Audit (Checks 1-50)"),
]

def print_banner(text):
    print("")
    print("=" * 62)
    print(f"  [PHASE10] {text}")
    print("=" * 62)

def run_script(name, label):
    print_banner("Step: " + label)
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, name],
            cwd=str(WORKSPACE),
            capture_output=True, text=True, timeout=300
        )
        elapsed = time.time() - t0
        print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
        if result.returncode != 0:
            print(f"  [ERROR] {name} exited with code {result.returncode}")
            print(result.stderr[-500:])
            return False
        print(f"  [OK] {label} completed in {elapsed:.1f}s")
        return True
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {name} exceeded 300s limit")
        return False
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        return False

def generate_summary():
    print_banner("Phase 10 Pipeline Complete")
    report_md = WORKSPACE / "Final_Standard_Technical_Report.md"
    vv_hist = WORKSPACE / "vv_history.json"
    library = WORKSPACE / "Material_Library.json"

    print(f"  Final Report: {'[EXISTS]' if report_md.exists() else '[MISSING]'}")
    if report_md.exists():
        print(f"     Size: {report_md.stat().st_size:,} bytes")

    if vv_hist.exists():
        try:
            hist = json.load(open(vv_hist))
            verdict = hist.get("latest_verdict", "UNKNOWN")
            n_runs = len(hist.get("runs", []))
            print(f"  V&V History: {n_runs} run(s), latest={verdict}")
        except Exception:
            print(f"  V&V History: [PARSE ERROR]")

    if library.exists():
        try:
            lib = json.load(open(library))
            n_mats = len(lib.get("materials", []))
            print(f"  Material Library: {n_mats} materials registered")
        except Exception:
            print(f"  Material Library: [PARSE ERROR]")

    print("")
    print("=" * 62)
    print("  [PHASE10] Standardization Pipeline - ALL STEPS COMPLETE")
    print("=" * 62)

def main():
    print("=" * 62)
    print("  [PHASE10] Standardization Pipeline - Starting")
    print("  Workspace: " + str(WORKSPACE))
    print("=" * 62)

    all_ok = True
    for script, label in SCRIPTS:
        path = WORKSPACE / script
        if not path.exists():
            print(f"  [SKIP] {script} not found")
            continue
        ok = run_script(script, label)
        if not ok:
            all_ok = False
            print(f"  [WARN] {label} reported issues")

    generate_summary()
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())