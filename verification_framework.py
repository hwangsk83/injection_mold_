#!/usr/bin/env python3
"""
verification_framework.py - V&V Benchmark Verification Module
Runs 3 standard benchmark cases against Gold Standard data,
computes error percentages, and tracks history.
"""
import os, sys, json, math, csv
from pathlib import Path
import numpy as np

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
BENCH_DIR = WORKSPACE / "validation_test" / "benchmark_cases"
MAT_DB    = WORKSPACE / "material_db.json"
VV_HIST   = WORKSPACE / "vv_history.json"
SOLVER_CSV = WORKSPACE / "solver_monitor.csv"

BENCH_CASES = [
    "case_a_cube_shrinkage",
    "case_b_plate_fill",
    "case_c_cantilever_warpage",
]

def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _merge_db(raw):
    """Merge partitioned DB into flat {mfg: {grade: props}}."""
    merged = {}
    for pk in ["Commercial_UDB_DB", "Synthetic_AI_DB"]:
        part = raw.get(pk, {})
        for pmfg, pgrades in part.items():
            if pmfg not in merged:
                merged[pmfg] = {}
            for pgrade, pprops in pgrades.items():
                merged[pmfg][pgrade] = pprops
    return merged

def load_material_props(mfg_grade):
    raw = load_json(MAT_DB)
    if "Commercial_UDB_DB" in raw:
        db = _merge_db(raw)
    else:
        db = raw
    parts = mfg_grade.split(".", 1)
    if len(parts) != 2:
        return None
    mfg, grade = parts[0], parts[1]
    try:
        return db[mfg][grade]
    except KeyError:
        flat = {}
        for pmfg, pgrades in db.items():
            for pgrade, pprops in pgrades.items():
                flat[f"{pmfg}.{pgrade}"] = pprops
        return flat.get(mfg_grade)

def solve_case_a(gold, mat_props):
    L0 = gold.get("input", {}).get("cube_edge_mm", 10.0)
    Tmelt = gold.get("input", {}).get("melt_temp_K", 573.15)
    Teject = gold.get("input", {}).get("eject_temp_K", 353.15)
    tait = (mat_props or {}).get("Tait", {})
    b1m = tait.get("b1m", 0.0009)
    b2m = tait.get("b2m", 1.2e-6)
    b3m = tait.get("b3m", 1.3e8)
    b4m = tait.get("b4m", 0.0035)
    b5 = tait.get("b5", 413.15)
    C = tait.get("C_tait", 0.0894)
    P = gold.get("input", {}).get("ambient_pressure_Pa", 101325.0)

    def spec_vol(T):
        v0 = b1m + b2m * (T - b5) if T > b5 else b1m
        B = b3m * math.exp(-b4m * (T - b5)) if T > b5 else b3m
        return v0 * (1.0 - C * math.log(1.0 + P / max(B, 1.0)))

    v_melt = spec_vol(Tmelt)
    v_eject = spec_vol(Teject)
    sr = 1.0 - (v_eject / v_melt) ** (1.0 / 3.0)
    dL = L0 * sr
    return {"computed_dL_mm": round(dL,6), "computed_shrinkage_pct": round(sr*100,4), "computed_final_edge_mm": round(L0-dL,4)}

def solve_case_b(gold, mat_props):
    L = gold.get("input",{}).get("plate_length_mm",100)*1e-3
    h = gold.get("input",{}).get("plate_thickness_mm",2)*1e-3
    P_inj = gold.get("input",{}).get("injection_pressure_MPa",80)*1e6
    wlf = (mat_props or {}).get("CrossWLF",{})
    n_val = wlf.get("n",0.30)
    tau_star = wlf.get("tau_star",1.8e5)
    D1 = wlf.get("D1",2.4e13); D2 = wlf.get("D2",413.15)
    A1 = wlf.get("A1",31.2); A2 = wlf.get("A2",51.6)
    T = gold.get("input",{}).get("melt_temp_K",573.15)
    eta0 = D1 * math.exp(-A1*(T-D2)/(A2+T-D2))
    g_dot = P_inj*h/(2*eta0*L)
    eta_app = eta0 / (1+(eta0*g_dot/tau_star)**(1-n_val))
    t_fill = 12*eta_app*L**2/(h**2*P_inj)
    return {"computed_t_fill_s": round(t_fill,6)}

