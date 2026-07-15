# -*- coding: utf-8 -*-
"""Tab 8: Expert -- Integrated Manual Override (Mesh/Process/Solver), TRIZ, IMD, GAIM, Cognitive Tuning"""
import streamlit as st
import json
import sys
import requests
from pathlib import Path
import pandas as pd
import numpy as np
from core_utils.subprocess_utils import run_module


def _run_with_feedback(module_name: str, success_msg: str = "Done"):
    """Run a backend module with spinner and error feedback."""
    with st.spinner(f"Running {module_name}..."):
        try:
            run_module(module_name, raise_on_error=True)
            st.success(success_msg)
        except Exception as e:
            st.error(f"{module_name} failed: {e}")


def _load_override_json(WORKSPACE_ROOT):
    """Load manual_override.json if exists"""
    override_path = WORKSPACE_ROOT / "manual_override.json"
    if override_path.exists():
        try:
            return json.loads(override_path.read_text())
        except Exception:
            pass
    return {}


def _save_override_json(WORKSPACE_ROOT, data):
    """Save to manual_override.json"""
    override_path = WORKSPACE_ROOT / "manual_override.json"
    override_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


# ==================================================================
# Mesh Override Sub-Renderer
# ==================================================================
def _render_mesh_override(WORKSPACE_ROOT, override_data):
    st.markdown("#### 🧱 Mesh Override Parameters")

    mesh = override_data.get("mesh", {})
    enabled = mesh.get("enabled", False)

    mesh_on = st.toggle("Enable Mesh Override", value=enabled, key="exp_toggle_mesh")
    if mesh_on != enabled:
        mesh["enabled"] = mesh_on
        override_data["mesh"] = mesh
        _save_override_json(WORKSPACE_ROOT, override_data)

    if mesh_on:
        col_em1, col_em2 = st.columns(2)
        with col_em1:
            new_gs = st.number_input(
                "Global Mesh Size (mm)", min_value=0.1, max_value=50.0,
                value=float(mesh.get("global_size_mm", 4.0)), step=0.1, format="%.2f",
                key="exp_mesh_global"
            )
            mesh["global_size_mm"] = new_gs
        with col_em2:
            new_bl = st.number_input(
                "Boundary Layer Count", min_value=0, max_value=10,
                value=int(mesh.get("boundary_layer_count", 2)), step=1,
                key="exp_mesh_bl"
            )
            mesh["boundary_layer_count"] = new_bl

        # Pin Points Editor
        pin_points = mesh.get("pin_points", [])
        df_pins = pd.DataFrame(pin_points) if pin_points else pd.DataFrame(columns=["x", "y", "z", "radius_mm", "local_size_mm"])
        edited_pins = st.data_editor(
            df_pins, num_rows="dynamic",
            column_config={
                "x": st.column_config.NumberColumn("X (m)", format="%.4f"),
                "y": st.column_config.NumberColumn("Y (m)", format="%.4f"),
                "z": st.column_config.NumberColumn("Z (m)", format="%.4f"),
                "radius_mm": st.column_config.NumberColumn("Radius (mm)", min_value=0.1, format="%.1f"),
                "local_size_mm": st.column_config.NumberColumn("Local Size (mm)", min_value=0.01, format="%.2f"),
            },
            key="exp_mesh_pins"
        )
        mesh["pin_points"] = edited_pins.dropna(how='all').to_dict(orient="records")

        override_data["mesh"] = mesh
        _save_override_json(WORKSPACE_ROOT, override_data)

        if st.button("📏 Run Expert Manual Mesher", key="exp_run_mesh"):
            _run_with_feedback("expert_manual_mesher.py", "Manual mesher executed.")


