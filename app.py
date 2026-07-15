# -*- coding: utf-8 -*-
"""simple-injection-mold-sim Pre-Processor -- Lightweight Router (9-Tab Modular)"""
import streamlit as st
from pathlib import Path
import json, os, sys, subprocess, re
import numpy as np, pandas as pd

st.set_page_config(page_title="simple-injection-mold-sim PRE", page_icon="🌊", layout="wide")

st.markdown("""<style>
html,body{font-family:'Outfit',sans-serif;background-color:#0f172a;color:#f1f5f9}
h1,h2,h3{background:linear-gradient(135deg,#38bdf8,#a855f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stButton>button{background:linear-gradient(135deg,#0284c7,#7c3aed)!important;color:white!important;border-radius:8px!important}
.glass-card{background:rgba(30,41,59,0.4);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.05);border-radius:16px;padding:24px;margin-bottom:20px}
</style>""", unsafe_allow_html=True)

WORKSPACE_ROOT = Path(r"D:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE_ROOT / "machine_spec.json"

st.title("🌊 simple-injection-mold-sim Pre-Processor & Solver")
st.caption("9-Tab Modular UI | core_utils integrated | Checks 1-71")

# Global session_state initialization (Race Condition Defense)
st.session_state.setdefault("preprocess_mesh_ok", False)
st.session_state.setdefault("preprocess_geo_ok", False)
st.session_state.setdefault("preprocess_gate_conf", {})
st.session_state.setdefault("mesh_generated", False)
st.session_state.setdefault("material_selected", False)
st.session_state.setdefault("process_window_ok", False)
st.session_state.setdefault("fem_converged", False)
st.session_state.setdefault("defects_analyzed", False)
st.session_state.setdefault("audit_passed", False)
st.session_state.setdefault("expert_tuning_done", False)
st.session_state.setdefault("report_generated", False)
st.session_state.setdefault("active_tab_index", 0)
st.session_state.setdefault("session_init_time", str(__import__("datetime").datetime.now()))

# --- Extended session_state for Input Form Binding (Phase A-I) ---
# Tab 01 - Pre-process: STL Upload & Machine Specs
st.session_state.setdefault("cavity_stl_paths", [])
st.session_state.setdefault("insert_stl_paths", [])
st.session_state.setdefault("clamping_force_ton", 250.0)
st.session_state.setdefault("screw_diameter_mm", 25.0)
st.session_state.setdefault("max_injection_pressure_mpa", 180.0)
st.session_state.setdefault("projected_area_m2", 0.01125)
st.session_state.setdefault("machine_spec_modified", False)
# Tab 02 - Mesh: Expert Manual Override
st.session_state.setdefault("expert_mesh_enabled", False)
st.session_state.setdefault("global_mesh_size_mm", 4.0)
st.session_state.setdefault("boundary_layer_count", 2)
st.session_state.setdefault("mesh_pin_points", [])
# Tab 03 - Material: Material Selector
st.session_state.setdefault("selected_material_name", "")
st.session_state.setdefault("material_properties", {})
st.session_state.setdefault("material_db_loaded", False)
# Tab 04 - Process: Expert Manual Override
st.session_state.setdefault("expert_process_enabled", False)
st.session_state.setdefault("stage_1_pressure_mpa", 100.0)
st.session_state.setdefault("stage_1_time_s", 1.5)
st.session_state.setdefault("stage_2_pressure_mpa", 80.0)
st.session_state.setdefault("stage_2_time_s", 3.0)
st.session_state.setdefault("stage_3_pressure_mpa", 40.0)
st.session_state.setdefault("stage_3_time_s", 2.0)
st.session_state.setdefault("melt_temp_k", 563.15)
st.session_state.setdefault("mold_temp_k", 373.15)
st.session_state.setdefault("injection_speed_mps", 0.25)
# Tab 05 - Structural: Fatigue, CZM, Homogenization
st.session_state.setdefault("fatigue_cycles", 100000)
st.session_state.setdefault("stress_ratio", 0.1)
st.session_state.setdefault("fracture_toughness_mpa_m05", 2.5)
st.session_state.setdefault("czm_gc", 1.0)
st.session_state.setdefault("czm_sigma_max", 50.0)
st.session_state.setdefault("homogenization_method", "Halpin-Tsai")
# Tab 08 - Expert: Solver Override
st.session_state.setdefault("expert_solver_enabled", False)
st.session_state.setdefault("relaxation_factor", 0.7)
st.session_state.setdefault("n_outer_correctors", 1)
st.session_state.setdefault("n_correctors", 2)
st.session_state.setdefault("n_non_orthogonal", 1)
st.session_state.setdefault("max_iter_solver", 1000)
st.session_state.setdefault("convergence_tolerance", 1e-6)
st.session_state.setdefault("fracture_coupling_coeff", 1.0)
st.session_state.setdefault("explicit_time_step_s", 0.0)

# ─── Extended Defaults: UI Overhaul v2.0 ──────────────────────────────
# Tab 01 Advanced: Machine layout
st.session_state.setdefault("n_cavities", 1)
st.session_state.setdefault("n_gates", 1)
st.session_state.setdefault("runner_diameter_mm", 6.0)
st.session_state.setdefault("sub_runner_diameter_mm", 4.0)
st.session_state.setdefault("gate_land_length_mm", 1.5)
st.session_state.setdefault("hot_runner_enabled", False)
st.session_state.setdefault("valve_gate_count", 0)
st.session_state.setdefault("valve_gate_timing_s", {})
st.session_state.setdefault("cavity_bbox_list", [])
st.session_state.setdefault("insert_bbox_list", [])
# Gate Pick Mode
st.session_state.setdefault("gate_pick_mode", "🤖 Auto-Wizard (자동 탐색)")
st.session_state.setdefault("manual_gate_coords", [])
# Tab 02 Advanced: Mesh quality
st.session_state.setdefault("mesh_quality_target", 0.7)
st.session_state.setdefault("mesh_max_skewness", 0.85)
# Tab 03 Advanced: Material
st.session_state.setdefault("selected_material_family", "")
st.session_state.setdefault("mat_melt_temp_k", 563.15)
# Tab 04 Advanced: Process
st.session_state.setdefault("vp_switchover_pos_mm", 10.0)
st.session_state.setdefault("cushion_mm", 5.0)
# Tab 05 Advanced: Structural fiber
st.session_state.setdefault("fiber_volume_fraction", 0.112)
st.session_state.setdefault("fiber_aspect_ratio", 25.0)
st.session_state.setdefault("fiber_modulus_mpa", 72000.0)
# Tab 06 Advanced: Quality thresholds
st.session_state.setdefault("sink_mark_threshold_mm", 0.05)
st.session_state.setdefault("weld_line_angle_deg", 135.0)
st.session_state.setdefault("shrinkage_limit_pct", 0.8)
# Tab 07 Advanced: V&V
st.session_state.setdefault("vv_convergence_tol", 1e-4)
st.session_state.setdefault("max_audit_checks", 71)
st.session_state.setdefault("benchmark_tolerance_pct", 5.0)
# Tab 08 Advanced: Solver
st.session_state.setdefault("mucell_gas_fraction", 0.05)
# Tab 09 Advanced: Postprocess
st.session_state.setdefault("vtk_decimate_factor", 0.7)
st.session_state.setdefault("vtk_visualization_field", "U")
st.session_state.setdefault("report_formats", ["PDF", "PPTX"])
st.session_state.setdefault("report_dpi", 150)

# Sidebar: Case Explorer
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
subfolders = [f.name for f in WORKSPACE_ROOT.iterdir() if f.is_dir()]
subfolders.sort()
selected_folder = st.sidebar.selectbox("📁 Case Directory:", options=subfolders)

if not selected_folder:
    st.sidebar.warning("No case folder.")
    st.stop()

case_dir = WORKSPACE_ROOT / selected_folder
st.sidebar.success(f"Active: `{selected_folder}`")

if st.sidebar.button("➕ Create Dummy Case"):
    from ui_components.common_imports import create_dummy_case
    create_dummy_case(WORKSPACE_ROOT / "dummy_mold_case")
    st.sidebar.success("Created!"); st.rerun()

# ─── Global Master Run Orchestrator ───
st.sidebar.divider()
st.sidebar.subheader("🚀 Master Run Orchestrator")

# Track active process in session state (Avoid orphaned processes)
st.session_state.setdefault("active_solver_process", None)

# Helper function to kill zombie solver processes on Windows
def kill_zombie_solvers():
    try:
        import subprocess
        for proc_name in ["titanFoam.exe", "blockMesh.exe", "decomposePar.exe", "mpiexec.exe"]:
            subprocess.run(["taskkill", "/F", "/IM", proc_name], capture_output=True)
    except Exception:
        pass

# 3-Button Interface (Run, Force Cancel, Reset)
run_btn = st.sidebar.button("⚡ RUN MASTER SIMULATION", use_container_width=True)

col_can, col_res = st.sidebar.columns(2)

with col_can:
    if st.button("⏹ FORCE CANCEL", use_container_width=True, help="현재 가동 중인 솔버 및 병렬 CPU 스레드 강제 중단"):
        proc = st.session_state.get("active_solver_process")
        if proc:
            try:
                proc.terminate()
                proc.kill()
            except Exception:
                pass
        kill_zombie_solvers()
        st.session_state["active_solver_process"] = None
        st.sidebar.success("⏹ 모든 사출 시뮬레이션 프로세스가 강제 중단되었습니다!")
        st.rerun()

with col_res:
    if st.button("🔄 RESET STATE", use_container_width=True, help="시뮬레이션 가동 이력 및 로컬 임시 결과 폴더 완전 초기화"):
        proc = st.session_state.get("active_solver_process")
        if proc:
            try:
                proc.terminate()
                proc.kill()
            except Exception:
                pass
        kill_zombie_solvers()
        st.session_state["active_solver_process"] = None
        
        # Reset Session Variables
        st.session_state["preprocess_mesh_ok"] = False
        st.session_state["preprocess_geo_ok"] = False
        st.session_state["preprocess_gate_conf"] = {}
        st.session_state["mesh_generated"] = False
        st.session_state["material_selected"] = False
        st.session_state["process_window_ok"] = False
        st.session_state["fem_converged"] = False
        st.session_state["defects_analyzed"] = False
        st.session_state["audit_passed"] = False
        st.session_state["expert_tuning_done"] = False
        st.session_state["report_generated"] = False
        
        # Clean background directories
        try:
            val_dir = WORKSPACE_ROOT / "validation_test"
            if val_dir.exists():
                import glob, shutil
                for pattern in ["processor*", "0.*", "[1-9]*"]:
                    for item in glob.glob(str(val_dir / pattern)):
                        if os.path.isdir(item):
                            shutil.rmtree(item, ignore_errors=True)
                for log in ["log.blockMesh", "log.decomposePar", "log.titanFoam", "log.reconstructPar"]:
                    lpath = val_dir / log
                    if lpath.exists():
                        os.remove(str(lpath))
        except Exception:
            pass
            
        st.sidebar.success("🔄 해석 제어 세션 및 로컬 잔여 파일이 리셋되었습니다!")
        st.rerun()

if run_btn:
    # 1. Integrity Check
    errors = []
    if not st.session_state.get("cavity_stl_paths"):
        errors.append("STL Cavity file is not selected (Tab 1).")
    if st.session_state.get("clamping_force_ton", 0) <= 0:
        errors.append("Clamping force must be greater than 0.")
    if st.session_state.get("screw_diameter_mm", 0) <= 0:
        errors.append("Screw diameter must be greater than 0.")
    if not st.session_state.get("selected_material_name"):
        errors.append("Material is not selected (Tab 3).")
        
    if errors:
        st.sidebar.error("❌ Integrity Checks Failed:")
        for err in errors:
            st.sidebar.write(f"- {err}")
    else:
        st.sidebar.info("✔ Integrity Checks Passed!")
        
        # 2. Serialize to machine_spec.json
        machine_spec_data = {
            "clamping_force_ton": float(st.session_state.get("clamping_force_ton", 250.0)),
            "screw_diameter_mm": float(st.session_state.get("screw_diameter_mm", 25.0)),
            "max_injection_pressure_mpa": float(st.session_state.get("max_injection_pressure_mpa", 180.0)),
            "projected_area_m2": float(st.session_state.get("projected_area_m2", 0.01125)),
            "n_cavities": int(st.session_state.get("n_cavities", 1)),
            "n_gates": int(st.session_state.get("n_gates", 1)),
            "runner_diameter_mm": float(st.session_state.get("runner_diameter_mm", 6.0)),
            "sub_runner_diameter_mm": float(st.session_state.get("sub_runner_diameter_mm", 4.0)),
            "gate_land_length_mm": float(st.session_state.get("gate_land_length_mm", 1.5)),
            "hot_runner_enabled": bool(st.session_state.get("hot_runner_enabled", False)),
            "valve_gate_count": int(st.session_state.get("valve_gate_count", 0)),
            "valve_gate_timing_s": st.session_state.get("valve_gate_timing_s", {}),
            "cavity_stl_paths": st.session_state.get("cavity_stl_paths", []),
            "insert_stl_paths": st.session_state.get("insert_stl_paths", []),
            "cavity_bbox_list": st.session_state.get("cavity_bbox_list", []),
            "insert_bbox_list": st.session_state.get("insert_bbox_list", []),
            "gate_pick_mode": st.session_state.get("gate_pick_mode", ""),
            "manual_gate_coords": st.session_state.get("manual_gate_coords", []),
            "postprocess": {
                "vtk_decimate_factor": float(st.session_state.get("vtk_decimate_factor", 0.7)),
                "vtk_visualization_field": st.session_state.get("vtk_visualization_field", "U"),
                "report_formats": st.session_state.get("report_formats", ["PDF", "PPTX"]),
                "report_dpi": int(st.session_state.get("report_dpi", 150)),
            }
        }
        
        # Write machine_spec.json
        try:
            SPEC_JSON.write_text(json.dumps(machine_spec_data, indent=4, ensure_ascii=False), encoding="utf-8")
            st.sidebar.success("💾 Sync: machine_spec.json updated!")
        except Exception as e:
            st.sidebar.error(f"Failed to update machine_spec.json: {e}")
            
        # 3. Serialize to manual_override.json
        manual_override_data = {
            "mesh": {
                "expert_mesh_enabled": bool(st.session_state.get("expert_mesh_enabled", False)),
                "global_mesh_size_mm": float(st.session_state.get("global_mesh_size_mm", 4.0)),
                "boundary_layer_count": int(st.session_state.get("boundary_layer_count", 2)),
                "mesh_pin_points": st.session_state.get("mesh_pin_points", []),
                "mesh_quality_target": float(st.session_state.get("mesh_quality_target", 0.7)),
                "mesh_max_skewness": float(st.session_state.get("mesh_max_skewness", 0.85)),
            },
            "material": {
                "selected_material_name": st.session_state.get("selected_material_name", ""),
                "selected_material_family": st.session_state.get("selected_material_family", ""),
                "mat_melt_temp_k": float(st.session_state.get("mat_melt_temp_k", 563.15)),
                "material_properties": st.session_state.get("material_properties", {}),
            },
            "process": {
                "expert_process_enabled": bool(st.session_state.get("expert_process_enabled", False)),
                "stage_1_pressure_mpa": float(st.session_state.get("stage_1_pressure_mpa", 100.0)),
                "stage_1_time_s": float(st.session_state.get("stage_1_time_s", 1.5)),
                "stage_2_pressure_mpa": float(st.session_state.get("stage_2_pressure_mpa", 80.0)),
                "stage_2_time_s": float(st.session_state.get("stage_2_time_s", 3.0)),
                "stage_3_pressure_mpa": float(st.session_state.get("stage_3_pressure_mpa", 40.0)),
                "stage_3_time_s": float(st.session_state.get("stage_3_time_s", 2.0)),
                "melt_temp_k": float(st.session_state.get("melt_temp_k", 563.15)),
                "mold_temp_k": float(st.session_state.get("mold_temp_k", 373.15)),
                "injection_speed_mps": float(st.session_state.get("injection_speed_mps", 0.25)),
                "vp_switchover_pos_mm": float(st.session_state.get("vp_switchover_pos_mm", 10.0)),
                "cushion_mm": float(st.session_state.get("cushion_mm", 5.0)),
            },
            "structural": {
                "fatigue_cycles": int(st.session_state.get("fatigue_cycles", 100000)),
                "stress_ratio": float(st.session_state.get("stress_ratio", 0.1)),
                "fracture_toughness_mpa_m05": float(st.session_state.get("fracture_toughness_mpa_m05", 2.5)),
                "czm_gc": float(st.session_state.get("czm_gc", 1.0)),
                "czm_sigma_max": float(st.session_state.get("czm_sigma_max", 50.0)),
                "homogenization_method": st.session_state.get("homogenization_method", "Halpin-Tsai"),
                "fiber_volume_fraction": float(st.session_state.get("fiber_volume_fraction", 0.112)),
                "fiber_aspect_ratio": float(st.session_state.get("fiber_aspect_ratio", 25.0)),
                "fiber_modulus_mpa": float(st.session_state.get("fiber_modulus_mpa", 72000.0)),
            },
            "expert_solver": {
                "expert_solver_enabled": bool(st.session_state.get("expert_solver_enabled", False)),
                "relaxation_factor": float(st.session_state.get("relaxation_factor", 0.7)),
                "n_outer_correctors": int(st.session_state.get("n_outer_correctors", 1)),
                "n_correctors": int(st.session_state.get("n_correctors", 2)),
                "n_non_orthogonal": int(st.session_state.get("n_non_orthogonal", 1)),
                "max_iter_solver": int(st.session_state.get("max_iter_solver", 1000)),
                "convergence_tolerance": float(st.session_state.get("convergence_tolerance", 1e-6)),
                "fracture_coupling_coeff": float(st.session_state.get("fracture_coupling_coeff", 1.0)),
                "explicit_time_step_s": float(st.session_state.get("explicit_time_step_s", 0.0)),
                "mucell_gas_fraction": float(st.session_state.get("mucell_gas_fraction", 0.05)),
            }
        }
        
        OVERRIDE_JSON = WORKSPACE_ROOT / "manual_override.json"
        try:
            OVERRIDE_JSON.write_text(json.dumps(manual_override_data, indent=4, ensure_ascii=False), encoding="utf-8")
            st.sidebar.success("💾 Sync: manual_override.json updated!")
        except Exception as e:
            st.sidebar.error(f"Failed to update manual_override.json: {e}")
            
        # 4. Launch Solver Process Background
        st.sidebar.info("🚀 Launching Titan Solver Engine...")
        
        try:
            # Execute python run_titan_final.py
            cmd = [sys.executable, str(WORKSPACE_ROOT / "run_titan_final.py")]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(WORKSPACE_ROOT))
            st.session_state["active_solver_process"] = process
            
            # Progress bar simulation / log parser
            progress_bar = st.sidebar.progress(0.0)
            status_text = st.sidebar.empty()
            
            filled_ratio = 0.0
            
            # Non-blocking log monitor (read output in real-time)
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                
                # Check line content to extract solver status
                if "blockMesh" in line:
                    status_text.text("🔨 Meshing blockMesh...")
                    progress_bar.progress(0.15)
                elif "decomposePar" in line:
                    status_text.text("🧩 Decomposing Domain...")
                    progress_bar.progress(0.35)
                elif "titanFoam" in line:
                    status_text.text("🔥 Running solver titanFoam...")
                    progress_bar.progress(0.55)
                elif "FilledRatio" in line:
                    match = re.search(r"FilledRatio = ([0-9.]+)", line)
                    if match:
                        filled_ratio = float(match.group(1))
                        # Scale progress from 0.60 to 0.95 depending on FilledRatio
                        solver_progress = 0.60 + (filled_ratio / 100.0) * 0.35
                        status_text.text(f"🌊 Solver Running: {filled_ratio}% Filled")
                        progress_bar.progress(min(solver_progress, 0.95))
                elif "VALIDATION PASSED" in line:
                    status_text.text("✅ Simulation Completed & Passed!")
                    progress_bar.progress(1.0)
            
            process.wait()
            st.session_state["active_solver_process"] = None
            if process.returncode == 0:
                st.sidebar.success("🎉 Simulation run successfully completed!")
                st.session_state["fem_converged"] = True
                st.session_state["defects_analyzed"] = True
            else:
                st.sidebar.error(f"❌ Simulation process failed with code {process.returncode}")
        except Exception as e:
            st.session_state["active_solver_process"] = None
            st.sidebar.error(f"Failed to start simulation process: {e}")