def solve_case_c(gold, mat_props):
    L = gold.get("input",{}).get("beam_length_mm",80)*1e-3
    h = gold.get("input",{}).get("beam_height_mm",4)*1e-3
    dT = gold.get("input",{}).get("delta_T_K",50)
    mech = (mat_props or {}).get("Mechanical",{})
    add = (mat_props or {}).get("Additives",{})
    cte_m = mech.get("CTE",6.5e-5)
    cte_f = add.get("filler_CTE",5e-6)
    vf = add.get("volume_fraction",0.112)
    cte = cte_m*(1-vf)+cte_f*vf
    delta = cte*dT*L**2/(2*h)
    curv = cte*dT/h
    return {"computed_delta_max_mm": round(delta*1e3,6), "computed_curvature_1_m": round(curv,6)}

def run_verification():
    print("="*62)
    print("  V&V Verification Framework - Running 3 Benchmark Cases")
    print("="*62)
    results = []; all_pass = True
    for case_id in BENCH_CASES:
        gp = BENCH_DIR/case_id/"gold_standard.json"
        if not gp.exists():
            print(f"  [{case_id}] SKIP - gold_standard not found"); continue
        gold = load_json(gp)
        mat_key = gold.get("input",{}).get("material_db_key","Generic.PC")
        mat_props = load_material_props(mat_key)
        cs = case_id.replace("case_","").replace("_"," ").title()
        print(f"\n  -- {cs} --")
        try:
            if "cube" in case_id: comp = solve_case_a(gold, mat_props)
            elif "plate" in case_id: comp = solve_case_b(gold, mat_props)
            elif "cantilever" in case_id: comp = solve_case_c(gold, mat_props)
            else: continue
        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({"case":case_id,"status":"ERROR","error":str(e)})
            all_pass = False; continue
        expected = gold.get("expected_output",{})
        tol = gold.get("tolerance",{})
        case_ok = True
        for key, exp_val in expected.items():
            ckey = key.replace("expected_", "computed_", 1)
            if ckey in comp:
                computed = comp[ckey]
                tkey = key.replace("expected_","",1)
                tolv = tol.get(tkey, 0.05*abs(exp_val) if exp_val!=0 else 0.05)
                abs_err = abs(computed-exp_val)
                rel_err = abs_err/max(abs(exp_val),1e-12)*100
                if tolv != 0:
                    thresh = tolv/max(abs(exp_val),1e-12)*100
                else:
                    thresh = 0.1
                passed = rel_err<=thresh or abs_err<=abs(tolv)
                status = "PASS" if passed else "FAIL"
                if not passed: all_pass=False; case_ok=False
                print(f"    {ckey}: {computed:.6f}, gold={exp_val:.6f}, err={rel_err:.3f}%, thresh={thresh:.3f}% -> {status}")
            else:
                print(f"    {ckey}: NOT COMPUTED")
        results.append({"case":case_id,"status":"PASS" if case_ok else "FAIL","computed":comp})

    n_pass = sum(1 for r in results if r["status"]=="PASS")
    n_total = len(results)
    verdict = "PASS" if all_pass and n_total>0 else "FAIL"
    print(f"\n  V&V Result: {n_pass}/{n_total} cases passed -> {verdict}")
    if not all_pass: print("\n  [V&V ALARM] Some cases exceeded 5% threshold!")
    entry = {"n_cases":n_total,"n_pass":n_pass,"verdict":verdict,"details":results}
    hist = {"runs":[entry],"latest_verdict":verdict}
    if VV_HIST.exists():
        try: hist = load_json(VV_HIST); hist.setdefault("runs",[]).append(entry); hist["latest_verdict"]=verdict
        except: pass
    with open(VV_HIST,"w",encoding="utf-8") as f: json.dump(hist,f,indent=4)
    return verdict, results

if __name__ == "__main__":
    v, r = run_verification()
    sys.exit(0 if v=="PASS" else 1)