# ==================================================================
# Process Override Sub-Renderer
# ==================================================================
def _render_process_override(WORKSPACE_ROOT, override_data):
    st.markdown("#### ⚙ Process Override Parameters")

    proc = override_data.get("process", {})
    enabled = proc.get("enabled", False)

    proc_on = st.toggle("Enable Process Override", value=enabled, key="exp_toggle_proc")
    if proc_on != enabled:
        proc["enabled"] = proc_on
        override_data["process"] = proc
        _save_override_json(WORKSPACE_ROOT, override_data)

    if proc_on:
        st.markdown("**📦 Packing Profile (3-Stage)**")
        col_ep1, col_ep2, col_ep3 = st.columns(3)
        with col_ep1:
            proc["stage_1_pressure_mpa"] = st.number_input(
                "Stage 1 P (MPa)", min_value=0.0, max_value=300.0,
                value=float(proc.get("stage_1_pressure_mpa", 100.0)), step=5.0, format="%.1f",
                key="exp_stage1_p"
            )
            proc["stage_1_time_s"] = st.number_input(
                "Stage 1 T (s)", min_value=0.1, max_value=30.0,
                value=float(proc.get("stage_1_time_s", 1.5)), step=0.1, format="%.1f",
                key="exp_stage1_t"
            )
        with col_ep2:
            proc["stage_2_pressure_mpa"] = st.number_input(
                "Stage 2 P (MPa)", min_value=0.0, max_value=300.0,
                value=float(proc.get("stage_2_pressure_mpa", 80.0)), step=5.0, format="%.1f",
                key="exp_stage2_p"
            )
            proc["stage_2_time_s"] = st.number_input(
                "Stage 2 T (s)", min_value=0.1, max_value=30.0,
                value=float(proc.get("stage_2_time_s", 3.0)), step=0.1, format="%.1f",
                key="exp_stage2_t"
            )
        with col_ep3:
            proc["stage_3_pressure_mpa"] = st.number_input(
                "Stage 3 P (MPa)", min_value=0.0, max_value=300.0,
                value=float(proc.get("stage_3_pressure_mpa", 40.0)), step=5.0, format="%.1f",
                key="exp_stage3_p"
            )
            proc["stage_3_time_s"] = st.number_input(
                "Stage 3 T (s)", min_value=0.1, max_value=30.0,
                value=float(proc.get("stage_3_time_s", 2.0)), step=0.1, format="%.1f",
                key="exp_stage3_t"
            )

        col_et1, col_et2, col_et3 = st.columns(3)
        with col_et1:
            proc["melt_temp_k"] = st.number_input(
                "Melt Temp (K)", min_value=300.0, max_value=800.0,
                value=float(proc.get("melt_temp_k", 563.15)), step=5.0, format="%.1f",
                key="exp_melt_temp"
            )
            st.caption(f"≈ {proc['melt_temp_k'] - 273.15:.1f}°C")
        with col_et2:
            proc["mold_temp_k"] = st.number_input(
                "Mold Temp (K)", min_value=273.0, max_value=500.0,
                value=float(proc.get("mold_temp_k", 373.15)), step=5.0, format="%.1f",
                key="exp_mold_temp"
            )
            st.caption(f"≈ {proc['mold_temp_k'] - 273.15:.1f}°C")
        with col_et3:
            proc["injection_speed_mps"] = st.number_input(
                "Injection Speed (m/s)", min_value=0.01, max_value=2.0,
                value=float(proc.get("injection_speed_mps", 0.25)), step=0.01, format="%.2f",
                key="exp_inj_speed"
            )

        override_data["process"] = proc
        _save_override_json(WORKSPACE_ROOT, override_data)

        if st.button("⚙ Run Expert Process Editor", key="exp_run_proc"):
            _run_with_feedback("expert_process_editor.py", "Process editor executed.")