# 9 Tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "1. Pre-process", "2. Mesh", "3. Material", "4. Process",
    "5. Structural", "6. Quality", "7. V&V", "8. Expert", "9. Post-process"
])

from ui_components.tab_01_preprocess import render as r1
from ui_components.tab_02_mesh import render as r2
from ui_components.tab_03_material import render as r3
from ui_components.tab_04_process import render as r4
from ui_components.tab_05_structural import render as r5
from ui_components.tab_06_quality import render as r6
from ui_components.tab_07_vandv import render as r7
from ui_components.tab_08_expert import render as r8
from ui_components.tab_09_postprocess import render as r9

with tab1: r1(WORKSPACE_ROOT, SPEC_JSON, case_dir, st.session_state)
with tab2: r2(WORKSPACE_ROOT, SPEC_JSON, case_dir)
with tab3: r3(WORKSPACE_ROOT, SPEC_JSON)
with tab4: r4(WORKSPACE_ROOT, SPEC_JSON, case_dir)
with tab5: r5(WORKSPACE_ROOT, SPEC_JSON)
with tab6: r6(WORKSPACE_ROOT, SPEC_JSON)
with tab7: r7(WORKSPACE_ROOT, SPEC_JSON)
with tab8: r8(WORKSPACE_ROOT, SPEC_JSON)
with tab9: r9(WORKSPACE_ROOT, SPEC_JSON)

st.divider()
st.caption("simple-injection-mold-sim Pre-Processor | 9-Tab Modular v2.0 | Phase A-I Complete")