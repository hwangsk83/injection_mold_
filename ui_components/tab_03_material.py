# -*- coding: utf-8 -*-
"""Tab 3: Material -- 2-Depth Family/Grade Dropdown, Cross-WLF Viscosity Chart,
   Tait PvT Chart, Advanced Options toggle, real-time → machine_spec.json serialization.
   OVERHAUL v2.0
"""
import streamlit as st
import json
import numpy as np
import pandas as pd
from pathlib import Path
from core_utils.subprocess_utils import run_module


# ==================================================================
# DB Loaders
# ==================================================================

@st.cache_data(show_spinner=False)
def _load_material_db_cached(db_path_str: str) -> dict:
    """Load material_db.json (cached, keyed by path string for cache invalidation)."""
    try:
        return json.loads(Path(db_path_str).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_family_grade_map(db: dict) -> dict[str, dict[str, dict]]:
    """
    Flatten material_db nested structure into a 2-depth map:
      { family_label: { grade_label: props_dict } }

    Supports:
      Commercial_UDB_DB > Supplier > Grade > {CrossWLF, Tait, ...}
      Synthetic_AI_DB   > Supplier > Grade > {resin_family, CrossWLF, ...}
    """
    family_map: dict[str, dict[str, dict]] = {}

    for db_category, suppliers in db.items():
        if not isinstance(suppliers, dict):
            continue
        for supplier_name, grades in suppliers.items():
            if not isinstance(grades, dict):
                continue
            for grade_name, props in grades.items():
                if not isinstance(props, dict):
                    continue

                # ── Determine Family Label ──────────────────────────
                family = props.get("resin_family", "")
                if not family:
                    # Heuristic: first token before +, _, space, digit
                    import re
                    match = re.match(r'^([A-Za-z]+)', grade_name)
                    family = match.group(1) if match else grade_name[:3]

                # Map family aliases
                FAMILY_ALIASES = {
                    "ABS": "ABS", "PC": "PC", "PA": "PA", "PA66": "PA",
                    "PA6": "PA", "PP": "PP", "POM": "POM", "PPS": "PPS",
                    "PEEK": "PEEK", "PE": "PE", "PET": "PET", "PBT": "PBT",
                    "Synthetic": "Synthetic_AI",
                    # Brand names → resin family
                    "INFINO": "PC", "LUPOY": "PC", "STAREX": "ABS",
                    "ULTRAMID": "PA", "DELRIN": "POM", "LEXAN": "PC",
                }
                family = FAMILY_ALIASES.get(family, family)

                # ── Grade Label (includes supplier for uniqueness) ──
                source_tag = db_category.replace("Commercial_UDB_DB", "").replace("Synthetic_AI_DB", "[AI]").strip("_")
                if source_tag:
                    grade_label = f"{grade_name}  [{supplier_name}]"
                else:
                    grade_label = f"{grade_name}  [{supplier_name}]"

                if family not in family_map:
                    family_map[family] = {}
                # Store full props + metadata
                family_map[family][grade_label] = {
                    **props,
                    "_grade_name": grade_name,
                    "_supplier": supplier_name,
                    "_db_category": db_category,
                }

    return family_map


# ==================================================================
# Cross-WLF Viscosity Chart
# ==================================================================

def _render_viscosity_chart(wlf: dict, melt_temp_k: float):
    """Render Cross-WLF viscosity vs shear rate chart."""
    try:
        n = wlf.get("n", 0.3)
        tau_star = wlf.get("tau_star", 180000.0)
        D1 = wlf.get("D1", 1e13)
        D2 = wlf.get("D2", 413.15)
        A1 = wlf.get("A1", 31.2)
        A2 = wlf.get("A2", 51.6)

        T = melt_temp_k
        dT = T - D2
        if dT <= 0:
            st.warning("⚠ 용융 온도가 D2(기준 온도)보다 낮습니다. WLF 점도 계산 불가.")
            return

        eta_0 = D1 * np.exp(-A1 * dT / (A2 + dT))
        shear_rates = np.logspace(1, 5, 200)
        eta = eta_0 / (1.0 + (eta_0 * shear_rates / tau_star) ** (1.0 - n))

        df = pd.DataFrame({
            "전단 속도 γ̇ (1/s)": shear_rates,
            "점도 η (Pa·s)": eta,
        }).set_index("전단 속도 γ̇ (1/s)")

        st.caption(f"Cross-WLF | T = {T:.1f} K ({T - 273.15:.1f}°C) | η₀ = {eta_0:.2e} Pa·s")
        st.line_chart(df, height=200)
    except Exception as e:
        st.warning(f"점도 그래프 렌더링 실패: {e}")


# ==================================================================
# Tait PVT Chart
# ==================================================================

def _render_pvt_chart(tait: dict):
    """Render simplified Tait PVT specific volume vs pressure chart."""
    try:
        b1m = tait.get("b1m", 0.001)
        b2m = tait.get("b2m", 1e-6)
        b3m = tait.get("b3m", 130e6)
        b4m = tait.get("b4m", 0.004)
        b5 = tait.get("b5", 413.15)
        C = tait.get("C_tait", 0.0894)

        # Temperature range for visualization (melt region)
        pressures_MPa = np.linspace(0, 200, 100)
        # Compute at 3 temperatures
        T_values = [b5 - 20, b5 + 20, b5 + 60]
        records = []
        for T in T_values:
            for P in pressures_MPa:
                P_Pa = P * 1e6
                V0 = b1m + b2m * (T - b5)
                B = b3m * np.exp(-b4m * (T - b5))
                V = V0 * (1 - C * np.log(1 + P_Pa / B))
                records.append({"압력 P (MPa)": P, "비부피 V (m³/kg)": V, "T (K)": f"T={T:.0f}K"})

        df_pvt = pd.DataFrame(records).pivot(index="압력 P (MPa)", columns="T (K)", values="비부피 V (m³/kg)")
        st.caption("Tait PVT 모델 — 특정 부피 vs 압력 (Melt Region)")
        st.line_chart(df_pvt, height=200)
    except Exception as e:
        st.warning(f"PVT 그래프 렌더링 실패: {e}")


# ==================================================================
# Machine Spec Serialization
# ==================================================================

def _sync_material_to_spec(WORKSPACE_ROOT: Path, session_state: dict):
    """Write selected material name + key properties → machine_spec.json."""
    spec_path = WORKSPACE_ROOT / "machine_spec.json"
    existing = {}
    if spec_path.exists():
        try:
            existing = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    props = session_state.get("material_properties", {})
    # Store only serializable subset (exclude large arrays if any)
    serializable_keys = ["CrossWLF", "Tait", "Thermal", "Mechanical", "Additives",
                         "resin_family", "melt_index", "density", "is_synthetic",
                         "_grade_name", "_supplier", "_db_category"]
    props_clean = {k: v for k, v in props.items() if k in serializable_keys}

    existing["selected_material"] = session_state.get("selected_material_name", "")
    existing["selected_material_family"] = session_state.get("selected_material_family", "")
    existing["material_properties"] = props_clean
    existing["material_melt_temp_k"] = session_state.get("mat_melt_temp_k", 563.15)

    spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
    session_state["material_selected"] = True


# ==================================================================
# Main Render Function
# ==================================================================

def render(WORKSPACE_ROOT, SPEC_JSON):
    """Render Tab 3: Material."""
    WORKSPACE_ROOT = Path(WORKSPACE_ROOT)

    # ── Session State Defaults ─────────────────────────────────────
    st.session_state.setdefault("selected_material_name", "")
    st.session_state.setdefault("selected_material_family", "")
    st.session_state.setdefault("material_properties", {})
    st.session_state.setdefault("material_db_loaded", False)
    st.session_state.setdefault("mat_melt_temp_k", 563.15)

    # ── Load DB ────────────────────────────────────────────────────
    db_path = WORKSPACE_ROOT / "material_db.json"
    if not db_path.exists():
        st.error("⚠ material_db.json을 찾을 수 없습니다. 파일을 프로젝트 루트에 배치하세요.")
        return

    db = _load_material_db_cached(str(db_path))
    family_map = _build_family_grade_map(db)
    st.session_state["material_db_loaded"] = bool(family_map)

    if not family_map:
        st.warning("⚠ 재질 DB를 파싱할 수 없습니다. material_db.json 형식을 확인하세요.")
        return

    # ==================================================================
    # Section A: 2-Depth Material Selection (Family → Grade)
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🧪 3-A. 재질 선택 — 2-Depth 드롭다운")
    st.caption("수지 계열(Family)을 먼저 선택한 후, 세부 그레이드(Grade)를 선택하세요.")

    col_sel1, col_sel2, col_info = st.columns([1, 2, 2])

    with col_sel1:
        families = sorted(family_map.keys())
        # Restore previous family selection
        prev_family = st.session_state.get("selected_material_family", "")
        default_fam_idx = families.index(prev_family) if prev_family in families else 0

        selected_family = st.selectbox(
            "🏷 수지 계열 (Resin Family)",
            options=families,
            index=default_fam_idx,
            key="selector_material_family",
            help="PC, ABS, PA66, PP 등 수지의 기본 계열을 선택하세요.",
        )
        st.session_state["selected_material_family"] = selected_family

    with col_sel2:
        grades_in_family = list(family_map[selected_family].keys())
        # Restore previous grade
        prev_grade = st.session_state.get("selected_material_name", "")
        default_grade_idx = (
            grades_in_family.index(prev_grade)
            if prev_grade in grades_in_family else 0
        )

        selected_grade = st.selectbox(
            "🔬 그레이드 선택 (Grade)",
            options=grades_in_family,
            index=default_grade_idx,
            key="selector_material_grade",
            help="특정 상용 그레이드 또는 AI 합성 재질을 선택하세요.",
        )

        # Update session state immediately on selection
        if selected_grade:
            mat_props = family_map[selected_family][selected_grade]
            st.session_state["selected_material_name"] = selected_grade
            st.session_state["material_properties"] = mat_props

            # Auto-fill melt temp from Tait b5 if not manually set
            tait = mat_props.get("Tait", {})
            if tait.get("b5"):
                st.session_state.setdefault("mat_melt_temp_k", tait["b5"] + 150)

    with col_info:
        if selected_grade:
            props = family_map[selected_family][selected_grade]
            supplier = props.get("_supplier", "—")
            db_cat = props.get("_db_category", "")
            is_ai = props.get("is_synthetic", False)
            st.success(f"✅ 선택됨: **{props.get('_grade_name', selected_grade)}**")
            st.caption(f"공급사: {supplier}")
            if is_ai:
                st.info("🤖 AI 합성 재질 (Synthetic_AI_DB)")
            thermal = props.get("Thermal", {})
            if thermal:
                tg = thermal.get("Tg", 0) - 273.15
                tm = thermal.get("Tm", 0) - 273.15
                st.caption(f"Tg = {tg:.0f}°C  |  Tm = {tm:.0f}°C")
        else:
            st.info("👆 위에서 수지 계열 → 그레이드를 선택하세요.")

    # Save button
    col_save1, col_save2 = st.columns([1, 3])
    with col_save1:
        if st.button("💾 재질 정보 저장 → machine_spec.json", key="save_material"):
            _sync_material_to_spec(WORKSPACE_ROOT, st.session_state)
            st.success(f"✅ '{selected_grade}' → machine_spec.json 저장 완료")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section B: Inline Charts (Viscosity + PVT)
    # ==================================================================
    if st.session_state.get("selected_material_name"):
        props = st.session_state.get("material_properties", {})
        wlf = props.get("CrossWLF", {})
        tait = props.get("Tait", {})

        if wlf or tait:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.subheader(f"📈 3-B. 재질 물성 그래프: {props.get('_grade_name', selected_grade)}")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                if wlf:
                    st.markdown("#### 🌊 Cross-WLF 점도 곡선 (Viscosity)")
                    melt_T = st.number_input(
                        "📌 시각화 온도 (K)",
                        min_value=300.0, max_value=800.0,
                        value=float(st.session_state.get("mat_melt_temp_k", 563.15)),
                        step=10.0, format="%.1f",
                        key="mat_viz_melt_temp",
                        help="점도 그래프 시각화 온도. 실제 사출 온도로 설정 권장.",
                    )
                    st.session_state["mat_melt_temp_k"] = melt_T
                    _render_viscosity_chart(wlf, melt_T)
                else:
                    st.info("Cross-WLF 데이터 없음")

            with chart_col2:
                if tait:
                    st.markdown("#### 📉 Tait PVT 곡선 (Specific Volume)")
                    _render_pvt_chart(tait)
                else:
                    st.info("Tait PVT 데이터 없음")

            st.markdown('</div>', unsafe_allow_html=True)

        # ==================================================================
        # Section C: Material Property Detail Browser
        # ==================================================================
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader(f"📋 3-C. 물성 상세 — {props.get('_grade_name', selected_grade)}")

        prop_tab1, prop_tab2, prop_tab3, prop_tab4 = st.tabs([
            "🌊 Cross-WLF", "📉 Tait PVT", "🔥 Thermal", "⚙️ Mechanical"
        ])

        with prop_tab1:
            wlf = props.get("CrossWLF", {})
            if wlf:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("n (Power-law)", f"{wlf.get('n', 'N/A')}")
                c2.metric("τ* (Pa)", f"{wlf.get('tau_star', 0):.2e}")
                c3.metric("D1 (Pa·s)", f"{wlf.get('D1', 0):.2e}")
                c4.metric("D2 (K)", f"{wlf.get('D2', 'N/A')}")
                c5, c6 = st.columns(2)
                c5.metric("A1", f"{wlf.get('A1', 'N/A')}")
                c6.metric("A2 (K)", f"{wlf.get('A2', 'N/A')}")
            else:
                st.info("Cross-WLF 데이터 없음")

        with prop_tab2:
            tait = props.get("Tait", {})
            if tait:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("b1m (m³/kg)", f"{tait.get('b1m', 'N/A')}")
                c2.metric("b2m (m³/kg·K)", f"{tait.get('b2m', 0):.2e}")
                c3.metric("b3m (Pa)", f"{tait.get('b3m', 0):.2e}")
                c4.metric("b4m (1/K)", f"{tait.get('b4m', 'N/A')}")
                c5, c6 = st.columns(2)
                c5.metric("b5 / Tm (K)", f"{tait.get('b5', 'N/A')}")
                c6.metric("C (Tait)", f"{tait.get('C_tait', 'N/A')}")
            else:
                st.info("Tait PVT 데이터 없음")

        with prop_tab3:
            thermal = props.get("Thermal", {})
            if thermal:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Cp (J/kg·K)", f"{thermal.get('Cp_poly', 'N/A')}")
                c2.metric("k (W/m·K)", f"{thermal.get('k_poly', 'N/A')}")
                tg_c = thermal.get("Tg", 273.15) - 273.15
                tm_c = thermal.get("Tm", 273.15) - 273.15
                c3.metric("Tg", f"{thermal.get('Tg', 'N/A')} K ({tg_c:.0f}°C)")
                c4.metric("Tm", f"{thermal.get('Tm', 'N/A')} K ({tm_c:.0f}°C)")
            else:
                st.info("열물성 데이터 없음")

        with prop_tab4:
            mech = props.get("Mechanical", {})
            if mech:
                c1, c2, c3 = st.columns(3)
                c1.metric("Young's Modulus (MPa)", f"{mech.get('YoungsModulus', 'N/A')}")
                c2.metric("Poisson's Ratio", f"{mech.get('PoissonsRatio', 'N/A')}")
                cte = mech.get("CTE", 0)
                c3.metric("CTE (1/K)", f"{cte:.2e}")
            else:
                st.info("기계물성 데이터 없음")

            # Additives (if any)
            additive = props.get("Additives", {})
            if additive:
                st.markdown("---")
                st.markdown("**🔩 충전재 (Additives)**")
                ca1, ca2, ca3 = st.columns(3)
                ca1.metric("충전재 종류", additive.get("filler_name", "N/A"))
                ca2.metric("중량 분율 (wt%)", f"{additive.get('weight_fraction', 0)*100:.1f}%")
                ca3.metric("종횡비 (Aspect Ratio)", f"{additive.get('aspect_ratio', 'N/A')}")

        # Full JSON raw viewer
        with st.expander("🔍 전체 재질 JSON 원시 데이터 보기", expanded=False):
            display_props = {k: v for k, v in props.items() if not k.startswith("_")}
            st.json(display_props)

        st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section D: Material DB Tools
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🛠 3-D. Material Database Tools")

    col_t1, col_t2, col_t3 = st.columns(3)

    with col_t1:
        if st.button("🤖 AI Material Synthesizer", key="ai_mat"):
            with st.spinner("AI 재질 합성 중..."):
                try:
                    run_module("ai_material_synthesizer.py", raise_on_error=True)
                    st.success("AI 재질 합성 완료. DB를 새로고침하세요.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"AI 합성 실패: {e}")

    with col_t2:
        if st.button("📚 Material DB Manager", key="mat_db_mgr"):
            with st.spinner("DB 관리자 실행 중..."):
                try:
                    run_module("material_db_manager.py", raise_on_error=True)
                    st.success("재질 DB 관리 완료")
                except Exception as e:
                    st.error(f"DB 관리자 실패: {e}")

    with col_t3:
        if st.button("🔬 Material Finetuner", key="mat_fine"):
            with st.spinner("재질 미세조정 중..."):
                try:
                    run_module("material_finetuner.py", raise_on_error=True)
                    st.success("재질 미세조정 완료")
                except Exception as e:
                    st.error(f"Finetuner 실패: {e}")

    st.markdown("---")
    if st.session_state.get("material_selected"):
        st.success(f"✅ 재질 설정 완료: {st.session_state.get('selected_material_name', '')}")
    else:
        st.info("ℹ 재질을 선택하고 '재질 정보 저장' 버튼을 눌러 진행하세요.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section E: ⚙️ Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 재질 물성 수동 미세조정", expanded=False):
        st.markdown("##### 🔬 CrossWLF 파라미터 수동 입력 (전문가 전용)")
        st.caption("DB 값을 직접 오버라이드합니다. 정확한 물성 데이터가 있을 때만 수정하세요.")

        props = st.session_state.get("material_properties", {})
        wlf = props.get("CrossWLF", {})

        col_adv1, col_adv2, col_adv3 = st.columns(3)
        with col_adv1:
            n_override = st.number_input(
                "n (Power-law index)",
                min_value=0.01, max_value=1.0,
                value=float(wlf.get("n", 0.3)),
                step=0.01, format="%.3f",
                help="전단박화 지수. 1에 가까울수록 뉴튼 유체.",
                key="adv_wlf_n",
            )
        with col_adv2:
            tau_override = st.number_input(
                "τ* — Cross Stress (Pa)",
                min_value=1000.0, max_value=1e7,
                value=float(wlf.get("tau_star", 180000.0)),
                step=1000.0, format="%.0f",
                key="adv_wlf_tau",
            )
        with col_adv3:
            d2_override = st.number_input(
                "D2 — Reference Temp (K)",
                min_value=200.0, max_value=700.0,
                value=float(wlf.get("D2", 413.15)),
                step=1.0, format="%.2f",
                key="adv_wlf_d2",
            )

        if st.button("🔄 수동 물성값 세션에 적용", key="apply_adv_material"):
            if "material_properties" in st.session_state:
                if "CrossWLF" not in st.session_state["material_properties"]:
                    st.session_state["material_properties"]["CrossWLF"] = {}
                st.session_state["material_properties"]["CrossWLF"]["n"] = n_override
                st.session_state["material_properties"]["CrossWLF"]["tau_star"] = tau_override
                st.session_state["material_properties"]["CrossWLF"]["D2"] = d2_override
                st.success("✅ 수동 CrossWLF 값 적용됨 (세션 내 유지, 저장 필요)")