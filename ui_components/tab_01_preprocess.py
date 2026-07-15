# -*- coding: utf-8 -*-
"""Tab 1: Pre-process -- STL Upload (w/ Bounding Box), Machine Specs, Gate Configuration
   OVERHAUL v2.0: Explicit file_uploader, binary STL bbox parser, Advanced Options toggle,
   real-time session_state → machine_spec.json serialization.
"""
import streamlit as st
import json
import struct
import numpy as np
from pathlib import Path
from core_utils.subprocess_utils import run_module, self_heal_or_skip


# ==================================================================
# Helpers: STL Bounding Box Parser (no external libs required)
# ==================================================================

def _parse_stl_bbox(stl_bytes: bytes) -> dict | None:
    """
    Parse a binary or ASCII STL file and compute 3D bounding box.

    Returns dict with keys: dx_mm, dy_mm, dz_mm, x_min, x_max, y_min, y_max, z_min, z_max
    All values are in the unit embedded in the STL (typically mm).
    Returns None on parse failure.
    """
    try:
        # Try binary STL first (more common)
        if len(stl_bytes) < 84:
            return None

        n_tri = struct.unpack_from('<I', stl_bytes, 80)[0]
        expected_size = 84 + n_tri * 50
        if len(stl_bytes) < expected_size:
            raise ValueError("Not binary STL or truncated")

        verts = []
        offset = 84
        for _ in range(n_tri):
            for v in range(3):
                x, y, z = struct.unpack_from('<fff', stl_bytes, offset + 12 + v * 12)
                verts.append((x, y, z))
            offset += 50

        if not verts:
            return None

        arr = np.array(verts, dtype=np.float32)
        return {
            "x_min": float(arr[:, 0].min()),
            "x_max": float(arr[:, 0].max()),
            "y_min": float(arr[:, 1].min()),
            "y_max": float(arr[:, 1].max()),
            "z_min": float(arr[:, 2].min()),
            "z_max": float(arr[:, 2].max()),
            "dx_mm": float(np.ptp(arr[:, 0])),
            "dy_mm": float(np.ptp(arr[:, 1])),
            "dz_mm": float(np.ptp(arr[:, 2])),
            "n_triangles": n_tri,
        }

    except Exception:
        # Fallback: try ASCII STL
        try:
            text = stl_bytes.decode("utf-8", errors="ignore")
            xs, ys, zs = [], [], []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("vertex "):
                    parts = line.split()
                    xs.append(float(parts[1]))
                    ys.append(float(parts[2]))
                    zs.append(float(parts[3]))
            if not xs:
                return None
            return {
                "x_min": min(xs), "x_max": max(xs),
                "y_min": min(ys), "y_max": max(ys),
                "z_min": min(zs), "z_max": max(zs),
                "dx_mm": max(xs) - min(xs),
                "dy_mm": max(ys) - min(ys),
                "dz_mm": max(zs) - min(zs),
                "n_triangles": len(xs) // 3,
            }
        except Exception:
            return None


