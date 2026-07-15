# -*- coding: utf-8 -*-
"""Tab 2: Mesh -- Auto-Wizard / Expert Manual Override, Multi-Insert, Hot Runner, Cooling"""
import streamlit as st
import json
from pathlib import Path
from core_utils.subprocess_utils import run_module


def _sync_mesh_override(WORKSPACE_ROOT, session_state):
    """Serialize mesh override params -> manual_override.json"""
    override_path = WORKSPACE_ROOT / "manual_override.json"
    data = {}
    if override_path.exists():
        try:
            data = json.loads(override_path.read_text())
        except Exception:
            pass

    data["mesh"] = {
        "enabled": session_state.get("expert_mesh_enabled", False),
        "global_size_mm": session_state.get("global_mesh_size_mm", 4.0),
        "pin_points": session_state.get("mesh_pin_points", []),
        "boundary_layer_count": session_state.get("boundary_layer_count", 2),
    }
    override_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")


def _load_mesh_override(WORKSPACE_ROOT, session_state):
    """Load mesh override from manual_override.json into session_state"""
    override_path = WORKSPACE_ROOT / "manual_override.json"
    if override_path.exists():
        try:
            data = json.loads(override_path.read_text())
            mesh = data.get("mesh", {})
            session_state["expert_mesh_enabled"] = mesh.get("enabled", False)
            session_state["global_mesh_size_mm"] = mesh.get("global_size_mm", 4.0)
            session_state["mesh_pin_points"] = mesh.get("pin_points", [])
            session_state["boundary_layer_count"] = mesh.get("boundary_layer_count", 2)
        except Exception:
            pass


