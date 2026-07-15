# -*- coding: utf-8 -*-
"""Tab 7: V&V -- System Auditor, Benchmark, Verification Framework
   (Self-Healing: core_utils.subprocess_utils + st.spinner, no raw subprocess.run)
"""
import streamlit as st
import json
from pathlib import Path
from core_utils.subprocess_utils import run_module, run_with_status

def render(WORKSPACE_ROOT, SPEC_JSON):
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("7. Verification & Validation")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**System Auditor**")
        if st.button("🔍 Run System Auditor (71 Checks)", key="aud"):
            with st.spinner("Running system_auditor.py - this may take a few minutes..."):
                try:
                    result = run_with_status("system_auditor.py")
                    if result["ok"]:
                        st.code(result["stdout"][:3000] or "(no stdout)")
                        st.success("✅ All checks PASSED")
                        st.session_state["audit_passed"] = True
                    else:
                        st.code(result["stderr"][:3000] or result["stdout"][:3000])
                        st.error(f"❌ Audit FAILED (exit code: {result['code']})")
                        st.session_state["audit_passed"] = False
                except Exception as e:
                    st.error(f"Auditor execution failed: {e}")

    with col2:
        st.markdown("**Benchmark & Verification**")
        if st.button("📊 Run Benchmark Verification", key="bmv"):
            with st.spinner("Running benchmark verification..."):
                try:
                    run_module("benchmark_verification.py", raise_on_error=True)
                    st.success("Benchmark verification completed.")
                except Exception as e:
                    st.error(f"Benchmark failed: {e}")

        if st.button("✅ Verification Framework", key="vf"):
            with st.spinner("Running verification framework..."):
                try:
                    run_module("verification_framework.py", raise_on_error=True)
                    st.success("Verification framework passed.")
                except Exception as e:
                    st.error(f"Verification framework failed: {e}")

        if st.button("🧪 Run Validation Suite", key="rvs"):
            with st.spinner("Running validation suite..."):
                try:
                    run_module("validation_runner.py", raise_on_error=True)
                    st.success("Validation suite completed.")
                except Exception as e:
                    st.error(f"Validation suite failed: {e}")

    # Audit report viewer
    ar = WORKSPACE_ROOT / "audit_report.json"
    if ar.exists():
        with open(ar, "r", encoding="utf-8") as f:
            audit_data = json.load(f)
        st.markdown("**Audit Report Summary**")
        # Count PASS/FAIL results
        pass_count = sum(1 for v in audit_data.values() if isinstance(v, dict) and v.get("result") == "PASS")
        fail_count = sum(1 for v in audit_data.values() if isinstance(v, dict) and v.get("result") == "FAIL")
        st.metric("PASS Count", pass_count)
        if fail_count > 0:
            st.metric("FAIL Count", fail_count, delta=f"-{fail_count}", delta_color="inverse")
        with st.expander("View Full Audit Report JSON"):
            st.json(audit_data)

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section C: ⚙️ Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 검증 수렴 임계값 & 오딧 제어", expanded=False):
        st.markdown("##### 🗓 V&V 제어 파라미터")

        col_adv1, col_adv2, col_adv3 = st.columns(3)

        with col_adv1:
            vv_tol = st.number_input(
                "🎯 검증 수렴 허용오차 (V&V Tolerance)",
                min_value=1e-10, max_value=1e-1,
                value=float(st.session_state.get("vv_convergence_tol", 1e-4)),
                step=1e-5, format="%.1e",
                help="V&V 수렴 판정 임계값. 구첤적으로 해석 수렴 오차와 비교합니다.",
                key="adv_vv_tol",
            )
            st.session_state["vv_convergence_tol"] = vv_tol

        with col_adv2:
            max_checks = st.number_input(
                "🔢 최대 실행 체크 수 (Max Checks)",
                min_value=1, max_value=200,
                value=int(st.session_state.get("max_audit_checks", 71)),
                step=1,
                help="시스템 오딧원 실행 체크 개수 제한 (1~71)",
                key="adv_max_checks",
            )
            st.session_state["max_audit_checks"] = max_checks

        with col_adv3:
            benchmark_tol = st.number_input(
                "📊 밤치마크 허용 편차 (%)",
                min_value=0.01, max_value=50.0,
                value=float(st.session_state.get("benchmark_tolerance_pct", 5.0)),
                step=0.5, format="%.2f",
                help="발치마크 바로미터 허용 편차 (%)",
                key="adv_bench_tol",
            )
            st.session_state["benchmark_tolerance_pct"] = benchmark_tol

        if st.button("💾 V&V Advanced Options 저장 → machine_spec.json", key="save_adv_vv"):
            spec_path = Path(WORKSPACE_ROOT) / "machine_spec.json"
            existing = {}
            if spec_path.exists():
                try:
                    existing = json.loads(spec_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            existing["vv_settings"] = {
                "convergence_tol": vv_tol,
                "max_audit_checks": max_checks,
                "benchmark_tolerance_pct": benchmark_tol,
            }
            spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
            st.success("✅ V&V Advanced Options → machine_spec.json 저장 완료")