# ==================================================================
# Solver Override Sub-Renderer
# ==================================================================
def _render_solver_override(WORKSPACE_ROOT, override_data):
    st.markdown("#### 🔬 Solver Settings Override")

    sol = override_data.get("solver", {})
    enabled = sol.get("enabled", False)

    sol_on = st.toggle("Enable Solver Override", value=enabled, key="exp_toggle_sol")
    if sol_on != enabled:
        sol["enabled"] = sol_on
        override_data["solver"] = sol
        _save_override_json(WORKSPACE_ROOT, override_data)

    if sol_on:
        col_es1, col_es2, col_es3 = st.columns(3)
        with col_es1:
            sol["relaxation_factor"] = st.number_input(
                "Relaxation Factor", min_value=0.1, max_value=0.99,
                value=float(sol.get("relaxation_factor", 0.7)), step=0.05, format="%.2f",
                key="exp_relax"
            )
            sol["n_outer_correctors"] = st.number_input(
                "N Outer Correctors", min_value=1, max_value=10,
                value=int(sol.get("n_outer_correctors", 1)), step=1,
                key="exp_n_outer"
            )
            sol["n_correctors"] = st.number_input(
                "N Correctors", min_value=1, max_value=10,
                value=int(sol.get("n_correctors", 2)), step=1,
                key="exp_n_corr"
            )
        with col_es2:
            sol["n_non_orthogonal"] = st.number_input(
                "N Non-Orthogonal", min_value=0, max_value=5,
                value=int(sol.get("n_non_orthogonal", 1)), step=1,
                key="exp_n_nonorth"
            )
            sol["max_iter"] = st.number_input(
                "Max Iterations", min_value=100, max_value=50000,
                value=int(sol.get("max_iter", 1000)), step=500,
                key="exp_max_iter"
            )
            sol["convergence_tolerance"] = st.number_input(
                "Convergence Tolerance", min_value=1e-12, max_value=1e-2,
                value=float(sol.get("convergence_tolerance", 1e-6)),
                step=1e-6, format="%.1e",
                key="exp_conv_tol"
            )
        with col_es3:
            sol["fracture_coupling_coeff"] = st.number_input(
                "Fracture Coupling Coeff", min_value=0.1, max_value=2.0,
                value=float(sol.get("fracture_coupling_coeff", 1.0)), step=0.1, format="%.2f",
                key="exp_frac_coeff"
            )
            sol["explicit_time_step_s"] = st.number_input(
                "Explicit Time Step (s)", min_value=0.0, max_value=0.1,
                value=float(sol.get("explicit_time_step_s", 0.0)),
                step=1e-5, format="%.6f",
                help="0 = auto time step",
                key="exp_time_step"
            )

        override_data["solver"] = sol
        _save_override_json(WORKSPACE_ROOT, override_data)

        if st.button("⚙ Run Expert Solver Settings", key="exp_run_sol"):
            _run_with_feedback("expert_solver_settings.py", "Solver settings applied.")