def render(WORKSPACE_ROOT, SPEC_JSON, case_dir):
    # Session State 초기화
    st.session_state.setdefault("expert_mesh_enabled", False)
    st.session_state.setdefault("global_mesh_size_mm", 4.0)
    st.session_state.setdefault("boundary_layer_count", 2)
    st.session_state.setdefault("mesh_pin_points", [])

    # Load existing overrides
    _load_mesh_override(WORKSPACE_ROOT, st.session_state)

    # ==================================================================
    # Section A: Auto-Wizard vs Expert Mode Toggle
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("2-A. Mesh Mode: Auto-Wizard / Expert Manual Override")

    col_toggle, col_info = st.columns([1, 3])
    with col_toggle:
        expert_on = st.toggle(
            "🔧 Expert Manual Override",
            value=st.session_state.get("expert_mesh_enabled", False),
            key="toggle_expert_mesh",
            help="ON: 수동으로 격자 크기와 경계층을 직접 설정합니다. OFF: Auto-Wizard가 자동으로 최적 격자를 생성합니다."
        )
        if expert_on != st.session_state.get("expert_mesh_enabled"):
            st.session_state["expert_mesh_enabled"] = expert_on
            _sync_mesh_override(WORKSPACE_ROOT, st.session_state)

    with col_info:
        if st.session_state.get("expert_mesh_enabled"):
            st.info("🔧 **Expert Mode Active**: 수동 격자 설정값이 적용됩니다. 아래에서 Global/Local 격자 크기를 직접 입력하세요.")
        else:
            st.info("🤖 **Auto-Wizard Mode**: Adaptive Mesher가 자동으로 최적 격자를 생성합니다. 버튼을 눌러 실행하세요.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section B: Expert Manual Mesh Parameters (visible when toggle ON)
    # ==================================================================
    if st.session_state.get("expert_mesh_enabled"):
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("2-B. Expert Mesh Parameters")

        col_m1, col_m2, col_m3 = st.columns(3)

        with col_m1:
            new_global = st.number_input(
                "🌐 Global Mesh Size (mm)",
                min_value=0.1, max_value=50.0,
                value=float(st.session_state.get("global_mesh_size_mm", 4.0)),
                step=0.1, format="%.2f",
                help="전체 도메인 기본 격자 크기 (mm). 작을수록 조밀한 격자.",
                key="input_global_mesh_size"
            )
            if new_global != st.session_state.get("global_mesh_size_mm"):
                st.session_state["global_mesh_size_mm"] = new_global
                _sync_mesh_override(WORKSPACE_ROOT, st.session_state)

        with col_m2:
            new_bl = st.number_input(
                "📐 Boundary Layer Count",
                min_value=0, max_value=10,
                value=int(st.session_state.get("boundary_layer_count", 2)),
                step=1,
                help="벽면 근처 경계층(프리즘 레이어) 개수. 0 = 경계층 없음.",
                key="input_boundary_layer"
            )
            if new_bl != st.session_state.get("boundary_layer_count"):
                st.session_state["boundary_layer_count"] = new_bl
                _sync_mesh_override(WORKSPACE_ROOT, st.session_state)

        with col_m3:
            st.markdown("**📌 Pin Points (Refinement Zones)**")
            st.caption("특정 위치에 국부 격자 세분화 영역을 추가합니다.")

        # Pin Points Data Editor
        st.markdown("**Pin Point Refinement Zones**")
        pin_points = st.session_state.get("mesh_pin_points", [])

        # Convert to DataFrame for editing
        import pandas as pd
        if pin_points:
            df_pins = pd.DataFrame(pin_points)
        else:
            df_pins = pd.DataFrame(columns=["x", "y", "z", "radius_mm", "local_size_mm"])

        edited_df = st.data_editor(
            df_pins,
            num_rows="dynamic",
            column_config={
                "x": st.column_config.NumberColumn("X (m)", format="%.4f"),
                "y": st.column_config.NumberColumn("Y (m)", format="%.4f"),
                "z": st.column_config.NumberColumn("Z (m)", format="%.4f"),
                "radius_mm": st.column_config.NumberColumn("Radius (mm)", min_value=0.1, max_value=50.0, format="%.1f"),
                "local_size_mm": st.column_config.NumberColumn("Local Size (mm)", min_value=0.01, max_value=10.0, format="%.2f"),
            },
            key="editor_pin_points"
        )

        # Update pin points if changed
        new_pins = edited_df.dropna(how='all').to_dict(orient="records")
        if new_pins != st.session_state.get("mesh_pin_points"):
            st.session_state["mesh_pin_points"] = new_pins
            _sync_mesh_override(WORKSPACE_ROOT, st.session_state)

        # Clear overrides button
        col_clr1, col_clr2 = st.columns(2)
        with col_clr1:
            if st.button("🔄 Reset Mesh Overrides to Default", key="reset_mesh_override"):
                st.session_state["global_mesh_size_mm"] = 4.0
                st.session_state["boundary_layer_count"] = 2
                st.session_state["mesh_pin_points"] = []
                st.session_state["expert_mesh_enabled"] = False
                _sync_mesh_override(WORKSPACE_ROOT, st.session_state)
                st.success("Mesh overrides reset to default.")
                st.rerun()

        with col_clr2:
            if st.button("💾 Save Mesh Override to JSON", key="save_mesh_override"):
                _sync_mesh_override(WORKSPACE_ROOT, st.session_state)
                st.success("Mesh override saved to manual_override.json ✅")

        # Display current override summary
        if st.session_state.get("expert_mesh_enabled"):
            st.markdown("**📋 Current Override Summary**")
            st.code(
                f"Global Size: {st.session_state['global_mesh_size_mm']:.2f} mm\n"
                f"Boundary Layers: {st.session_state['boundary_layer_count']}\n"
                f"Pin Points: {len(st.session_state.get('mesh_pin_points', []))} zones",
                language="text"
            )

        st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section C: Mesh Generation Buttons (Original)
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("2-C. Mesh Generation & Pre-processing")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Core Mesh**")
        if st.button("🧱 Multi-Insert Mesher", key="mi_mesh"):
            with st.spinner("Generating multi-insert mesh..."):
                try:
                    run_module("multi_insert_mesher.py", raise_on_error=True)
                    st.session_state["mesh_generated"] = True
                    st.success("Multi-insert mesh generated.")
                except Exception as e:
                    st.error(f"Mesh generation failed: {e}")

        if st.button("🔥 Hot Runner Mesher", key="hr_mesh"):
            with st.spinner("Meshing hot runner channels..."):
                try:
                    run_module("hot_runner_mesher.py", raise_on_error=True)
                    st.success("Hot runner mesh created.")
                except Exception as e:
                    st.error(f"Hot runner meshing failed: {e}")

        if st.button("🎯 Gate Patcher", key="gate_patch"):
            with st.spinner("Patching gate mesh..."):
                try:
                    run_module("gate_patcher.py", raise_on_error=True)
                    st.success("Gate mesh patched.")
                except Exception as e:
                    st.error(f"Gate patching failed: {e}")

    with col2:
        st.markdown("**Cooling System**")
        if st.button("❄ Cooling Mesher", key="cool_mesh"):
            with st.spinner("Generating cooling channel mesh..."):
                try:
                    run_module("cooling_mesher.py", raise_on_error=True)
                    st.success("Cooling mesh generated.")
                except Exception as e:
                    st.error(f"Cooling meshing failed: {e}")

        if st.button("💧 Hybrid Cooling Hydraulics", key="hch"):
            with st.spinner("Running hybrid cooling hydraulics..."):
                try:
                    run_module("hybrid_cooling_hydraulics.py", raise_on_error=True)
                    st.success("Cooling hydraulics computed.")
                except Exception as e:
                    st.error(f"Cooling hydraulics failed: {e}")

        if st.button("🌡 HR Thermal Controller", key="hr_thermal"):
            with st.spinner("Running HR thermal controller..."):
                try:
                    run_module("hr_thermal_controller.py", raise_on_error=True)
                    st.success("Thermal controller tuned.")
                except Exception as e:
                    st.error(f"Thermal controller failed: {e}")

    with col3:
        st.markdown("**Expert Tools**")
        if st.button("📏 Expert Manual Mesher", key="emm"):
            with st.spinner("Running expert manual mesher..."):
                try:
                    run_module("expert_manual_mesher.py", raise_on_error=True)
                    _load_mesh_override(WORKSPACE_ROOT, st.session_state)
                    st.success("Manual meshing completed. Overrides loaded.")
                except Exception as e:
                    st.error(f"Manual meshing failed: {e}")

        if st.button("⚙ Expert Solver Settings", key="ess"):
            with st.spinner("Configuring expert solver settings..."):
                try:
                    run_module("expert_solver_settings.py", raise_on_error=True)
                    st.success("Solver settings applied.")
                except Exception as e:
                    st.error(f"Solver settings failed: {e}")

    # Status indicator
    if st.session_state.get("mesh_generated"):
        st.success("✅ Mesh generation: COMPLETE")
    elif st.session_state.get("expert_mesh_enabled"):
        st.warning("⚠ Expert mesh overrides set. Run mesh generator to apply.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section D: ⚙️ Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 격자 품질 & 런너 밸런싱 상세 설정", expanded=False):
        st.markdown("##### 🔧 런너 밸런싱 치수 (Runner Balancing)")
        col_adv1, col_adv2, col_adv3 = st.columns(3)

        with col_adv1:
            runner_d = st.number_input(
                "📏 런너 직경 (mm)",
                min_value=1.0, max_value=50.0,
                value=float(st.session_state.get("runner_diameter_mm", 6.0)),
                step=0.5, format="%.1f",
                help="주 런너 직경. 런너 밸런싱 솔버에 전달됩니다.",
                key="adv_mesh_runner_d",
            )
            st.session_state["runner_diameter_mm"] = runner_d

        with col_adv2:
            sub_runner_d = st.number_input(
                "📏 서브 런너 직경 (mm)",
                min_value=1.0, max_value=30.0,
                value=float(st.session_state.get("sub_runner_diameter_mm", 4.0)),
                step=0.5, format="%.1f",
                help="분기 런너 직경 (mm)",
                key="adv_mesh_sub_runner_d",
            )
            st.session_state["sub_runner_diameter_mm"] = sub_runner_d

        with col_adv3:
            gate_land_len = st.number_input(
                "📏 게이트 Land 길이 (mm)",
                min_value=0.5, max_value=10.0,
                value=float(st.session_state.get("gate_land_length_mm", 1.5)),
                step=0.1, format="%.1f",
                help="게이트 Land 길이 (mm). 게이트 형상 메싱에 사용됨.",
                key="adv_mesh_gate_land",
            )
            st.session_state["gate_land_length_mm"] = gate_land_len

        st.markdown("##### ⚡ 격자 품질 파라미터 (Mesh Quality)")
        col_adv4, col_adv5 = st.columns(2)

        with col_adv4:
            mesh_quality = st.slider(
                "🎯 격자 품질 목표 (0~1)",
                min_value=0.1, max_value=1.0,
                value=float(st.session_state.get("mesh_quality_target", 0.7)),
                step=0.05,
                help="0.7 이상 권장. 값이 높을수록 정밀하지만 생성 시간이 증가합니다.",
                key="adv_mesh_quality",
            )
            st.session_state["mesh_quality_target"] = mesh_quality

        with col_adv5:
            mesh_skew_max = st.number_input(
                "📐 최대 허용 왜도 (Max Skewness)",
                min_value=0.1, max_value=0.99,
                value=float(st.session_state.get("mesh_max_skewness", 0.85)),
                step=0.01, format="%.2f",
                help="격자 왜도 허용 상한. 0.85 이하 권장.",
                key="adv_mesh_skew",
            )
            st.session_state["mesh_max_skewness"] = mesh_skew_max

        if st.button("💾 Advanced Mesh Options 저장 → manual_override.json", key="save_adv_mesh"):
            override_path = WORKSPACE_ROOT / "manual_override.json"
            data = {}
            if override_path.exists():
                try:
                    data = json.loads(override_path.read_text())
                except Exception:
                    pass
            data.setdefault("mesh", {})
            data["mesh"]["runner_diameter_mm"] = runner_d
            data["mesh"]["sub_runner_diameter_mm"] = sub_runner_d
            data["mesh"]["gate_land_length_mm"] = gate_land_len
            data["mesh"]["quality_target"] = mesh_quality
            data["mesh"]["max_skewness"] = mesh_skew_max
            override_path.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
            st.success("✅ Advanced Mesh Options → manual_override.json 저장 완료")