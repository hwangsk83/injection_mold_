# -*- coding: utf-8 -*-
"""Tab 6: Quality -- Defects, Sink Mark, Gate Freeze, Weldline
   (Self-Healing: st.spinner + error handling for all subprocess calls)
"""
import streamlit as st
from core_utils.subprocess_utils import run_module

def _run_with_feedback(module_name: str, success_msg: str = "Done"):
    """Run a backend module with spinner and error feedback."""
    with st.spinner(f"Running {module_name}..."):
        try:
            run_module(module_name, raise_on_error=True)
            st.success(success_msg)
        except Exception as e:
            st.error(f"{module_name} failed: {e}")

def render(WORKSPACE_ROOT, SPEC_JSON):
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("6. Quality & Defect Analysis")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Surface & Dimensional**")
        if st.button("📉 Sink Mark Solver", key="sms"):
            _run_with_feedback("sinkmark_vol_predictor.py", "Sink mark prediction completed.")
        if st.button("🔍 Defect Analyzer", key="da"):
            _run_with_feedback("defect_analyzer.py", "Defect analysis completed.")
        if st.button("📏 Surface Quality", key="sq"):
            _run_with_feedback("surface_quality_solver.py", "Surface quality evaluated.")

    with col2:
        st.markdown("**Gate & Flow**")
        if st.button("❄ Gate Freeze Detector", key="gfd"):
            _run_with_feedback("gate_freeze_detector.py", "Gate freeze time computed.")
        if st.button("🔄 Check-ring Backflow", key="crb"):
            _run_with_feedback("checkring_backflow_simulator.py", "Backflow simulation done.")
        if st.button("💪 Plastic Failure", key="pf"):
            _run_with_feedback("plastic_failure_bridge.py", "Failure analysis completed.")

    with col3:
        st.markdown("**Weld & Fiber**")
        if st.button("🧵 Weld Strength Map", key="wsm"):
            _run_with_feedback("weld_strength_mapper.py", "Weld strength mapped.")
        if st.button("🧬 Fiber Orientation", key="fo"):
            _run_with_feedback("fiber_orientator.py", "Fiber orientation computed.")
        if st.button("📐 Shrinkage Calculator", key="sc"):
            _run_with_feedback("shrinkage_calculator.py", "Shrinkage calculated.")

    st.markdown('</div>', unsafe_allow_html=True)

    # Additional quality metrics panel
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("**Quality Metrics Summary**")

    audit_path = WORKSPACE_ROOT / "audit_report.json"
    if audit_path.exists():
        import json
        with open(audit_path, "r", encoding="utf-8") as f:
            audit = json.load(f)
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            if "check3_shrinkage" in audit:
                st.metric("Shrinkage Check", "PASS" if "PASS" in str(audit["check3_shrinkage"]) else "N/A")
        with col_m2:
            if "check13_srf_degradation_bounds" in audit:
                st.metric("SRF Bounds", audit["check13_srf_degradation_bounds"].get("result", "N/A"))
        with col_m3:
            if "check9_trace_conservation" in audit:
                violations = audit["check9_trace_conservation"].get("n_violations", "?")
                st.metric("Fiber Trace Violations", str(violations))
    else:
        st.info("Run quality solvers and system auditor to populate metrics.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section C: ⚙️ Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 결함 판정 임계값 & 품질 기준 상세 설정", expanded=False):
        import json
        from pathlib import Path
        st.markdown("##### 🔍 결함 판정 임계값 (Defect Threshold Parameters)")
        st.caption("아래 값을 초과하면 결함으로 판정됩니다. machine_spec.json에 저장됩니다.")

        col_t1, col_t2, col_t3 = st.columns(3)

        with col_t1:
            sink_threshold = st.number_input(
                "📉 싱크마크 깊이 한계 (mm)",
                min_value=0.001, max_value=5.0,
                value=float(st.session_state.get("sink_mark_threshold_mm", 0.05)),
                step=0.005, format="%.3f",
                help="싱크마크 심도 허용스 (mm). 이를 초과하면 FAIL",
                key="adv_sink_threshold",
            )
            st.session_state["sink_mark_threshold_mm"] = sink_threshold

        with col_t2:
            weld_angle_max = st.number_input(
                "🧵 용접선 최대 각도 (°)",
                min_value=10.0, max_value=180.0,
                value=float(st.session_state.get("weld_line_angle_deg", 135.0)),
                step=5.0, format="%.1f",
                help="용접선 합류각 허용 상한 (°). 135° 이하 = 강도 저하 위험",
                key="adv_weld_angle",
            )
            st.session_state["weld_line_angle_deg"] = weld_angle_max

        with col_t3:
            shrink_limit = st.number_input(
                "💹 수축률 허용 상한 (%)",
                min_value=0.01, max_value=10.0,
                value=float(st.session_state.get("shrinkage_limit_pct", 0.8)),
                step=0.05, format="%.2f",
                help="수콡 수축률 허용스 (%). 대부분 0.3~1.5%를 허용합니다.",
                key="adv_shrink_limit",
            )
            st.session_state["shrinkage_limit_pct"] = shrink_limit

        if st.button("💾 품질 임계값 저장 → machine_spec.json", key="save_adv_quality"):
            spec_path = Path(WORKSPACE_ROOT) / "machine_spec.json"
            existing = {}
            if spec_path.exists():
                try:
                    existing = json.loads(spec_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            existing["quality_thresholds"] = {
                "sink_mark_mm": sink_threshold,
                "weld_line_angle_deg": weld_angle_max,
                "shrinkage_pct": shrink_limit,
            }
            spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
            st.success("✅ 품질 임계값 → machine_spec.json 저장 완료")