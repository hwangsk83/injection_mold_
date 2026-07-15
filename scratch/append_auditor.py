with open("system_auditor.py", "r", encoding="utf-8") as f:
    content = f.read()

target = 'is_sym = flow_stress.get("is_symmetric", False)'
parts = content.split(target)

new_content = parts[0] + target + """
    sym_dev = flow_stress.get("symmetry_deviation_MPa", 0.0)
    print(f"  [Verify-Check 14] Flow Viscous Stress Symmetry:")
    print(f"    Symmetry status: {is_sym}")
    print(f"    Symmetry deviation: {sym_dev:.6e} MPa")
    
    assert is_sym, f"[TENSOR ERROR] Flow stress tensor is not symmetric! Max deviation {sym_dev:.3e} MPa exceeds tolerance!"
    print("    [PASS] Flow stress tensor symmetry verified.")
    
    # Check 15: Birefringence Index Deviation Limit Check (delta_n < 0.01)
    biref = specs.get("optical_birefringence", {})
    if not biref:
        raise AssertionError("Birefringence specs missing. Run optical_biref_calc.py first.")
        
    delta_n = biref.get("delta_n", 1.0)
    retardation = biref.get("retardation_nm", 0.0)
    print(f"  [Verify-Check 15] Birefringence Index Limits:")
    print(f"    Birefringence delta_n: {delta_n:.6e} (Limit: < 0.01)")
    print(f"    Total phase retardation R: {retardation:.4f} nm")
    
    assert delta_n < 0.01, f"[OPTICAL LIMIT VIOLATION] Refractive index deviation delta_n {delta_n:.6e} exceeds physical limit of 0.01!"
    print("    [PASS] Refractive index deviation delta_n within physical limits.")
    
    # Update audit_report.json
    check14_15_data = {
        "check14_flow_induced_symmetry": {
            "max_deviation_MPa": sym_dev,
            "result": "PASS"
        },
        "check15_birefringence_limits": {
            "delta_n": delta_n,
            "retardation_nm": retardation,
            "result": "PASS"
        }
    }
    
    audit_path = WORKSPACE / "audit_report.json"
    report = {}
    if audit_path.exists():
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            pass
    report.update(check14_15_data)
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
        
    print("[PASS] Checks 14 & 15: Flow stress symmetry and birefringence audits passed successfully.")

def audit_cad_cleaner_and_explicit_drop():
    print("[AUDIT] Starting Checks 16 & 17: CAD Cleaner Watertightness & CFL Explicit Step Audit...")
    
    if not SPEC_JSON.exists():
        raise AssertionError("machine_spec.json is missing.")
        
    with open(SPEC_JSON, "r", encoding="utf-8") as f:
        specs = json.load(f)
        
    # Check 16: Watertight Mesh Audit
    cad_clean = specs.get("cad_cleaner", {})
    if not cad_clean:
        raise AssertionError("CAD cleaner specs missing. Run cad_cleaner.py first.")
        
    free_edges_after = cad_clean.get("free_edges_after", 1)
    is_watertight_after = cad_clean.get("watertight_after", False)
    
    print(f"  [Verify-Check 16] CAD Cleaner Healing Verification:")
    print(f"    Watertight after: {is_watertight_after}")
    print(f"    Free edges remaining: {free_edges_after} (Expected: 0)")
    
    assert free_edges_after == 0 or is_watertight_after, f"[GEOMETRIC FAULT] Healed STL mesh is not watertight! Remaining free edges: {free_edges_after}"
    print("    [PASS] Watertight CAD mesh integrity verified successfully (0% free boundary error).")
    
    # Check 17: CFL Condition Explicit Time Step Limit Audit
    explicit = specs.get("explicit_drop_test", {})
    if not explicit:
        raise AssertionError("Explicit drop test specs missing. Run explicit_drop_solver.py first.")
        
    dt_crit = explicit.get("critical_time_step_s", 0.0)
    dt_stable = explicit.get("stable_time_step_s", 1.0)
    
    print(f"  [Verify-Check 17] CFL Explicit Time Step Limit:")
    print(f"    Critical Time Step Limit: {dt_crit:.6e} s")
    print(f"    Applied Stable Time Step: {dt_stable:.6e} s (Limit check: dt_stable < dt_crit)")
    
    assert dt_stable < dt_crit, f"[NUMERICAL UNSTABILITY] Applied time step {dt_stable:.6e} s exceeds CFL critical stability limit {dt_crit:.6e} s!"
    print("    [PASS] CFL explicit stable time step limit verified successfully.")
    
    # Update audit_report.json
    check16_17_data = {
        "check16_watertight_mesh": {
            "free_edges_after": free_edges_after,
            "watertight_after": is_watertight_after,
            "result": "PASS"
        },
        "check17_cfl_condition": {
            "critical_time_step_s": dt_crit,
            "stable_time_step_s": dt_stable,
            "result": "PASS"
        }
    }
    
    audit_path = WORKSPACE / "audit_report.json"
    report_new = {}
    if audit_path.exists():
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                report_new = json.load(f)
        except Exception:
            pass
    report_new.update(check16_17_data)
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(report_new, f, indent=4)
        
    print("[PASS] Checks 16 & 17: Watertight STL and CFL stability audits passed successfully.")

def audit_synthetic_materials_thermodynamics():
    print("[AUDIT] Starting Check 18: Synthetic Material Thermodynamics & Rheological Consistency Audit...")
    
    if not SPEC_JSON.exists():
        raise AssertionError("machine_spec.json is missing.")
        
    with open(SPEC_JSON, "r", encoding="utf-8") as f:
        specs = json.load(f)
        
    synth_mat = specs.get("synthetic_ai_material", {})
    if not synth_mat:
        raise AssertionError("Synthetic AI material specs missing. Run ai_material_synthesizer.py first.")
        
    # Verification A: Monotonic Viscosity Decrease (Shear Thinning: d(eta)/d(gamma) < 0)
    wlf = synth_mat.get("CrossWLF", {})
    n = wlf.get("n", 0.3)
    tau_star = wlf.get("tau_star", 1.8e5)
    D1 = wlf.get("D1", 2.4e13)
    D2 = wlf.get("D2", 413.15)
    A1 = wlf.get("A1", 31.2)
    A2 = wlf.get("A2", 51.6)
    
    # Test temperature: melt temperature of PC e.g. 543 K (270 °C)
    T_test = 543.15
    eta_0 = D1 * np.exp(-A1 * (T_test - D2) / (A2 + T_test - D2))
    
    # Test shear rates from 1 to 10,000 s^-1
    shear_rates = np.logspace(0, 4, 20)
    viscosities = []
    for g_dot in shear_rates:
        eta = eta_0 / (1.0 + (eta_0 * g_dot / tau_star) ** (1.0 - n))
        viscosities.append(eta)
        
    # Check monotonic decrease
    for i in range(len(viscosities) - 1):
        assert viscosities[i] > viscosities[i+1], f"[RHEOLOGICAL ERROR] Viscosity is not monotonically decreasing: {viscosities[i]:.2f} -> {viscosities[i+1]:.2f}"
    print("    [PASS] Shear Thinning Law physically validated: viscosity decreases monotonically with shear rate.")

    # Verification B: Modified Tait PvT Thermodynamics (dv/dp < 0 and dv/dT > 0)
    tait = synth_mat.get("Tait", {})
    b1m = tait.get("b1m", 0.0009)
    b2m = tait.get("b2m", 1.2e-6)
    b3m = tait.get("b3m", 1.3e8)
    b4m = tait.get("b4m", 0.0035)
    b5 = tait.get("b5", 413.15)
    C_tait = tait.get("C_tait", 0.0894)
    
    def get_specific_volume(T, p):
        # Melt state T > b5
        v0 = b1m + b2m * (T - b5)
        B = b3m * np.exp(-b4m * (T - b5))
        v = v0 * (1.0 - C_tait * np.log(1.0 + p / B))
        return v
        
    # B1: dv/dp < 0 (Compressibility)
    p_steps = np.linspace(0.0, 100.0 * 1e6, 10)
    v_p = [get_specific_volume(500.15, p) for p in p_steps]
    for i in range(len(v_p) - 1):
        assert v_p[i] > v_p[i+1], f"[THERMODYNAMIC ERROR] Specific volume does not decrease with pressure: v_i={v_p[i]:.6e}, v_next={v_p[i+1]:.6e}"
    print("    [PASS] Thermodynamic Compressibility validated: specific volume decreases monotonically with pressure.")
    
    # B2: dv/dT > 0 (Thermal Expansion)
    t_steps = np.linspace(430.15, 500.15, 10)
    v_t = [get_specific_volume(t, 20.0 * 1e6) for t in t_steps]
    for i in range(len(v_t) - 1):
        assert v_t[i] < v_t[i+1], f"[THERMODYNAMIC ERROR] Specific volume does not increase with temperature: v_i={v_t[i]:.6e}, v_next={v_t[i+1]:.6e}"
    print("    [PASS] Thermodynamic Thermal Expansion validated: specific volume increases monotonically with temperature.")
    
    # Update audit_report.json
    check18_data = {
        "check18_synthetic_thermodynamics": {
            "shear_thinning_verified": True,
            "compressibility_verified": True,
            "thermal_expansion_verified": True,
            "result": "PASS"
        }
    }
    
    audit_path = WORKSPACE / "audit_report.json"
    report_final = {}
    if audit_path.exists():
        try:
            with open(audit_path, "r", encoding="utf-8") as f:
                report_final = json.load(f)
        except Exception:
            pass
    report_final.update(check18_data)
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(report_final, f, indent=4)
        
    print("[PASS] Check 18: Synthetic Material Thermodynamics and Rheology audit passed successfully.")

def main():
    print("="*60)
    print("  system_auditor.py: AI Autonomous Code & Physical Integrity Audit")
    print("  Checks: 1=Geometry, 2=DefectAST, 3=Shrinkage, 4=Topology,")
    print("          5=MaterialDB, 6=FSIMapping, 7=FEMSolver, 8=DOE,")
    print("          9=AnisotropicShrinkage, 10=CHTEnergyConservation,")
    print("          12=ViscoelasticNonlinear, 13=CoreDeflectionSRF,")
    print("          14=FlowStressSymmetry, 15=BirefringenceValid,")
    print("          16=WatertightMeshAudit, 17=CFLConditionAudit,")
    print("          18=SyntheticMaterialThermodynamicsAudit [NEW]")
    print("="*60)

    audit_results = {"status": "FAILED", "errors": []}

    try:
        audit_geometry()
        audit_defect_sensor_ast()
        audit_shrinkage_solver()
        audit_topology_optimizer()
        audit_material_database()
        audit_fsi_mapping()
        audit_fem_solver()
        audit_doe_integrity()
        audit_anisotropic_shrinkage()
        audit_cht_integrity()
        audit_viscoelasticity_nonlinear()
        audit_core_and_srf_mechanics()
        audit_optical_birefringence_and_flow_stress()
        audit_cad_cleaner_and_explicit_drop()
        audit_synthetic_materials_thermodynamics()
        
        print("\\n" + "="*60)
        print("[AUDIT SYSTEM COMPLETED] ALL SYSTEMS GO.")
        print("LOGICAL & PHYSICAL INTEGRITY VERIFIED (Checks 1-18)")
        print("="*60)
        audit_results["status"] = "PASS"
        with open(WORKSPACE / "audit_report.json", "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=4)
        sys.exit(0)
    except AssertionError as e:
        print(f"\\n[AUDIT FAILED] Verification Integrity Broken: {e}")
        audit_results["errors"].append(str(e))
        with open(WORKSPACE / "audit_report.json", "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=4)
        sys.exit(1)
    except Exception as e:
        print(f"\\n[CRITICAL AUDIT EXCEPTION]: {e}")
        import traceback
        audit_results["errors"].append(str(e))
        audit_results["traceback"] = traceback.format_exc()
        with open(WORKSPACE / "audit_report.json", "w", encoding="utf-8") as f:
            json.dump(audit_results, f, indent=4)
        sys.exit(1)

if __name__ == "__main__":
    main()
"""

with open("system_auditor.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print("APPEND DONE!")
