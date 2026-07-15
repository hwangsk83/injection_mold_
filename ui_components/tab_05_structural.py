# -*- coding: utf-8 -*-
"""Tab 5: Structural -- Fatigue, Fracture (CZM), Homogenization, FSI Mapping"""
import streamlit as st
import json
from pathlib import Path
from core_utils.subprocess_utils import run_module


def _sync_structural_spec(WORKSPACE_ROOT, session_state):
    """Serialize structural params -> machine_spec.json"""
    spec_path = WORKSPACE_ROOT / "machine_spec.json"
    existing = {}
    if spec_path.exists():
        try:
            existing = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    existing["structural"] = {
        "fatigue": {
            "n_cycles": session_state.get("fatigue_cycles", 100000),
            "stress_ratio": session_state.get("stress_ratio", 0.1),
            "fracture_toughness_mpa_m05": session_state.get("fracture_toughness_mpa_m05", 2.5),
        },
        "czm": {
            "gc": session_state.get("czm_gc", 1.0),
            "sigma_max": session_state.get("czm_sigma_max", 50.0),
        },
        "homogenization": {
            "method": session_state.get("homogenization_method", "Halpin-Tsai"),
        },
    }
    spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")


def render(WORKSPACE_ROOT, SPEC_JSON):
    # Session State 초기화
    st.session_state.setdefault("fatigue_cycles", 100000)
    st.session_state.setdefault("stress_ratio", 0.1)
    st.session_state.setdefault("fracture_toughness_mpa_m05", 2.5)
    st.session_state.setdefault("czm_gc", 1.0)
    st.session_state.setdefault("czm_sigma_max", 50.0)
    st.session_state.setdefault("homogenization_method", "Halpin-Tsai")

    # ==================================================================
    # Section A: Fatigue Analysis
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("5-A. Fatigue & Fracture Analysis")

    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        new_cycles = st.number_input(
            "🔄 Fatigue Cycles (N)",
            min_value=100, max_value=100000000,
            value=int(st.session_state.get("fatigue_cycles", 100000)),
            step=10000, format="%d",
            help="반복 하중 사이클 수. 예: 100,000 cycles",
            key="input_fatigue_cycles"
        )
        if new_cycles != st.session_state.get("fatigue_cycles"):
            st.session_state["fatigue_cycles"] = new_cycles
            _sync_structural_spec(WORKSPACE_ROOT, st.session_state)

    with col_f2:
        new_ratio = st.number_input(
            "⚖ Stress Ratio (R = σ_min/σ_max)",
            min_value=-1.0, max_value=1.0,
            value=float(st.session_state.get("stress_ratio", 0.1)),
            step=0.05, format="%.2f",
            help="응력 비율. R=0.1은 인장-인장 피로. R=-1은 완전 양진.",
            key="input_stress_ratio"
        )
        if new_ratio != st.session_state.get("stress_ratio"):
            st.session_state["stress_ratio"] = new_ratio
            _sync_structural_spec(WORKSPACE_ROOT, st.session_state)

    with col_f3:
        new_kic = st.number_input(
            "🔪 Fracture Toughness KIC (MPa·√m)",
            min_value=0.1, max_value=200.0,
            value=float(st.session_state.get("fracture_toughness_mpa_m05", 2.5)),
            step=0.5, format="%.2f",
            help="파괴 인성. PC: ~2-3 MPa·√m, ABS: ~1.5-2.5 MPa·√m",
            key="input_fracture_toughness"
        )
        if new_kic != st.session_state.get("fracture_toughness_mpa_m05"):
            st.session_state["fracture_toughness_mpa_m05"] = new_kic
            _sync_structural_spec(WORKSPACE_ROOT, st.session_state)

    # Fatigue solvers
    col_fb1, col_fb2, col_fb3 = st.columns(3)
    with col_fb1:
        if st.button("📉 J-Integral Fatigue Solver", key="j_fatigue"):
            with st.spinner("Running J-integral fatigue analysis..."):
                try:
                    run_module("j_integral_fatigue_solver.py", raise_on_error=True)
                    st.success("J-integral fatigue completed.")
                except Exception as e:
                    st.error(f"Fatigue solver failed: {e}")

    with col_fb2:
        if st.button("🔬 XFEM Crack Propagator", key="xfem"):
            with st.spinner("Running XFEM crack propagation..."):
                try:
                    run_module("xfem_crack_propagator.py", raise_on_error=True)
                    st.success("XFEM crack analysis completed.")
                except Exception as e:
                    st.error(f"XFEM failed: {e}")

    with col_fb3:
        if st.button("💪 Plastic Failure Bridge", key="pf_bridge"):
            with st.spinner("Running plastic failure analysis..."):
                try:
                    run_module("plastic_failure_bridge.py", raise_on_error=True)
                    st.success("Plastic failure analysis done.")
                except Exception as e:
                    st.error(f"Failure bridge failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section B: CZM Delamination Parameters
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("5-B. Cohesive Zone Model (CZM) — Delamination")

    col_c1, col_c2 = st.columns(2)

    with col_c1:
        new_gc = st.number_input(
            "🔗 Critical Energy Release Rate Gc (N/mm)",
            min_value=0.01, max_value=100.0,
            value=float(st.session_state.get("czm_gc", 1.0)),
            step=0.1, format="%.2f",
            help="임계 에너지 방출률. PC/ABS: 0.5-3.0 N/mm",
            key="input_czm_gc"
        )
        if new_gc != st.session_state.get("czm_gc"):
            st.session_state["czm_gc"] = new_gc
            _sync_structural_spec(WORKSPACE_ROOT, st.session_state)

    with col_c2:
        new_sigma = st.number_input(
            "📏 Maximum Traction σ_max (MPa)",
            min_value=1.0, max_value=500.0,
            value=float(st.session_state.get("czm_sigma_max", 50.0)),
            step=5.0, format="%.1f",
            help="계면 최대 견인 응력. 일반적으로 재료 항복 강도의 50-80%",
            key="input_czm_sigma"
        )
        if new_sigma != st.session_state.get("czm_sigma_max"):
            st.session_state["czm_sigma_max"] = new_sigma
            _sync_structural_spec(WORKSPACE_ROOT, st.session_state)

    col_cb1, col_cb2 = st.columns(2)
    with col_cb1:
        if st.button("🧩 CZM Delamination Solver", key="czm_solve"):
            with st.spinner("Running CZM delamination analysis..."):
                try:
                    run_module("czm_delamination_solver.py", raise_on_error=True)
                    st.success("CZM delamination solved.")
                except Exception as e:
                    st.error(f"CZM solver failed: {e}")

    with col_cb2:
        if st.button("📐 Core Deformator", key="core_def"):
            with st.spinner("Analyzing core deformation..."):
                try:
                    run_module("core_deformator.py", raise_on_error=True)
                    st.success("Core deformation analyzed.")
                except Exception as e:
                    st.error(f"Core deformator failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section C: Multi-Scale Homogenization
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("5-C. Multi-Scale Homogenization (Fiber-Reinforced)")

    col_h1, col_h2 = st.columns([2, 3])

    with col_h1:
        methods = ["Halpin-Tsai", "Mori-Tanaka", "Rule of Mixtures", "FE-RVE"]
        selected_method = st.selectbox(
            "🧬 Homogenization Method",
            options=methods,
            index=methods.index(st.session_state.get("homogenization_method", "Halpin-Tsai")),
            key="select_homogenization"
        )
        if selected_method != st.session_state.get("homogenization_method"):
            st.session_state["homogenization_method"] = selected_method
            _sync_structural_spec(WORKSPACE_ROOT, st.session_state)

    with col_h2:
        st.markdown("**Method Description**")
        if selected_method == "Halpin-Tsai":
            st.caption("Semi-empirical model for aligned short fiber composites. Good for moderate fiber volume fractions (Vf < 50%).")
        elif selected_method == "Mori-Tanaka":
            st.caption("Mean-field homogenization. Accounts for fiber interaction via Eshelby tensor. Good for higher Vf.")
        elif selected_method == "Rule of Mixtures":
            st.caption("Simple upper/lower bound estimation. Voigt (iso-strain) and Reuss (iso-stress) bounds.")
        elif selected_method == "FE-RVE":
            st.caption("Full-field finite element representative volume element. Most accurate but computationally expensive.")

    col_hb1, col_hb2, col_hb3 = st.columns(3)
    with col_hb1:
        if st.button("🔬 Multiscale Homogenizer", key="multiscale_hom"):
            with st.spinner("Running multiscale homogenization..."):
                try:
                    run_module("multiscale_homogenizer.py", raise_on_error=True)
                    st.success("Homogenization completed.")
                except Exception as e:
                    st.error(f"Homogenizer failed: {e}")

    with col_hb2:
        if st.button("📊 Structural Homogenizer", key="struct_hom"):
            with st.spinner("Running structural homogenization..."):
                try:
                    run_module("structural_homogenizer.py", raise_on_error=True)
                    st.success("Structural homogenization done.")
                except Exception as e:
                    st.error(f"Structural homogenizer failed: {e}")

    with col_hb3:
        if st.button("🗺 FSI Mapper", key="fsi_map"):
            with st.spinner("Running FSI mapping..."):
                try:
                    run_module("fsi_mapper.py", raise_on_error=True)
                    st.success("FSI mapping completed.")
                except Exception as e:
                    st.error(f"FSI mapper failed: {e}")

    # Show homogenized stiffness if available
    stiffness_path = WORKSPACE_ROOT / "homogenized_stiffness_map.json"
    if stiffness_path.exists():
        with st.expander("📋 View Homogenized Stiffness Map", expanded=False):
            try:
                stiff_data = json.loads(stiffness_path.read_text())
                st.json(stiff_data.get("global_stiffness", {}))
            except Exception:
                st.warning("Could not read stiffness map.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section D: Additional Structural Tools
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("5-D. Additional Structural Analysis")

    col_s1, col_s2, col_s3 = st.columns(3)

    with col_s1:
        if st.button("🔩 Die Compensation Solver", key="die_comp"):
            with st.spinner("Running die compensation..."):
                try:
                    run_module("die_compensation_solver.py", raise_on_error=True)
                    st.success("Die compensation completed.")
                except Exception as e:
                    st.error(f"Die compensation failed: {e}")

        if st.button("📏 Viscoelastic Mapper", key="visco_map"):
            with st.spinner("Running viscoelastic mapping..."):
                try:
                    run_module("visco_mapper.py", raise_on_error=True)
                    st.success("Viscoelastic mapping done.")
                except Exception as e:
                    st.error(f"Visco mapper failed: {e}")

    with col_s2:
        if st.button("🏗 Topology Optimizer", key="topo_opt"):
            with st.spinner("Running topology optimization..."):
                try:
                    run_module("topology_optimizer.py", raise_on_error=True)
                    st.success("Topology optimization completed.")
                except Exception as e:
                    st.error(f"Topology optimizer failed: {e}")

        if st.button("🔩 Initial Stress Binder", key="init_stress"):
            with st.spinner("Binding initial stresses..."):
                try:
                    run_module("initial_stress_binder.py", raise_on_error=True)
                    st.success("Initial stress binding done.")
                except Exception as e:
                    st.error(f"Stress binder failed: {e}")

    with col_s3:
        if st.button("💾 Save Structural Config", key="save_struct"):
            _sync_structural_spec(WORKSPACE_ROOT, st.session_state)
            st.success("Structural config saved to machine_spec.json ✅")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section E: ⚙️ Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 다중 스케일 균질화 모델 & 섬유 상세 파라미터", expanded=False):
        st.markdown("##### 🧬 섬유 강화 파라미터 (Fiber Reinforcement Parameters)")
        st.caption("섬유 체적분율, 종투비 등은 Mori-Tanaka / Halpin-Tsai 균질화 모델 입력값으로 사용됩니다.")

        col_adv1, col_adv2, col_adv3 = st.columns(3)

        with col_adv1:
            fiber_vf = st.number_input(
                "🧪 섬유 체적분율 Vf",
                min_value=0.0, max_value=0.7,
                value=float(st.session_state.get("fiber_volume_fraction", 0.112)),
                step=0.005, format="%.3f",
                help="유리섬유 GF20 기준 약 0.112 (중량분율 20% 수준)",
                key="adv_fiber_vf",
            )
            st.session_state["fiber_volume_fraction"] = fiber_vf

        with col_adv2:
            fiber_ar = st.number_input(
                "📏 섬유 종투비 (Aspect Ratio)",
                min_value=1.0, max_value=1000.0,
                value=float(st.session_state.get("fiber_aspect_ratio", 25.0)),
                step=1.0, format="%.1f",
                help="l/d 종투비. 단섬유: 20~50, 레이어: 1~10, 나노튜브: 100~1000",
                key="adv_fiber_ar",
            )
            st.session_state["fiber_aspect_ratio"] = fiber_ar

        with col_adv3:
            fiber_E = st.number_input(
                "🔬 섬유 탄성계수 Ef (MPa)",
                min_value=1000.0, max_value=1000000.0,
                value=float(st.session_state.get("fiber_modulus_mpa", 72000.0)),
                step=1000.0, format="%.0f",
                help="유리섬유: ~72,000 MPa, 탄소섬유: ~230,000 MPa",
                key="adv_fiber_E",
            )
            st.session_state["fiber_modulus_mpa"] = fiber_E

        st.markdown("---")
        st.markdown("##### 🔬 다중 스케일 해석 제어 (Multiscale Coupling)")
        col_adv4, col_adv5 = st.columns(2)

        with col_adv4:
            ms_method = st.selectbox(
                "🧬 균질화 모델 선택",
                ["Halpin-Tsai", "Mori-Tanaka", "Rule of Mixtures", "FE-RVE"],
                index=["Halpin-Tsai", "Mori-Tanaka", "Rule of Mixtures", "FE-RVE"].index(
                    st.session_state.get("homogenization_method", "Halpin-Tsai")
                ),
                key="adv_homog_method",
            )
            st.session_state["homogenization_method"] = ms_method

        with col_adv5:
            coupling_coeff = st.number_input(
                "🔗 유체-구조 연성 계수 (FSI Coupling)",
                min_value=0.0, max_value=2.0,
                value=float(st.session_state.get("fracture_coupling_coeff", 1.0)),
                step=0.1, format="%.2f",
                help="유체-구조 연성 강도 계수. 1.0 = 완전 연성, 0 = 비연성",
                key="adv_coupling_coeff",
            )
            st.session_state["fracture_coupling_coeff"] = coupling_coeff

        if st.button("💾 Advanced Structural Config 저장 → machine_spec.json", key="save_adv_structural"):
            spec_path = WORKSPACE_ROOT / "machine_spec.json"
            existing = {}
            if spec_path.exists():
                try:
                    existing = json.loads(spec_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            existing.setdefault("structural", {})
            existing["structural"]["fiber"] = {
                "volume_fraction": fiber_vf,
                "aspect_ratio": fiber_ar,
                "modulus_mpa": fiber_E,
            }
            existing["structural"]["homogenization"] = {"method": ms_method}
            existing["structural"]["fsi_coupling_coeff"] = coupling_coeff
            spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
            st.success("✅ Advanced Structural Config → machine_spec.json 저장 완료")