def _render_bbox_metrics(filename: str, bbox: dict):
    """Render bounding box metrics in a compact 3-column layout."""
    st.markdown(f"**📦 `{filename}` — Bounding Box**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("X (mm)", f"{bbox['dx_mm']:.2f}")
    c2.metric("Y (mm)", f"{bbox['dy_mm']:.2f}")
    c3.metric("Z (mm)", f"{bbox['dz_mm']:.2f}")
    vol_cm3 = (bbox['dx_mm'] * bbox['dy_mm'] * bbox['dz_mm']) / 1000.0
    c4.metric("Vol (cm³)", f"{vol_cm3:.2f}")
    st.caption(
        f"X [{bbox['x_min']:.3f} → {bbox['x_max']:.3f}]  "
        f"Y [{bbox['y_min']:.3f} → {bbox['y_max']:.3f}]  "
        f"Z [{bbox['z_min']:.3f} → {bbox['z_max']:.3f}]  "
        f"Triangles: {bbox.get('n_triangles', '?'):,}"
    )


# ==================================================================
# Helpers: machine_spec.json Serialization
# ==================================================================

def _sync_machine_spec(WORKSPACE_ROOT: Path, session_state: dict):
    """Serialize all machine + STL path session_state → machine_spec.json (real-time)."""
    spec_path = WORKSPACE_ROOT / "machine_spec.json"
    existing = {}
    if spec_path.exists():
        try:
            existing = json.loads(spec_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Core machine specs
    existing["clamping_force_ton"] = session_state.get("clamping_force_ton", 250.0)
    existing["screw_diameter_mm"] = session_state.get("screw_diameter_mm", 25.0)
    existing["max_injection_pressure_mpa"] = session_state.get("max_injection_pressure_mpa", 180.0)
    existing["projected_area_m2"] = session_state.get("projected_area_m2", 0.01125)

    # Advanced machine specs
    existing["n_cavities"] = session_state.get("n_cavities", 1)
    existing["n_gates"] = session_state.get("n_gates", 1)
    existing["runner_diameter_mm"] = session_state.get("runner_diameter_mm", 6.0)
    existing["hot_runner_enabled"] = session_state.get("hot_runner_enabled", False)
    existing["valve_gate_count"] = session_state.get("valve_gate_count", 0)

    # STL file paths (cached upload paths)
    existing["cavity_stl_paths"] = session_state.get("cavity_stl_paths", [])
    existing["insert_stl_paths"] = session_state.get("insert_stl_paths", [])

    spec_path.write_text(
        json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8"
    )
    session_state["machine_spec_modified"] = True


# ==================================================================
# Main Render Function
# ==================================================================

def render(WORKSPACE_ROOT, SPEC_JSON, case_dir, session_state):
    """Render Tab 1: Pre-process."""

    # ── Query Params Synchronizer (Sync Gate Coordinates from WebGL Viewer) ──
    query_params = st.query_params
    if "sync_gates" in query_params and "coords" in query_params:
        coords_str = query_params["coords"]
        try:
            parsed_coords = []
            for pair in coords_str.split('|'):
                if not pair.strip():
                    continue
                parts = pair.split(',')
                parsed_coords.append({
                    "x": float(parts[0]),
                    "y": float(parts[1]),
                    "z": float(parts[2])
                })
            session_state["manual_gate_coords"] = parsed_coords
            session_state["n_gates"] = len(parsed_coords)
            
            # Sync directly to machine_spec.json
            spec_path = Path(WORKSPACE_ROOT) / "machine_spec.json"
            existing = {}
            if spec_path.exists():
                try:
                    existing = json.loads(spec_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            existing["gate_pick_mode"] = "Expert_Manual"
            existing["manual_gate_coords"] = parsed_coords
            existing["n_gates"] = len(parsed_coords)
            spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
            
            session_state["preprocess_gate_conf"] = {"manual_gate_coords": parsed_coords}
            session_state["machine_spec_modified"] = True
            
            # Clear params to avoid loop
            st.query_params.clear()
            st.toast("🎯 3D 뷰어에서 픽한 게이트 좌표가 동기화되었습니다!", icon="🎉")
            st.rerun()
        except Exception as e:
            st.error(f"Gate Sync Error: {e}")

    # ── Session State Defaults ─────────────────────────────────────
    session_state.setdefault("preprocess_mesh_ok", False)
    session_state.setdefault("preprocess_geo_ok", False)
    session_state.setdefault("preprocess_gate_conf", {})
    session_state.setdefault("cavity_stl_paths", [])
    session_state.setdefault("insert_stl_paths", [])
    session_state.setdefault("cavity_bbox_list", [])
    session_state.setdefault("insert_bbox_list", [])
    session_state.setdefault("clamping_force_ton", 250.0)
    session_state.setdefault("screw_diameter_mm", 25.0)
    session_state.setdefault("max_injection_pressure_mpa", 180.0)
    session_state.setdefault("projected_area_m2", 0.01125)
    session_state.setdefault("n_cavities", 1)
    session_state.setdefault("n_gates", 1)
    session_state.setdefault("runner_diameter_mm", 6.0)
    session_state.setdefault("hot_runner_enabled", False)
    session_state.setdefault("valve_gate_count", 0)
    session_state.setdefault("machine_spec_modified", False)

    WORKSPACE_ROOT = Path(WORKSPACE_ROOT)

    # ==================================================================
    # Section A: STL File Upload — Cavity & Insert
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("📐 1-A. STL Geometry Upload  (Cavity & Insert)")
    st.caption("CAD 파일(.stl)을 드래그 앤 드롭하거나 클릭하여 업로드하세요. "
               "업로드 즉시 바운딩 박스 크기가 자동 계산됩니다.")

    col_cav, col_ins = st.columns(2)

    # ── Cavity STL ──────────────────────────────────────────────────
    with col_cav:
        st.markdown("#### 🏭 Cavity STL Files")
        cavity_files = st.file_uploader(
            "Cavity STL(s) 업로드 — 여러 파일 동시 선택 가능",
            type=["stl"],
            accept_multiple_files=True,
            key="cavity_uploader",
            help="금형 캐비티 형상 STL 파일. 다중 캐비티의 경우 여러 파일을 동시에 선택하세요.",
        )

        if cavity_files:
            upload_dir = WORKSPACE_ROOT / "uploads" / "cavity"
            upload_dir.mkdir(parents=True, exist_ok=True)
            saved_paths = []
            bbox_list = []
            for f in cavity_files:
                dest = upload_dir / f.name
                raw = f.getbuffer()
                dest.write_bytes(raw)
                saved_paths.append(str(dest))
                bbox = _parse_stl_bbox(bytes(raw))
                bbox_list.append(bbox)

            session_state["cavity_stl_paths"] = saved_paths
            session_state["cavity_bbox_list"] = bbox_list
            _sync_machine_spec(WORKSPACE_ROOT, session_state)

            st.success(f"✅ {len(saved_paths)}개 Cavity STL 업로드 완료")
            for fname, bbox in zip([f.name for f in cavity_files], bbox_list):
                if bbox:
                    _render_bbox_metrics(fname, bbox)
                else:
                    st.warning(f"⚠ `{fname}`: Bounding Box 파싱 실패 (파일 형식 확인 필요)")

        elif session_state["cavity_stl_paths"]:
            st.info(f"📁 {len(session_state['cavity_stl_paths'])}개 Cavity STL 로드됨")
            for i, (p, bbox) in enumerate(
                zip(session_state["cavity_stl_paths"], session_state.get("cavity_bbox_list", []))
            ):
                st.caption(f"  • {Path(p).name}")
                if bbox:
                    _render_bbox_metrics(Path(p).name, bbox)
        else:
            st.info("⬆ 위 업로드 영역에 Cavity STL 파일을 드래그하세요.")

    # ── Insert STL ──────────────────────────────────────────────────
    with col_ins:
        st.markdown("#### 🔩 Insert STL Files")
        insert_files = st.file_uploader(
            "Insert STL(s) 업로드 — 다중 Insert 동시 업로드 지원",
            type=["stl"],
            accept_multiple_files=True,
            key="insert_uploader",
            help="인서트, 코어, 슬라이드 등 부품 형상 STL 파일. 복수의 파트를 동시에 업로드 가능합니다.",
        )

        if insert_files:
            upload_dir = WORKSPACE_ROOT / "uploads" / "insert"
            upload_dir.mkdir(parents=True, exist_ok=True)
            saved_paths = []
            bbox_list = []
            for f in insert_files:
                dest = upload_dir / f.name
                raw = f.getbuffer()
                dest.write_bytes(raw)
                saved_paths.append(str(dest))
                bbox = _parse_stl_bbox(bytes(raw))
                bbox_list.append(bbox)

            session_state["insert_stl_paths"] = saved_paths
            session_state["insert_bbox_list"] = bbox_list
            _sync_machine_spec(WORKSPACE_ROOT, session_state)

            st.success(f"✅ {len(saved_paths)}개 Insert STL 업로드 완료")
            for fname, bbox in zip([f.name for f in insert_files], bbox_list):
                if bbox:
                    _render_bbox_metrics(fname, bbox)
                else:
                    st.warning(f"⚠ `{fname}`: Bounding Box 파싱 실패")

        elif session_state["insert_stl_paths"]:
            st.info(f"📁 {len(session_state['insert_stl_paths'])}개 Insert STL 로드됨")
            for p, bbox in zip(
                session_state["insert_stl_paths"],
                session_state.get("insert_bbox_list", [])
            ):
                st.caption(f"  • {Path(p).name}")
                if bbox:
                    _render_bbox_metrics(Path(p).name, bbox)
        else:
            st.info("⬆ Insert/Core 파트 STL 파일을 드래그하세요. (선택사항)")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section B: Machine & Mold Specifications (Required Inputs)
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("⚙️ 1-B. Machine & Mold Specifications  [필수 입력]")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    with col_m1:
        new_ton = st.number_input(
            "🔒 형개력 — Clamping Force (Ton)",
            min_value=10.0, max_value=5000.0,
            value=float(session_state.get("clamping_force_ton", 250.0)),
            step=10.0, format="%.1f",
            help="사출기 형개력 (톤 단위). 예: 소형 50T, 중형 250T, 대형 2000T",
            key="input_clamping_force",
        )
        if new_ton != session_state.get("clamping_force_ton"):
            session_state["clamping_force_ton"] = new_ton
            _sync_machine_spec(WORKSPACE_ROOT, session_state)

    with col_m2:
        new_screw = st.number_input(
            "🔩 스크류 직경 — Screw Diameter (mm)",
            min_value=10.0, max_value=200.0,
            value=float(session_state.get("screw_diameter_mm", 25.0)),
            step=1.0, format="%.1f",
            help="사출 스크류 직경 (mm). 보통 20~100mm 범위",
            key="input_screw_diameter",
        )
        if new_screw != session_state.get("screw_diameter_mm"):
            session_state["screw_diameter_mm"] = new_screw
            _sync_machine_spec(WORKSPACE_ROOT, session_state)

    with col_m3:
        new_pressure = st.number_input(
            "💥 최대 사출 압력 — Max Injection Pressure (MPa)",
            min_value=10.0, max_value=500.0,
            value=float(session_state.get("max_injection_pressure_mpa", 180.0)),
            step=5.0, format="%.1f",
            help="사출기 최대 사출 압력 (MPa). 예: 180~220 MPa",
            key="input_max_pressure",
        )
        if new_pressure != session_state.get("max_injection_pressure_mpa"):
            session_state["max_injection_pressure_mpa"] = new_pressure
            _sync_machine_spec(WORKSPACE_ROOT, session_state)

    with col_m4:
        new_area = st.number_input(
            "📏 투영 면적 — Projected Area (m²)",
            min_value=0.0001, max_value=10.0,
            value=float(session_state.get("projected_area_m2", 0.01125)),
            step=0.001, format="%.6f",
            help="캐비티 투영 면적 (m²). 형개력 검증에 사용됨",
            key="input_projected_area",
        )
        if new_area != session_state.get("projected_area_m2"):
            session_state["projected_area_m2"] = new_area
            _sync_machine_spec(WORKSPACE_ROOT, session_state)

    # Derived metrics
    st.markdown("---")
    st.markdown("**📊 자동 계산 파라미터 (Derived)**")
    col_d1, col_d2, col_d3, col_d4 = st.columns(4)
    clamp_ton = session_state.get("clamping_force_ton", 250.0)
    proj_area = session_state.get("projected_area_m2", 0.01125)
    screw_d = session_state.get("screw_diameter_mm", 25.0)
    max_p = session_state.get("max_injection_pressure_mpa", 180.0)

    with col_d1:
        st.metric("비클램프 압력 (ton/m²)", f"{clamp_ton / max(proj_area, 1e-9):,.0f}")
    with col_d2:
        st.metric("형개력 (kN)", f"{clamp_ton * 9.80665:,.1f}")
    with col_d3:
        screw_area = 3.14159 * (screw_d / 2000.0) ** 2  # m²
        est_force = max_p * 1e6 * screw_area / 1000.0  # kN
        st.metric("추정 사출력 (kN)", f"{est_force:,.1f}")
    with col_d4:
        st.metric("최대 캐비티 압력 (MPa)", f"{max_p:.1f}")

    if st.button("💾 machine_spec.json 저장", key="save_machine_spec"):
        _sync_machine_spec(WORKSPACE_ROOT, session_state)
        st.success("✅ machine_spec.json 저장 완료")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section C: Gate Configuration — Auto-Wizard / Expert Manual Pick
    # ==================================================================
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🎯 1-C. Gate Configuration")

    # ── Mode Toggle ─────────────────────────────────────────────────
    session_state.setdefault("gate_pick_mode", "🤖 Auto-Wizard (자동 탐색)")
    session_state.setdefault("manual_gate_coords", [])

    gate_mode = st.radio(
        "게이트 지정 방식 선택",
        options=["🤖 Auto-Wizard (자동 탐색)", "✋ Expert Manual (수동 좌표 지정)"],
        index=0 if session_state["gate_pick_mode"] == "🤖 Auto-Wizard (자동 탐색)" else 1,
        horizontal=True,
        key="gate_mode_radio",
        help="Auto-Wizard는 AI 알고리즘으로 최적 위치를 탐색합니다. Expert Manual은 3D 뷰어에서 좌표를 직접 입력합니다.",
    )
    session_state["gate_pick_mode"] = gate_mode

    # ================================================================
    # Mode A: Auto-Wizard
    # ================================================================
    if gate_mode == "🤖 Auto-Wizard (자동 탐색)":
        col_geo1, col_geo2 = st.columns(2)

        with col_geo1:
            st.markdown("**📐 Geometry & Mesh**")
            if st.button("📐 Generate STL Mesh", key="gen_stl"):
                with st.spinner("stl_mesher.py 실행 중..."):
                    try:
                        run_module("stl_mesher.py", raise_on_error=True)
                        session_state["preprocess_mesh_ok"] = True
                        st.success("STL Mesh 생성 완료")
                    except Exception as e:
                        st.error(f"STL 생성 실패: {e}")

            if st.button("🔍 CAD Cleaner (Heal)", key="cad_clean"):
                with st.spinner("CAD 힐링 실행 중..."):
                    try:
                        run_module("cad_cleaner.py", raise_on_error=True)
                        session_state["preprocess_geo_ok"] = True
                        st.success("CAD 힐링 완료")
                    except Exception as e:
                        st.error(f"CAD 힐링 실패: {e}")

            st.markdown("**🎯 Auto Gate Picker**")
            if SPEC_JSON.exists():
                try:
                    specs = json.loads(SPEC_JSON.read_text(encoding="utf-8"))
                    gate_conf = specs.get("gate_config", specs.get("gate_picker", {}))
                    session_state["preprocess_gate_conf"] = gate_conf
                    if gate_conf:
                        with st.expander("📋 현재 자동 게이트 설정", expanded=False):
                            st.json(gate_conf)
                except Exception:
                    pass

            if st.button("🎯 Run Auto Gate Picker", key="gate_pick"):
                with st.spinner("최적 게이트 위치 AI 분석 중..."):
                    try:
                        run_module("gate_picker.py", raise_on_error=True)
                        st.success("게이트 위치 최적화 완료")
                        st.rerun()
                    except Exception as e:
                        st.error(f"게이트 탐색 실패: {e}")

            if st.button("🧩 Adaptive Mesher", key="adp_mesh"):
                with st.spinner("적응형 격자 생성 중..."):
                    try:
                        run_module("adaptive_mesher.py", raise_on_error=True)
                        st.success("적응형 격자 생성 완료")
                    except Exception as e:
                        st.error(f"적응형 격자 실패: {e}")

        with col_geo2:
            st.markdown("**📊 현재 machine_spec.json 요약**")
            if SPEC_JSON.exists():
                try:
                    specs = json.loads(SPEC_JSON.read_text(encoding="utf-8"))
                    st.metric("투영 면적", f"{specs.get('projected_area_m2', 0):.6f} m²")
                    st.metric("형개력", f"{specs.get('clamping_force_ton', 0):.1f} Ton")
                    st.metric("최대 사출 압력", f"{specs.get('max_injection_pressure_mpa', 0):.1f} MPa")
                    st.metric("캐비티 STL 수", f"{len(specs.get('cavity_stl_paths', []))}")
                    st.metric("인서트 STL 수", f"{len(specs.get('insert_stl_paths', []))}")
                except Exception:
                    st.warning("machine_spec.json 읽기 오류")
            else:
                st.warning("machine_spec.json 없음")

    # ================================================================
    # Mode B: Expert Manual Gate Pick (3D Interactive WebGL Viewer)
    # ================================================================
    else:
        st.markdown("#### ✋ 수동 게이트 위치 지정 — 3D Interactive WebGL Viewer")
        st.caption("업로드된 Cavity STL을 마우스로 자유롭게 **회전/이동/확대**하고, 원하는 위치를 **더블 클릭**하여 게이트 좌표를 픽하세요.")

        # ── Cavity STL path resolution ───────────────────────────────
        cavity_paths = session_state.get("cavity_stl_paths", [])
        stl_path_to_render = None
        if cavity_paths:
            stl_path_to_render = Path(cavity_paths[0])
        else:
            # Fallback: scan uploads/cavity directory
            upload_cav_dir = WORKSPACE_ROOT / "uploads" / "cavity"
            if upload_cav_dir.exists():
                stl_files = list(upload_cav_dir.glob("*.stl"))
                if stl_files:
                    stl_path_to_render = stl_files[0]

        # ── 3D WebGL Viewer ──────────────────────────────────────────
        if stl_path_to_render and stl_path_to_render.exists():
            import base64
            try:
                # Read and base64-encode STL file for client-side loading
                stl_bytes = stl_path_to_render.read_bytes()
                stl_base64 = base64.b64encode(stl_bytes).decode('utf-8')
                
                n_manual_gates = int(session_state.get("n_gates", 1))
                manual_gates_coords = session_state.get("manual_gate_coords", [])
                
                # Render Three.js WebGL Application
                html_template = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <style>
                        body {{ margin: 0; padding: 0; overflow: hidden; background-color: #0f172a; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #f1f5f9; }}
                        #canvas-container {{ width: 100vw; height: 100vh; position: relative; }}
                        /* Premium Glassmorphism Control Panel */
                        #control-panel {{
                            position: absolute;
                            top: 20px;
                            right: 20px;
                            width: 250px;
                            background: rgba(30, 41, 59, 0.75);
                            backdrop-filter: blur(12px);
                            border: 1px solid rgba(255, 255, 255, 0.08);
                            border-radius: 12px;
                            padding: 16px;
                            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
                            z-index: 100;
                        }}
                        h3 {{ margin-top: 0; margin-bottom: 12px; font-size: 15px; font-weight: 700; color: #38bdf8; background: linear-gradient(135deg, #38bdf8, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
                        .gate-row {{
                            display: flex;
                            justify-content: space-between;
                            align-items: center;
                            margin-bottom: 8px;
                            padding: 8px 10px;
                            border-radius: 8px;
                            background: rgba(15, 23, 42, 0.5);
                            font-size: 12px;
                            cursor: pointer;
                            border: 1px solid transparent;
                            transition: all 0.2s;
                        }}
                        .gate-row:hover {{
                            background: rgba(15, 23, 42, 0.8);
                            border-color: rgba(56, 189, 248, 0.3);
                        }}
                        .gate-row.active {{
                            background: rgba(56, 189, 248, 0.15);
                            border-color: #38bdf8;
                        }}
                        .gate-badge {{
                            font-weight: 700;
                            padding: 2px 8px;
                            border-radius: 6px;
                            color: white;
                            font-size: 10px;
                        }}
                        .gate-coords {{ font-family: monospace; color: #94a3b8; }}
                        .gate-coords.set {{ color: #38bdf8; font-weight: bold; }}
                        button {{
                            width: 100%;
                            padding: 10px;
                            border-radius: 8px;
                            border: none;
                            background: linear-gradient(135deg, #0284c7, #7c3aed);
                            color: white;
                            font-weight: bold;
                            font-size: 13px;
                            cursor: pointer;
                            margin-top: 12px;
                            transition: opacity 0.2s;
                            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
                        }}
                        button:hover {{ opacity: 0.9; }}
                        #instructions {{
                            position: absolute;
                            bottom: 20px;
                            left: 20px;
                            background: rgba(15, 23, 42, 0.8);
                            padding: 8px 16px;
                            border-radius: 20px;
                            font-size: 12px;
                            color: #94a3b8;
                            border: 1px solid rgba(255, 255, 255, 0.05);
                            pointer-events: none;
                        }}
                        #instructions span {{ color: #38bdf8; font-weight: bold; }}
                    </style>
                    <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
                    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
                    <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js"></script>
                </head>
                <body>
                    <div id="canvas-container">
                        <div id="control-panel">
                            <h3>🎯 3D Interactive Picker</h3>
                            <div style="font-size:11px; color:#94a3b8; margin-bottom:12px;">게이트 클릭 후, 모델 위를 <b>더블 클릭</b>하여 지정하세요.</div>
                            <div id="gate-list"></div>
                            <button onclick="saveAndSync()">💾 Apply Gate Positions</button>
                        </div>
                        <div id="instructions">🖱️ 좌드래그: <span>회전</span> | 우드래그: <span>이동</span> | 휠: <span>줌</span> | 더블 클릭: <span>게이트 픽</span></div>
                    </div>

                    <script>
                        let nGates = {n_manual_gates};
                        let activeGateIndex = 0;
                        let gatesData = [];
                        const gateColors = ["#f97316", "#a855f7", "#22c55e", "#ef4444", "#eab308", "#06b6d4", "#ec4899", "#84cc16"];
                        
                        const stlBase64 = "{stl_base64}";
                        const initialGates = {json.dumps(manual_gates_coords)};

                        // Init state
                        for (let i = 0; i < nGates; i++) {{
                            if (initialGates[i]) {{
                                gatesData.push({{ x: initialGates[i].x, y: initialGates[i].y, z: initialGates[i].z }});
                            }} else {{
                                gatesData.push(null);
                            }}
                        }}

                        function renderGateList() {{
                            const listEl = document.getElementById("gate-list");
                            listEl.innerHTML = "";
                            for (let i = 0; i < nGates; i++) {{
                                const row = document.createElement("div");
                                row.className = `gate-row ${{i === activeGateIndex ? "active" : ""}}`;
                                row.onclick = () => selectGate(i);
                                
                                const badge = document.createElement("span");
                                badge.className = "gate-badge";
                                badge.style.backgroundColor = gateColors[i % gateColors.length];
                                badge.innerText = `Gate ${{i+1}}`;
                                
                                const coords = document.createElement("span");
                                const g = gatesData[i];
                                if (g) {{
                                    coords.className = "gate-coords set";
                                    coords.innerText = `${{g.x.toFixed(1)}}, ${{g.y.toFixed(1)}}, ${{g.z.toFixed(1)}}`;
                                }} else {{
                                    coords.className = "gate-coords";
                                    coords.innerText = "Double Click Model";
                                }}
                                
                                row.appendChild(badge);
                                row.appendChild(coords);
                                listEl.appendChild(row);
                            }}
                        }}

                        function selectGate(index) {{
                            activeGateIndex = index;
                            renderGateList();
                        }}

                        // Scene Setup
                        const container = document.getElementById("canvas-container");
                        const scene = new THREE.Scene();
                        scene.background = new THREE.Color(0x0f172a);

                        const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 1000);
                        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
                        renderer.setSize(window.innerWidth, window.innerHeight);
                        renderer.setPixelRatio(window.devicePixelRatio);
                        renderer.shadowMap.enabled = true;
                        container.appendChild(renderer.domElement);

                        const controls = new THREE.OrbitControls(camera, renderer.domElement);
                        controls.enableDamping = true;
                        controls.dampingFactor = 0.05;

                        // Lights
                        const ambientLight = new THREE.AmbientLight(0x334155, 1.5);
                        scene.add(ambientLight);

                        const dirLight = new THREE.DirectionalLight(0xffffff, 2.0);
                        dirLight.position.set(200, 400, 200);
                        scene.add(dirLight);

                        const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 1.0);
                        dirLight2.position.set(-200, -200, -200);
                        scene.add(dirLight2);

                        // Load STL
                        function base64ToArrayBuffer(base64) {{
                            var binary_string = window.atob(base64);
                            var len = binary_string.length;
                            var bytes = new Uint8Array(len);
                            for (var i = 0; i < len; i++) {{
                                bytes[i] = binary_string.charCodeAt(i);
                            }}
                            return bytes.buffer;
                        }}

                        const arrayBuffer = base64ToArrayBuffer(stlBase64);
                        const loader = new THREE.STLLoader();
                        const geometry = loader.parse(arrayBuffer);
                        
                        const material = new THREE.MeshStandardMaterial({{
                            color: 0x38bdf8,
                            roughness: 0.4,
                            metalness: 0.1,
                            transparent: true,
                            opacity: 0.65,
                            side: THREE.DoubleSide
                        }});
                        
                        const mesh = new THREE.Mesh(geometry, material);
                        scene.add(mesh);

                        // Center Mesh
                        geometry.computeBoundingBox();
                        geometry.computeVertexNormals(); // Compute normals for correct shading and lighting
                        
                        const boundingBox = geometry.boundingBox;
                        const center = new THREE.Vector3();
                        boundingBox.getCenter(center);
                        mesh.position.sub(center);
                        
                        const size = new THREE.Vector3();
                        boundingBox.getSize(size);
                        const maxDim = Math.max(size.x, size.y, size.z);
                        
                        // Helpers
                        const gridHelper = new THREE.GridHelper(maxDim * 3, 50, 0x334155, 0x1e293b);
                        gridHelper.position.y = -size.y / 2 - 5;
                        scene.add(gridHelper);
                        
                        // Safe Camera Distance calculation (avoiding Math.tan(90deg) which yields Infinity)
                        const cameraDistance = maxDim * 2.0;
                        camera.position.set(cameraDistance, cameraDistance, cameraDistance);
                        camera.lookAt(0, 0, 0);
                        controls.target.set(0, 0, 0);
                        controls.update();

                        // Gate markers
                        const gateMarkers = {{}};

                        function createGateMarker(index, position) {{
                            if (gateMarkers[index]) {{
                                scene.remove(gateMarkers[index]);
                            }}
                            
                            const radius = maxDim * 0.025;
                            const markerGeo = new THREE.SphereGeometry(radius, 32, 32);
                            const markerMat = new THREE.MeshStandardMaterial({{
                                color: new THREE.Color(gateColors[index % gateColors.length]),
                                roughness: 0.2,
                                metalness: 0.8
                            }});
                            const markerMesh = new THREE.Mesh(markerGeo, markerMat);
                            markerMesh.position.copy(position);
                            scene.add(markerMesh);
                            gateMarkers[index] = markerMesh;
                        }}

                        // Render initial markers
                        for (let i = 0; i < nGates; i++) {{
                            const g = gatesData[i];
                            if (g) {{
                                const worldPos = new THREE.Vector3(g.x, g.y, g.z).sub(center);
                                createGateMarker(i, worldPos);
                            }}
                        }}

                        // Raycasting (Double Click Pick)
                        const raycaster = new THREE.Raycaster();
                        const mouse = new THREE.Vector2();

                        renderer.domElement.addEventListener('dblclick', (event) => {{
                            const rect = renderer.domElement.getBoundingClientRect();
                            mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
                            mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

                            raycaster.setFromCamera(mouse, camera);
                            const intersects = raycaster.intersectObject(mesh);

                            if (intersects.length > 0) {{
                                const intersection = intersects[0];
                                const localPoint = intersection.point.clone();
                                const originalCoords = localPoint.clone().add(center);

                                gatesData[activeGateIndex] = {{
                                    x: originalCoords.x,
                                    y: originalCoords.y,
                                    z: originalCoords.z
                                }};

                                createGateMarker(activeGateIndex, localPoint);
                                renderGateList();
                            }}
                        }});

                        window.saveAndSync = function() {{
                            try {{
                                // Filter only set gates
                                const validGates = gatesData.filter(g => g !== null);
                                if (validGates.length < nGates) {{
                                    if (!confirm(`일부 게이트(${{nGates - validGates.length}}개) 좌표가 지정되지 않았습니다. 동기화를 진행하시겠습니까?`)) {{
                                        return;
                                    }}
                                }}
                                
                                // Format coords string: x,y,z|x,y,z
                                const coordsStr = gatesData
                                    .map(g => g ? `${{g.x.toFixed(2)}},${{g.y.toFixed(2)}},${{g.z.toFixed(2)}}` : '0,0,0')
                                    .join('|');
                                
                                // Send postMessage to parent window to bypass iframe allowance sandboxing
                                window.parent.postMessage({{
                                    type: "SYNC_GATES_BRIDGE",
                                    coords: coordsStr
                                }}, "*");
                                
                                // Direct DOM fallback as backup
                                const parentDoc = window.parent.document;
                                const labelElements = Array.from(parentDoc.querySelectorAll('label'));
                                const gateInputPairs = [];
                                labelElements.forEach(lbl => {{
                                    const text = lbl.innerText || "";
                                    if (text.includes("X (mm)") || text.includes("Y (mm)") || text.includes("Z (mm)")) {{
                                        const parentContainer = lbl.parentElement;
                                        if (parentContainer) {{
                                            const inp = parentContainer.querySelector('input');
                                            if (inp) gateInputPairs.push({{ label: text, input: inp }});
                                        }}
                                    }}
                                }});
                                let pairIdx = 0;
                                for (let i = 0; i < nGates; i++) {{
                                    const g = gatesData[i];
                                    if (!g) continue;
                                    if (pairIdx + 2 < gateInputPairs.length) {{
                                        const xInp = gateInputPairs[pairIdx++].input;
                                        const yInp = gateInputPairs[pairIdx++].input;
                                        const zInp = gateInputPairs[pairIdx++].input;
                                        xInp.value = g.x.toFixed(2);
                                        yInp.value = g.y.toFixed(2);
                                        zInp.value = g.z.toFixed(2);
                                        [xInp, yInp, zInp].forEach(inp => {{
                                            inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                            inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                        }});
                                    }}
                                }}
                            }} catch (err) {{
                                console.error("Sync transmission failed:", err);
                            }}
                        }}

                        function animate() {{
                            requestAnimationFrame(animate);
                            controls.update();
                            renderer.render(scene, camera);
                        }}

                        renderGateList();
                        animate();

                        window.addEventListener('resize', () => {{
                            camera.aspect = window.innerWidth / window.innerHeight;
                            camera.updateProjectionMatrix();
                            renderer.setSize(window.innerWidth, window.innerHeight);
                        }});
                    </script>
                </body>
                </html>
                """
                
                # Render WebGL app via Streamlit component
                import streamlit.components.v1 as components
                components.html(html_template, height=520)
                
                # Embedded Parent-level postMessage Listener (Bypasses Sandbox Security completely)
                components.html("""
                <script>
                window.parent.addEventListener('message', function(event) {
                    if (event.data && event.data.type === 'SYNC_GATES_BRIDGE') {
                        // Exits iframe context to top-level window.location.search redirection
                        window.parent.location.search = '?sync_gates=true&coords=' + encodeURIComponent(event.data.coords);
                    }
                });
                </script>
                """, height=0, width=0)
                
                import pyvista as pv
                mesh = pv.read(str(stl_path_to_render))
                bounds = mesh.bounds
                
                st.caption(
                    f"📐 모델: **{stl_path_to_render.name}** | "
                    f"Bounds: X[{bounds[0]:.1f}~{bounds[1]:.1f}] "
                    f"Y[{bounds[2]:.1f}~{bounds[3]:.1f}] "
                    f"Z[{bounds[4]:.1f}~{bounds[5]:.1f}] mm"
                )

            except Exception as ex:
                st.warning(f"⚠️ WebGL 3D 시각화 로드 실패: {ex}")
        else:
            st.info(
                "⬆ **1-A 섹션에서 Cavity STL 파일을 먼저 업로드하세요.** "
                "업로드 후 이 화면에서 3D 모델이 렌더링됩니다."
            )

        # ── Manual Gate Coordinate Entry ─────────────────────────────
        st.markdown("---")
        st.markdown("##### 🎯 게이트 좌표 수동 입력")

        # Determine coordinate bounds from BBox for sensible defaults/limits
        x_default = y_default = z_default = 0.0
        x_min_hint = y_min_hint = z_min_hint = -9999.0
        x_max_hint = y_max_hint = z_max_hint = 9999.0
        if stl_path_to_render and stl_path_to_render.exists():
            try:
                _bbox_tmp = _parse_stl_bbox(stl_path_to_render.read_bytes())
                if _bbox_tmp:
                    x_default = round((_bbox_tmp["x_min"] + _bbox_tmp["x_max"]) / 2, 2)
                    y_default = round((_bbox_tmp["y_min"] + _bbox_tmp["y_max"]) / 2, 2)
                    z_default = round(_bbox_tmp["z_max"], 2)  # top face
                    x_min_hint, x_max_hint = _bbox_tmp["x_min"], _bbox_tmp["x_max"]
                    y_min_hint, y_max_hint = _bbox_tmp["y_min"], _bbox_tmp["y_max"]
                    z_min_hint, z_max_hint = _bbox_tmp["z_min"], _bbox_tmp["z_max"]
            except Exception:
                pass

        n_manual_gates = int(session_state.get("n_gates", 1))
        st.caption(f"게이트 수(N Gates) = **{n_manual_gates}** — Advanced Options에서 변경 가능")

        current_coords = session_state.get("manual_gate_coords", [])
        # Pad / trim to match n_gates
        while len(current_coords) < n_manual_gates:
            current_coords.append({"x": x_default, "y": y_default, "z": z_default})
        current_coords = current_coords[:n_manual_gates]

        updated_coords = []
        # Render in rows of 4
        cols_per_row = 4
        gate_indices = list(range(n_manual_gates))
        for row_start in range(0, n_manual_gates, cols_per_row):
            row_end = min(row_start + cols_per_row, n_manual_gates)
            row_cols = st.columns(row_end - row_start)
            for col_idx, gate_i in enumerate(range(row_start, row_end)):
                gc = current_coords[gate_i]
                with row_cols[col_idx]:
                    _GATE_COLORS_CSS = [
                        "#f97316", "#a855f7", "#22c55e", "#ef4444",
                        "#eab308", "#06b6d4", "#ec4899", "#84cc16",
                    ]
                    badge_color = _GATE_COLORS_CSS[gate_i % len(_GATE_COLORS_CSS)]
                    st.markdown(
                        f'<span style="background:{badge_color};color:#fff;'
                        f'padding:2px 10px;border-radius:12px;font-size:13px;font-weight:700;">'
                        f'Gate {gate_i+1}</span>',
                        unsafe_allow_html=True,
                    )
                    gx = st.number_input(
                        f"X (mm)", key=f"gate_{gate_i}_x",
                        value=float(gc.get("x", x_default)),
                        step=0.1, format="%.2f",
                    )
                    gy = st.number_input(
                        f"Y (mm)", key=f"gate_{gate_i}_y",
                        value=float(gc.get("y", y_default)),
                        step=0.1, format="%.2f",
                    )
                    gz = st.number_input(
                        f"Z (mm)", key=f"gate_{gate_i}_z",
                        value=float(gc.get("z", z_default)),
                        step=0.1, format="%.2f",
                    )
                    updated_coords.append({"x": gx, "y": gy, "z": gz})

        session_state["manual_gate_coords"] = updated_coords

        # ── Save to machine_spec.json ────────────────────────────────
        col_gs1, col_gs2 = st.columns([1, 3])
        with col_gs1:
            if st.button("💾 게이트 좌표 저장", key="save_manual_gates"):
                try:
                    spec_path = WORKSPACE_ROOT / "machine_spec.json"
                    existing = {}
                    if spec_path.exists():
                        existing = json.loads(spec_path.read_text(encoding="utf-8"))
                    existing["gate_pick_mode"] = "Expert_Manual"
                    existing["manual_gate_coords"] = updated_coords
                    existing["n_gates"] = n_manual_gates
                    spec_path.write_text(
                        json.dumps(existing, indent=4, ensure_ascii=False),
                        encoding="utf-8"
                    )
                    session_state["preprocess_gate_conf"] = {"manual_gate_coords": updated_coords}
                    session_state["machine_spec_modified"] = True
                    st.success(f"✅ {n_manual_gates}개 게이트 좌표 → machine_spec.json 저장 완료")
                    st.rerun()
                except Exception as e:
                    st.error(f"저장 실패: {e}")

        with col_gs2:
            # Summary table
            if updated_coords:
                import pandas as pd
                df_gates = pd.DataFrame(updated_coords)
                df_gates.index = [f"Gate {i+1}" for i in range(len(updated_coords))]
                df_gates.columns = ["X (mm)", "Y (mm)", "Z (mm)"]
                st.dataframe(df_gates, use_container_width=True)

    # Status strip (shared)
    st.markdown("---")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        if session_state.get("preprocess_mesh_ok"):
            st.success("✅ STL Mesh: READY")
        else:
            st.info("ℹ STL Mesh를 생성하세요.")
    with col_s2:
        if session_state.get("cavity_stl_paths") or session_state.get("insert_stl_paths"):
            total = len(session_state.get("cavity_stl_paths", [])) + len(session_state.get("insert_stl_paths", []))
            st.success(f"✅ STL 파일: {total}개 로드됨")
        else:
            st.info("ℹ STL 파일을 1-A에서 업로드하세요.")
    with col_s3:
        n_gates_confirmed = len(session_state.get("manual_gate_coords", []))
        gate_mode_label = session_state.get("gate_pick_mode", "")
        if session_state.get("preprocess_gate_conf") or n_gates_confirmed:
            mode_tag = "수동" if "Manual" in gate_mode_label else "자동"
            st.success(f"✅ 게이트 설정: {mode_tag} {n_gates_confirmed or '?'}개")
        else:
            st.info("ℹ 게이트 위치를 설정하세요.")

    st.markdown('</div>', unsafe_allow_html=True)

    # ==================================================================
    # Section D: ⚙️ Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 금형 & 사출기 상세 설정", expanded=False):
        st.markdown("##### 🔧 캐비티 & 게이트 레이아웃")
        col_adv1, col_adv2, col_adv3 = st.columns(3)

        with col_adv1:
            new_n_cav = st.number_input(
                "🏭 캐비티 수 (N Cavities)",
                min_value=1, max_value=128,
                value=int(session_state.get("n_cavities", 1)),
                step=1,
                help="1캐비티=단일 성형, 다중 캐비티=연속 대량 생산",
                key="adv_n_cavities",
            )
            if new_n_cav != session_state.get("n_cavities"):
                session_state["n_cavities"] = new_n_cav
                _sync_machine_spec(WORKSPACE_ROOT, session_state)

        with col_adv2:
            new_n_gate = st.number_input(
                "🎯 게이트 수 (N Gates)",
                min_value=1, max_value=64,
                value=int(session_state.get("n_gates", 1)),
                step=1,
                help="캐비티당 게이트 개수",
                key="adv_n_gates",
            )
            if new_n_gate != session_state.get("n_gates"):
                session_state["n_gates"] = new_n_gate
                _sync_machine_spec(WORKSPACE_ROOT, session_state)

        with col_adv3:
            new_vg_cnt = st.number_input(
                "💨 밸브 게이트 수 (Valve Gate Count)",
                min_value=0, max_value=32,
                value=int(session_state.get("valve_gate_count", 0)),
                step=1,
                help="순차 밸브 게이트(SVG) 개수. 0 = 밸브 게이트 없음",
                key="adv_valve_gate_count",
            )
            if new_vg_cnt != session_state.get("valve_gate_count"):
                session_state["valve_gate_count"] = new_vg_cnt
                _sync_machine_spec(WORKSPACE_ROOT, session_state)

        st.markdown("##### 🔩 런너 & 핫러너 시스템")
        col_adv4, col_adv5 = st.columns(2)

        with col_adv4:
            new_runner_d = st.number_input(
                "📏 런너 직경 (mm)",
                min_value=1.0, max_value=50.0,
                value=float(session_state.get("runner_diameter_mm", 6.0)),
                step=0.5, format="%.1f",
                help="주 런너 직경 (mm). 런너 밸런싱에 사용됨",
                key="adv_runner_diameter",
            )
            if new_runner_d != session_state.get("runner_diameter_mm"):
                session_state["runner_diameter_mm"] = new_runner_d
                _sync_machine_spec(WORKSPACE_ROOT, session_state)

        with col_adv5:
            new_hr = st.toggle(
                "🔥 Hot Runner 시스템 사용",
                value=session_state.get("hot_runner_enabled", False),
                help="핫러너 시스템 활성화 시 Hot Runner Mesher 기능이 연동됩니다.",
                key="adv_hot_runner",
            )
            if new_hr != session_state.get("hot_runner_enabled"):
                session_state["hot_runner_enabled"] = new_hr
                _sync_machine_spec(WORKSPACE_ROOT, session_state)
            if new_hr:
                st.info("🔥 Hot Runner 활성화됨 → Tab 2 Mesh에서 Hot Runner Mesher 실행 권장")

        if st.button("💾 Advanced Options 저장", key="save_adv_preprocess"):
            _sync_machine_spec(WORKSPACE_ROOT, session_state)
            st.success("✅ Advanced Options → machine_spec.json 저장 완료")