# -*- coding: utf-8 -*-
"""Tab 4: Process -- Auto-Wizard / Expert Manual Override, Molding Window, DOE, Packing Profile"""
import streamlit as st
import json
from pathlib import Path
from core_utils.subprocess_utils import run_module


def _sync_process_override(WORKSPACE_ROOT, session_state):
    """Serialize process override params -> manual_override.json"""
    override_path = WORKSPACE_ROOT / "manual_override.json"
    data = {}
    if override_path.exists():
        try:
            data = json.loads(override_path.read_text())
        except Exception:
            pass

    data["process"] = {
        "enabled": session_state.get("expert_process_enabled", False),
        "stage_1_pressure_mpa": session_state.get("stage_1_pressure_mpa", 100.0),
        "stage_1_time_s": session_state.get("stage_1_time_s", 1.5),
        "stage_2_pressure_mpa": session_state.get("stage_2_pressure_mpa", 80.0),
        "stage_2_time_s": session_state.get("stage_2_time_s", 3.0),
        "stage_3_pressure_mpa": session_state.get("stage_3_pressure_mpa", 40.0),
        "stage_3_time_s": session_state.get("stage_3_time_s", 2.0),
        "melt_temp_k": session_state.get("melt_temp_k", 563.15),
        "mold_temp_k": session_state.get("mold_temp_k", 373.15),
        "injection_speed_mps": session_state.get("injection_speed_mps", 0.25),
        "valve_gate_timing_s": session_state.get("valve_gate_timing_s", {}),
    }
    override_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def _load_process_override(WORKSPACE_ROOT, session_state):
    """Load process override from manual_override.json into session_state"""
    override_path = WORKSPACE_ROOT / "manual_override.json"
    if override_path.exists():
        try:
            data = json.loads(override_path.read_text())
            proc = data.get("process", {})
            session_state["expert_process_enabled"] = proc.get("enabled", False)
            session_state["stage_1_pressure_mpa"] = proc.get("stage_1_pressure_mpa", 100.0)
            session_state["stage_1_time_s"] = proc.get("stage_1_time_s", 1.5)
            session_state["stage_2_pressure_mpa"] = proc.get("stage_2_pressure_mpa", 80.0)
            session_state["stage_2_time_s"] = proc.get("stage_2_time_s", 3.0)
            session_state["stage_3_pressure_mpa"] = proc.get("stage_3_pressure_mpa", 40.0)
            session_state["stage_3_time_s"] = proc.get("stage_3_time_s", 2.0)
            session_state["melt_temp_k"] = proc.get("melt_temp_k", 563.15)
            session_state["mold_temp_k"] = proc.get("mold_temp_k", 373.15)
            session_state["injection_speed_mps"] = proc.get("injection_speed_mps", 0.25)
            session_state["valve_gate_timing_s"] = proc.get("valve_gate_timing_s", {})
        except Exception:
            pass


def _run_with_feedback(module_name: str, success_msg: str = "Done"):
    """Run a backend module with spinner and error feedback (non-blocking UI)."""
    with st.spinner(f"Running {module_name}..."):
        try:
            run_module(module_name, raise_on_error=True)
            st.success(success_msg)
        except Exception as e:
            st.error(f"{module_name} failed: {e}")