# ==================================================================
# Main Render Function
# ==================================================================
def render(WORKSPACE_ROOT, SPEC_JSON):
    # Session State 초기화
    st.session_state.setdefault("expert_solver_enabled", False)

    # Load existing override data
    override_data = _load_override_json(WORKSPACE_ROOT)

    # ==================================================================
    # Section A: Integrated Manual Override Dashboard (3-in-1)
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("8-A. 🛠 Integrated Expert Manual Override Dashboard")
    st.caption("Mesh, Process, Solver — 통합 수동 제어 (manual_override.json)")

    tab_mesh, tab_proc, tab_sol = st.tabs(["🧱 Mesh Override", "⚙ Process Override", "🔬 Solver Override"])

    with tab_mesh:
        _render_mesh_override(WORKSPACE_ROOT, override_data)
    with tab_proc:
        _render_process_override(WORKSPACE_ROOT, override_data)
    with tab_sol:
        _render_solver_override(WORKSPACE_ROOT, override_data)

    # Global clear all overrides
    st.markdown("---")
    col_gc1, col_gc2 = st.columns(2)
    with col_gc1:
        if st.button("🔄 Clear ALL Overrides", key="clear_all_overrides"):
            override_data = {}
            _save_override_json(WORKSPACE_ROOT, override_data)
            st.success("All manual overrides cleared. Auto-Wizard mode restored.")
            st.rerun()
    with col_gc2:
        override_path = WORKSPACE_ROOT / "manual_override.json"
        if override_path.exists():
            with st.expander("📋 View manual_override.json", expanded=False):
                st.json(override_data)
        else:
            st.info("No manual_override.json yet. Enable toggles above to create.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section B: Original Advanced Molding Tools
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("8-B. Advanced Molding & Process Tools")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Process & Film**")
        if st.button("🎬 IMD Film FSI", key="imd"):
            _run_with_feedback("imd_film_fsi_solver.py", "IMD film FSI solved.")

    with col2:
        st.markdown("**Multiphase & Optimization**")
        if st.button("💨 GAIM N2 Coring", key="gaim"):
            _run_with_feedback("gaim_multiphase_solver.py", "GAIM multiphase solved.")
        if st.button("🧠 TRIZ Optimizer", key="triz"):
            _run_with_feedback("triz_process_optimizer.py", "TRIZ optimization done.")

    with col3:
        st.markdown("**Shear & Learning**")
        if st.button("⚖ Shear Imbalance Opt", key="sio"):
            _run_with_feedback("shear_imbalance_optimizer.py", "Shear imbalance optimized.")
        if st.button("🤖 RL SVG Optimizer", key="rl"):
            _run_with_feedback("rl_svg_optimizer.py", "RL SVG optimization done.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section C: Cognitive Self-Learning & MSA Solver Dashboard
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 🤖 Cognitive Self-Learning & Non-blocking MSA Solver")
    st.caption("Active Optimization Framework | Zero-blocking Queue | Gaussian Process Bayesian Optimization")

    tab_msa, tab_cognitive = st.tabs(["⚡ MSA Async Queue", "🧠 Bayesian Self-Tuning"])

    with tab_msa:
        st.markdown("#### FastAPI Gateway & Celery Solver Queue")
        st.write("Submit high-fidelity tasks to the background microservice queue and monitor progress in real-time.")

        col_ctrl, col_mon = st.columns(2)
        with col_ctrl:
            case_name = st.text_input("Active Case Name", value="Case_A_Production", key="exp_case_name")
            if st.button("Submit Asynchronous Solver Job", key="submit_job_async"):
                try:
                    with st.spinner("Submitting job to API gateway..."):
                        response = requests.post(
                            "http://127.0.0.1:8000/api/v1/solve",
                            json={"case_name": case_name, "parameters": {}},
                            timeout=5.0
                        )
                    if response.status_code == 200:
                        data = response.json()
                        st.session_state["async_task_id"] = data["task_id"]
                        st.success(f"Task submitted successfully! ID: {data['task_id']}")
                    else:
                        st.error(f"Gateway Error: {response.text}")
                except Exception as e:
                    st.warning("Gateway offline. Running mock async workflow.")
                    st.session_state["async_task_id"] = "mock-uuid-1234-5678"
                    st.session_state["mock_progress"] = 0

        with col_mon:
            task_id = st.session_state.get("async_task_id", None)
            if task_id:
                st.info(f"Monitoring Task: `{task_id}`")
                if task_id == "mock-uuid-1234-5678":
                    prog = st.session_state.get("mock_progress", 0)
                    if prog < 100:
                        prog += 20
                        st.session_state["mock_progress"] = prog
                    st.progress(prog / 100.0)
                    st.caption(f"Progress: {prog}% | Status: RUNNING (Mock)")
                    if prog >= 100:
                        st.success("Mock Solver Completed Successfully!")
                else:
                    try:
                        resp = requests.get(f"http://127.0.0.1:8000/api/v1/status/{task_id}", timeout=3.0)
                        if resp.status_code == 200:
                            status_data = resp.json()
                            progress = status_data.get("progress", 0)
                            status = status_data.get("status", "PENDING")
                            st.progress(progress / 100.0)
                            st.caption(f"Progress: {progress}% | Status: **{status}**")
                            if status == "SUCCESS":
                                st.success("Task completed successfully!")
                                st.json(status_data.get("result", {}))
                            elif status == "FAILED":
                                st.error("Task failed.")
                                st.write(status_data.get("logs", []))
                        else:
                            st.error("Failed to query task status.")
                    except Exception as e:
                        st.warning(f"Could not reach API gateway: {e}")

    with tab_cognitive:
        st.markdown("#### Gaussian Process Bayesian Parameter Optimization")
        learning_approved = st.toggle(
            "Approve Autonomous Parameter Updates",
            value=True,
            help="When enabled, self-tuned optimal physical properties are automatically written to calibration_constants.json.",
            key="toggle_learning_approved"
        )

        if st.button("Trigger Self-Learning & Tuning Loop", key="trigger_tuning"):
            with st.spinner("Running Bayesian optimization (Gaussian Process + Expected Improvement)..."):
                try:
                    from cognitive_tuning_engine import run_bayesian_optimization
                    tuning_results = run_bayesian_optimization(max_iter=8, approval_callback=learning_approved)
                    st.session_state["tuning_results"] = tuning_results
                    st.session_state["expert_tuning_done"] = True
                    st.success(f"Tuning loop finished! Best error rate achieved: {tuning_results['best_error_pct']:.4f}%")
                except Exception as e:
                    st.error(f"Tuning Engine Error: {e}")

        tr = st.session_state.get("tuning_results", None)
        if tr:
            col_graph1, col_graph2 = st.columns(2)
            with col_graph1:
                st.markdown("**V&V Optimization Trajectory**")
                df_traj = pd.DataFrame({
                    "Iteration": range(1, len(tr["trajectory"]) + 1),
                    "Mean Squared Error (%)": [x * 100 for x in tr["trajectory"]]
                }).set_index("Iteration")
                st.line_chart(df_traj)

            with col_graph2:
                st.markdown("**Parameter Convergence History**")
                df_params = pd.DataFrame(
                    tr["param_history"],
                    columns=["Thermal Resistance (Rc)", "Fracture Toughness (Gc)", "Friction Coefficient (mu)"]
                )
                st.line_chart(df_params)

            st.markdown("##### Calibrated Optimal Parameters")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                st.metric("Thermal Resistance (Rc)", f"{tr['best_params']['Rc']:.4f}",
                          delta=f"{tr['best_params']['Rc'] - 1.0:.4f}")
            with col_p2:
                st.metric("Fracture Toughness (Gc)", f"{tr['best_params']['Gc']:.4f}",
                          delta=f"{tr['best_params']['Gc'] - 1.0:.4f}")
            with col_p3:
                st.metric("Friction Coefficient (mu)", f"{tr['best_params']['mu']:.4f}",
                          delta=f"{tr['best_params']['mu'] - 1.0:.4f}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section D: Advanced Options Toggle (솔버 핵심 파라미터 직접 노출)
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 솔버 이터레이션 & 수렴 오차 직접 제어", expanded=False):
        override_data_adv = _load_override_json(WORKSPACE_ROOT)
        sol = override_data_adv.get("solver", {})

        st.markdown("##### 🔬 핵심 솔버 파라미터 (Core Solver Parameters)")
        st.caption("모든 값은 manual_override.json에 즉시 저장되며, 다음 솔버 실행 시 적용됩니다.")

        col_s1, col_s2, col_s3 = st.columns(3)

        with col_s1:
            max_iter_adv = st.number_input(
                "🔢 솔버 맥스 이터레이션 (Max Iterations)",
                min_value=100, max_value=100000,
                value=int(sol.get("max_iter", st.session_state.get("max_iter_solver", 1000))),
                step=500,
                help="솔버 최대 반복 횟수. 물리적 불안정시 10,000 이상으로 증가.",
                key="adv_expert_max_iter",
            )
            st.session_state["max_iter_solver"] = max_iter_adv

        with col_s2:
            conv_tol_adv = st.number_input(
                "🎯 수렴 허용오차 (Convergence Tolerance)",
                min_value=1e-12, max_value=1e-2,
                value=float(sol.get("convergence_tolerance", st.session_state.get("convergence_tolerance", 1e-6))),
                step=1e-7, format="%.2e",
                help="람스 잔차 수렴 임계값. 더 작을수록 정밀하지만 해석 시간 증가.",
                key="adv_expert_conv_tol",
            )
            st.session_state["convergence_tolerance"] = conv_tol_adv

        with col_s3:
            relax_adv = st.number_input(
                "📉 완화 인수 (Relaxation Factor)",
                min_value=0.05, max_value=0.99,
                value=float(sol.get("relaxation_factor", st.session_state.get("relaxation_factor", 0.7))),
                step=0.05, format="%.2f",
                help="앞으로의 수렴 속도 제어. 0.5~0.8 일반. 너무 크면 다발산.",
                key="adv_expert_relax",
            )
            st.session_state["relaxation_factor"] = relax_adv

        st.markdown("---")
        st.markdown("##### 🧩 특수 맞가 설정 (Specialized Solver Controls)")
        col_ss1, col_ss2 = st.columns(2)

        with col_ss1:
            mucell_gas = st.slider(
                "🧪 MuCell 가스 체적분율 (N2 Fraction)",
                min_value=0.0, max_value=0.3,
                value=float(st.session_state.get("mucell_gas_fraction", 0.05)),
                step=0.005,
                help="MuCell 폴리머 발포 성형 시 N2 가스 체적분율 (0~30%)",
                key="adv_mucell_gas",
            )
            st.session_state["mucell_gas_fraction"] = mucell_gas

        with col_ss2:
            explicit_dt = st.number_input(
                "⏱ 명시적 시간 스텝 Δt (s) [0=auto]",
                min_value=0.0, max_value=0.01,
                value=float(sol.get("explicit_time_step_s", st.session_state.get("explicit_time_step_s", 0.0))),
                step=1e-5, format="%.6f",
                help="0 = CFL 조건 자동 결정. 매우 작은 값으로 시작 권장.",
                key="adv_expert_explicit_dt",
            )
            st.session_state["explicit_time_step_s"] = explicit_dt

        if st.button("💾 솔버 Advanced Options 즉시 저장 → manual_override.json", key="save_adv_expert_solver"):
            override_data_adv.setdefault("solver", {})
            override_data_adv["solver"]["max_iter"] = max_iter_adv
            override_data_adv["solver"]["convergence_tolerance"] = conv_tol_adv
            override_data_adv["solver"]["relaxation_factor"] = relax_adv
            override_data_adv["solver"]["mucell_gas_fraction"] = mucell_gas
            override_data_adv["solver"]["explicit_time_step_s"] = explicit_dt
            override_data_adv["solver"]["enabled"] = True
            _save_override_json(WORKSPACE_ROOT, override_data_adv)
            st.success("✅ 솔버 Advanced Options → manual_override.json 저장 완료")

    # ==================================================================
    # Section E: CPU & Parallel Core Settings (NEW)
    # ==================================================================
    with st.expander("🖥️ CPU & 병렬 연산 코어 제어 (CPU Core Allocation)", expanded=False):
        import os
        logical_cores = os.cpu_count() or 1
        physical_cores = logical_cores // 2 if logical_cores >= 4 else logical_cores
        try:
            import psutil
            phys = psutil.cpu_count(logical=False)
            if phys and phys > 0:
                physical_cores = phys
        except Exception:
            pass

        st.markdown("##### 🧩 병렬 분할 연산 CPU 설정")
        st.caption(f"시스템 감지 정보: 물리 코어 **{physical_cores}개** | 논리 스레드 **{logical_cores}개**")

        # Load from machine_spec.json
        spec_path = Path(WORKSPACE_ROOT) / "machine_spec.json"
        saved_cores = 4
        if spec_path.exists():
            try:
                _spec = json.loads(spec_path.read_text(encoding="utf-8"))
                saved_cores = int(_spec.get("postprocess", {}).get("cpu_cores", max(1, int(physical_cores * 0.8))))
            except Exception:
                pass

        selected_cores = st.slider(
            "⚡ 사출 해석용 사용 CPU 코어 수 (Cores)",
            min_value=1,
            max_value=logical_cores,
            value=min(saved_cores, logical_cores),
            step=1,
            help="병렬 연산에 투입할 코어 수를 지정합니다. 안정적인 윈도우 사용을 위해 물리 코어 수 이하로 할당을 권장합니다."
        )

        if st.button("💾 CPU 코어 설정 영구 저장 & 격자 분할 반영", key="save_cpu_cores"):
            try:
                # 1. Save to machine_spec.json
                existing = {}
                if spec_path.exists():
                    try:
                        existing = json.loads(spec_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                existing.setdefault("postprocess", {})
                existing["postprocess"]["cpu_cores"] = selected_cores
                spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")

                # 2. Update decomposeParDict dynamically
                from dynamic_cpu_allocator import factorize_n, apply_decompose_par_dict
                nx, ny, nz = factorize_n(selected_cores)
                case_dir = Path(WORKSPACE_ROOT) / "validation_test"
                apply_decompose_par_dict(case_dir, selected_cores, nx, ny, nz)

                st.success(f"✅ CPU 코어가 {selected_cores}개로 영구 할당되고 격자 분할 설정({nx}x{ny}x{nz})이 완료되었습니다!")
                st.toast(f"💾 CPU Cores: {selected_cores} Cores Saved", icon="⚡")
            except Exception as e:
                st.error(f"CPU 설정 저장 실패: {e}")