def render(WORKSPACE_ROOT, SPEC_JSON, case_dir):
    # Session State 초기화
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
    st.session_state.setdefault("valve_gate_timing_s", {})

    # Load existing overrides
    _load_process_override(WORKSPACE_ROOT, st.session_state)

    # ==================================================================
    # Section A: Auto-Wizard vs Expert Mode Toggle
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("4-A. Process Mode: Auto-Wizard / Expert Manual Override")

    col_toggle, col_info = st.columns([1, 3])
    with col_toggle:
        expert_on = st.toggle(
            "🔧 Expert Manual Override",
            value=st.session_state.get("expert_process_enabled", False),
            key="toggle_expert_process",
            help="ON: 보압 프로파일, 온도, 사출 속도를 수동으로 직접 설정합니다. OFF: Auto-Wizard (DOE Optimizer)가 자동으로 최적 공정을 찾습니다."
        )
        if expert_on != st.session_state.get("expert_process_enabled"):
            st.session_state["expert_process_enabled"] = expert_on
            _sync_process_override(WORKSPACE_ROOT, st.session_state)

    with col_info:
        if st.session_state.get("expert_process_enabled"):
            st.info("🔧 **Expert Mode Active**: 수동 공정 파라미터가 적용됩니다. 아래에서 Packing Profile과 온도를 직접 입력하세요.")
        else:
            st.info("🤖 **Auto-Wizard Mode**: DOE Optimizer가 자동으로 Molding Window를 탐색하고 최적 공정 조건을 계산합니다.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section B: Expert Manual Process Parameters (visible when toggle ON)
    # ==================================================================
    if st.session_state.get("expert_process_enabled"):
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("4-B. Expert Process Parameters")

        # --- Packing Profile (3-Stage) ---
        st.markdown("#### 📦 Multi-Stage Packing Profile")

        col_p1, col_p2, col_p3 = st.columns(3)

        with col_p1:
            st.markdown("**Stage 1**")
            new_p1 = st.number_input(
                "Pressure (MPa)",
                min_value=0.0, max_value=300.0,
                value=float(st.session_state.get("stage_1_pressure_mpa", 100.0)),
                step=5.0, format="%.1f",
                key="input_stage1_pressure"
            )
            new_t1 = st.number_input(
                "Time (sec)",
                min_value=0.1, max_value=30.0,
                value=float(st.session_state.get("stage_1_time_s", 1.5)),
                step=0.1, format="%.1f",
                key="input_stage1_time"
            )
            if new_p1 != st.session_state.get("stage_1_pressure_mpa") or new_t1 != st.session_state.get("stage_1_time_s"):
                st.session_state["stage_1_pressure_mpa"] = new_p1
                st.session_state["stage_1_time_s"] = new_t1
                _sync_process_override(WORKSPACE_ROOT, st.session_state)

        with col_p2:
            st.markdown("**Stage 2**")
            new_p2 = st.number_input(
                "Pressure (MPa)",
                min_value=0.0, max_value=300.0,
                value=float(st.session_state.get("stage_2_pressure_mpa", 80.0)),
                step=5.0, format="%.1f",
                key="input_stage2_pressure"
            )
            new_t2 = st.number_input(
                "Time (sec)",
                min_value=0.1, max_value=30.0,
                value=float(st.session_state.get("stage_2_time_s", 3.0)),
                step=0.1, format="%.1f",
                key="input_stage2_time"
            )
            if new_p2 != st.session_state.get("stage_2_pressure_mpa") or new_t2 != st.session_state.get("stage_2_time_s"):
                st.session_state["stage_2_pressure_mpa"] = new_p2
                st.session_state["stage_2_time_s"] = new_t2
                _sync_process_override(WORKSPACE_ROOT, st.session_state)

        with col_p3:
            st.markdown("**Stage 3**")
            new_p3 = st.number_input(
                "Pressure (MPa)",
                min_value=0.0, max_value=300.0,
                value=float(st.session_state.get("stage_3_pressure_mpa", 40.0)),
                step=5.0, format="%.1f",
                key="input_stage3_pressure"
            )
            new_t3 = st.number_input(
                "Time (sec)",
                min_value=0.1, max_value=30.0,
                value=float(st.session_state.get("stage_3_time_s", 2.0)),
                step=0.1, format="%.1f",
                key="input_stage3_time"
            )
            if new_p3 != st.session_state.get("stage_3_pressure_mpa") or new_t3 != st.session_state.get("stage_3_time_s"):
                st.session_state["stage_3_pressure_mpa"] = new_p3
                st.session_state["stage_3_time_s"] = new_t3
                _sync_process_override(WORKSPACE_ROOT, st.session_state)

        # Packing profile visualization
        st.markdown("**📈 Packing Pressure Profile Preview**")
        import pandas as pd
        times = [0.0,
                 st.session_state.get("stage_1_time_s", 1.5),
                 st.session_state.get("stage_1_time_s", 1.5) + st.session_state.get("stage_2_time_s", 3.0),
                 st.session_state.get("stage_1_time_s", 1.5) + st.session_state.get("stage_2_time_s", 3.0) + st.session_state.get("stage_3_time_s", 2.0)]
        pressures = [st.session_state.get("stage_1_pressure_mpa", 100.0),
                     st.session_state.get("stage_1_pressure_mpa", 100.0),
                     st.session_state.get("stage_2_pressure_mpa", 80.0),
                     st.session_state.get("stage_3_pressure_mpa", 40.0)]
        df_pp = pd.DataFrame({"Time (s)": times, "Pressure (MPa)": pressures}).set_index("Time (s)")
        st.line_chart(df_pp)

        # --- Temperature & Speed ---
        st.markdown("---")
        st.markdown("#### 🌡 Melt & Mold Temperature")

        col_t1, col_t2, col_t3 = st.columns(3)

        with col_t1:
            new_melt = st.number_input(
                "🔥 Melt Temperature (K)",
                min_value=300.0, max_value=800.0,
                value=float(st.session_state.get("melt_temp_k", 563.15)),
                step=5.0, format="%.1f",
                help="용융 수지 온도 (Kelvin). ABS: ~510-530K, PC: ~560-580K",
                key="input_melt_temp"
            )
            if new_melt != st.session_state.get("melt_temp_k"):
                st.session_state["melt_temp_k"] = new_melt
                _sync_process_override(WORKSPACE_ROOT, st.session_state)
            st.caption(f"≈ {new_melt - 273.15:.1f} °C")

        with col_t2:
            new_mold = st.number_input(
                "🧊 Mold Temperature (K)",
                min_value=273.0, max_value=500.0,
                value=float(st.session_state.get("mold_temp_k", 373.15)),
                step=5.0, format="%.1f",
                help="금형 온도 (Kelvin). 일반적으로 323-393K (50-120°C)",
                key="input_mold_temp"
            )
            if new_mold != st.session_state.get("mold_temp_k"):
                st.session_state["mold_temp_k"] = new_mold
                _sync_process_override(WORKSPACE_ROOT, st.session_state)
            st.caption(f"≈ {new_mold - 273.15:.1f} °C")

        with col_t3:
            new_speed = st.number_input(
                "🚀 Injection Speed (m/s)",
                min_value=0.01, max_value=2.0,
                value=float(st.session_state.get("injection_speed_mps", 0.25)),
                step=0.01, format="%.2f",
                help="스크류 전진 속도 (m/s). 게이트에서의 유속에 영향.",
                key="input_injection_speed"
            )
            if new_speed != st.session_state.get("injection_speed_mps"):
                st.session_state["injection_speed_mps"] = new_speed
                _sync_process_override(WORKSPACE_ROOT, st.session_state)

        # Control buttons
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("🔄 Reset Process Overrides to Default", key="reset_process_override"):
                st.session_state["stage_1_pressure_mpa"] = 100.0
                st.session_state["stage_1_time_s"] = 1.5
                st.session_state["stage_2_pressure_mpa"] = 80.0
                st.session_state["stage_2_time_s"] = 3.0
                st.session_state["stage_3_pressure_mpa"] = 40.0
                st.session_state["stage_3_time_s"] = 2.0
                st.session_state["melt_temp_k"] = 563.15
                st.session_state["mold_temp_k"] = 373.15
                st.session_state["injection_speed_mps"] = 0.25
                st.session_state["expert_process_enabled"] = False
                _sync_process_override(WORKSPACE_ROOT, st.session_state)
                st.success("Process overrides reset to default.")
                st.rerun()

        with col_b2:
            if st.button("💾 Save Process Override to JSON", key="save_process_override"):
                st.session_state["expert_process_enabled"] = True
                _sync_process_override(WORKSPACE_ROOT, st.session_state)
                st.success("Process override saved to manual_override.json ✅")

        # Override summary
        st.markdown("**📋 Current Override Summary**")
        st.code(
            f"Packing: {st.session_state['stage_1_pressure_mpa']:.1f}MPa/{st.session_state['stage_1_time_s']:.1f}s "
            f"→ {st.session_state['stage_2_pressure_mpa']:.1f}MPa/{st.session_state['stage_2_time_s']:.1f}s "
            f"→ {st.session_state['stage_3_pressure_mpa']:.1f}MPa/{st.session_state['stage_3_time_s']:.1f}s\n"
            f"Melt Temp: {st.session_state['melt_temp_k']:.1f}K ({st.session_state['melt_temp_k']-273.15:.1f}°C)\n"
            f"Mold Temp: {st.session_state['mold_temp_k']:.1f}K ({st.session_state['mold_temp_k']-273.15:.1f}°C)\n"
            f"Injection Speed: {st.session_state['injection_speed_mps']:.2f} m/s",
            language="text"
        )

        st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section C: Auto-Wizard & Process Control Buttons (Original)
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("4-C. Process Control & Optimization")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Molding Window**")
        if st.button("🔧 Process Window", key="pw"):
            _run_with_feedback("process_window_solver.py", "Process window computed.")
        if st.button("📊 DOE Optimizer", key="doe"):
            _run_with_feedback("doe_optimizer.py", "DOE optimization completed.")

        st.markdown("**Flow & Packing**")
        if st.button("🌊 Multistage Flow Ctrl", key="fc"):
            _run_with_feedback("multistage_flow_controller.py", "Flow controller optimized.")
        if st.button("📦 Multistage Packing", key="pb"):
            _run_with_feedback("multistage_packing_binder.py", "Packing binder applied.")

    with col2:
        st.markdown("**Runner & Gate**")
        if st.button("⚖ Runner Balancer", key="rb"):
            _run_with_feedback("runner_balancer.py", "Runner balancing done.")
        if st.button("🎯 Gate Aligner", key="ga"):
            _run_with_feedback("gate_aligner.py", "Gate alignment computed.")
        if st.button("📐 Gate Advisor", key="gadv"):
            _run_with_feedback("gate_advisor.py", "Gate advisory generated.")

        st.markdown("**Venting & Jetting**")
        if st.button("💨 Vent Designer", key="vd"):
            _run_with_feedback("vent_designer.py", "Vent design computed.")
        if st.button("🌪 Jetting Analyzer", key="ja"):
            _run_with_feedback("jetting_analyzer.py", "Jetting analysis done.")

    with col3:
        st.markdown("**Advanced Control**")
        if st.button("🔄 VP Switchover", key="vps"):
            _run_with_feedback("vp_switchover_handler.py", "V/P switchover optimized.")
        if st.button("⚡ Fast Melt Front", key="fmf"):
            _run_with_feedback("fast_melt_front_advisor.py", "Melt front analyzed.")
        if st.button("🧪 Purging Multiphase", key="pm"):
            _run_with_feedback("purging_multiphase_solver.py", "Purging simulation done.")
        if st.button("🔬 MuCell PVT", key="mucell"):
            _run_with_feedback("mucell_pvt_solv.py", "MuCell PVT solved.")
        if st.button("⚙ Expert Process Editor", key="epe_proc"):
            with st.spinner("Launching expert process editor..."):
                try:
                    run_module("expert_process_editor.py", raise_on_error=True)
                    _load_process_override(WORKSPACE_ROOT, st.session_state)
                    st.success("Process editor launched. Overrides loaded.")
                except Exception as e:
                    st.error(f"Process editor failed: {e}")

    # Status
    if st.session_state.get("process_window_ok") or st.session_state.get("expert_process_enabled"):
        st.success("✅ Process configuration: ACTIVE")
    else:
        st.info("ℹ Select Auto-Wizard (Process Window / DOE) or enable Expert Mode.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section D: ⚙️ Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 밸브 게이트 타이밍 & 런너 밸런싱 상세 설정", expanded=False):
        st.markdown("##### 💨 밸브 게이트 개폐 타이밍 (Valve Gate Sequential Timing)")
        st.caption("순자 밸브 게이트(SVG) 개폐 시간을 게이트별로 설정하세요. 0 = 주사 시작과 동시에 개폐.")

        n_vg = st.session_state.get("valve_gate_count", 0)
        if n_vg == 0:
            # Try to get from machine_spec
            spec_path = WORKSPACE_ROOT / "machine_spec.json"
            if spec_path.exists():
                try:
                    import json
                    _spec = json.loads(spec_path.read_text(encoding="utf-8"))
                    n_vg = _spec.get("valve_gate_count", 0)
                except Exception:
                    pass

        if n_vg > 0:
            vg_timing = st.session_state.get("valve_gate_timing_s", {})
            cols_vg = st.columns(min(n_vg, 4))
            for i in range(n_vg):
                gate_key = f"gate_{i+1}"
                col_idx = i % 4
                with cols_vg[col_idx]:
                    t_open = st.number_input(
                        f"💨 Gate {i+1} 개폐 (s)",
                        min_value=0.0, max_value=30.0,
                        value=float(vg_timing.get(gate_key, 0.0 + i * 0.3)),
                        step=0.05, format="%.2f",
                        help=f"Gate {i+1} 밸브 개폐 시점 (s, 주사 시작 후)",
                        key=f"adv_vg_timing_{i}",
                    )
                    vg_timing[gate_key] = t_open
            st.session_state["valve_gate_timing_s"] = vg_timing
        else:
            st.info("ℹ 밸브 게이트 수가 0입니다. Tab 1 Pre-process Advanced Options에서 valve_gate_count를 설정하세요.")

        st.markdown("---")
        st.markdown("##### 🔍 V/P 전환 조건 (V/P Switchover Advanced)")
        col_vp1, col_vp2 = st.columns(2)
        with col_vp1:
            vp_pos = st.number_input(
                "📐 V→P 전환 위치 (Screw mm)",
                min_value=0.0, max_value=200.0,
                value=float(st.session_state.get("vp_switchover_pos_mm", 10.0)),
                step=0.5, format="%.1f",
                help="쿠션 위치를 기준으로 한 V→P 전환 스크류 위치 (mm)",
                key="adv_vp_position",
            )
            st.session_state["vp_switchover_pos_mm"] = vp_pos

        with col_vp2:
            cushion = st.number_input(
                "💹 쿠션비 (Cushion, mm)",
                min_value=0.0, max_value=50.0,
                value=float(st.session_state.get("cushion_mm", 5.0)),
                step=0.5, format="%.1f",
                help="쿠션 0를 피하기 위한 쿠션비 최소화 목표치 (mm)",
                key="adv_cushion",
            )
            st.session_state["cushion_mm"] = cushion

        if st.button("💾 Advanced Process Options 저장 → manual_override.json", key="save_adv_process"):
            import json
            _sync_process_override(WORKSPACE_ROOT, st.session_state)
            override_path = WORKSPACE_ROOT / "manual_override.json"
            data = {}
            if override_path.exists():
                try:
                    data = json.loads(override_path.read_text())
                except Exception:
                    pass
            data.setdefault("process", {})
            data["process"]["valve_gate_timing_s"] = st.session_state.get("valve_gate_timing_s", {})
            data["process"]["vp_switchover_pos_mm"] = st.session_state.get("vp_switchover_pos_mm", 10.0)
            data["process"]["cushion_mm"] = st.session_state.get("cushion_mm", 5.0)
            override_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
            st.success("✅ Advanced Process Options → manual_override.json 저장 완료")