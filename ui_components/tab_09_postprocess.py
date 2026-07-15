# -*- coding: utf-8 -*-
"""Tab 9: Post-process -- 3D Viz, STEP Export, Report Generation
   (Local Optimized: st.cache_data + Mesh Decimation for fast rendering)
"""
import streamlit as st
import json
import sys
import os
import numpy as np
from pathlib import Path
from core_utils.subprocess_utils import run_module


# ==================================================================
# PyVista 3D 렌더링 유틸리티 (로컬 최적화: 캐싱 + Decimation)
# ==================================================================

@st.cache_data(show_spinner=False)
def _load_vtk_cached(vtk_path_str: str):
    """VTK 파일을 PyVista 메시로 로드 (캐싱 적용)."""
    try:
        import pyvista as pv
        mesh = pv.read(vtk_path_str)
        return mesh
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _decimate_mesh_cached(vtk_path_str: str, target_reduction: float = 0.7):
    """
    메시를 Decimation 알고리즘으로 경량화 (캐싱 적용).

    Parameters
    ----------
    vtk_path_str : VTK 파일 경로
    target_reduction : 감소 비율 (0.7 = 70% 면 수 감소, 30%만 유지)

    Returns
    -------
    pyvista.PolyData or None
    """
    try:
        import pyvista as pv
        mesh = _load_vtk_cached(vtk_path_str)
        if mesh is None:
            return None

        n_faces_original = mesh.n_faces if hasattr(mesh, 'n_faces') else mesh.n_cells
        if n_faces_original < 5000:
            # 작은 메시는 Decimation 불필요
            return mesh

        # PyVista decimate_pro 필터 (또는 quadric_decimation fallback)
        try:
            decimated = mesh.decimate_pro(target_reduction, inplace=False)
        except AttributeError:
            try:
                decimated = mesh.quadric_decimation(int(n_faces_original * (1.0 - target_reduction)))
            except Exception:
                return mesh  # Decimation 실패 시 원본 반환

        n_faces_after = decimated.n_faces if hasattr(decimated, 'n_faces') else decimated.n_cells
        print(f"  [Decimate] {vtk_path_str}: {n_faces_original} -> {n_faces_after} faces "
              f"(reduction: {(1.0 - n_faces_after/max(n_faces_original,1))*100:.1f}%)")
        return decimated
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def _parse_field_data_cached(vtk_path_str: str, field_name: str):
    """
    VTK 파일에서 특정 필드 데이터를 파싱 (캐싱 적용).
    대용량 Warpage 변형 및 Fiber Orientation 데이터에 사용.

    Returns
    -------
    dict or None : {"min": float, "max": float, "array": np.ndarray (downsampled)}
    """
    try:
        import pyvista as pv
        mesh = _load_vtk_cached(vtk_path_str)
        if mesh is None:
            return None

        # Point data 또는 Cell data 검색
        data = None
        location = None
        if field_name in mesh.point_data:
            data = mesh.point_data[field_name]
            location = "point"
        elif field_name in mesh.cell_data:
            data = mesh.cell_data[field_name]
            location = "cell"

        if data is None:
            return None

        arr = np.asarray(data, dtype=np.float32)
        # 대용량 배열은 다운샘플링 (최대 50000 포인트로)
        if len(arr) > 50000:
            stride = max(1, len(arr) // 50000)
            arr_down = arr[::stride]
        else:
            arr_down = arr

        return {
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
            "mean": float(np.nanmean(arr)),
            "array": arr_down,
            "location": location,
            "size": len(arr),
        }
    except Exception:
        return None


def _find_latest_vtk(directory: Path, pattern: str = "*.vtk") -> str:
    """주어진 디렉토리에서 가장 최근 VTK 파일을 찾는다."""
    if not directory.exists():
        return ""
    vtk_files = list(directory.glob(pattern))
    if not vtk_files:
        return ""
    vtk_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return str(vtk_files[0])


def generate_weldline_rendering(workspace_root):
    """
    Weldline 3D 렌더링: 캐싱 + Decimation 최적화 적용.
    PyVista Plotter로 렌더링 후 Streamlit에 표시.
    """
    workspace = Path(workspace_root)
    vtk_dir = workspace / "validation_test" / "VTK"

    vtk_path = _find_latest_vtk(vtk_dir, "validation_test_*.vtk")
    if not vtk_path:
        st.warning("No VTK files found for weldline rendering. Run injectionFoam first.")
        return False

    st.info(f"Rendering weldline from: {Path(vtk_path).name}")

    try:
        import pyvista as pv
        from pyvista import examples

        # Decimation 적용 메시 로드
        mesh = _decimate_mesh_cached(vtk_path, target_reduction=0.7)
        if mesh is None:
            st.error("Failed to load or decimate mesh.")
            return False

        # Plotter 생성
        plotter = pv.Plotter(window_size=[800, 600], off_screen=True)
        plotter.add_mesh(
            mesh,
            scalars="U" if "U" in mesh.array_names else None,
            cmap="viridis",
            show_edges=False,
            opacity=0.9,
            lighting=True,
        )
        plotter.add_text("Weldline 3D Rendering", position="upper_left", font_size=12)
        plotter.view_isometric()
        plotter.camera.zoom(1.2)

        # Render to screenshot
        img_path = workspace / "report_assets" / "weldline_3d.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(str(img_path), return_img=False)
        plotter.close()

        if img_path.exists():
            st.image(str(img_path), caption="3D Weldline Rendering", use_column_width=True)
            return True
        return False
    except ImportError:
        st.warning("PyVista not installed. Install with: pip install pyvista")
        return False
    except Exception as e:
        st.error(f"Weldline rendering failed: {e}")
        return False


def generate_warpage_rendering(workspace_root):
    """
    Warpage 3D 변형 렌더링: 캐싱 + Decimation 최적화 적용.
    대용량 변형 데이터를 경량화하여 시각화 지연 감소.
    """
    workspace = Path(workspace_root)
    vtk_dir = workspace / "validation_test" / "VTK"

    vtk_path = _find_latest_vtk(vtk_dir, "validation_test_*.vtk")
    if not vtk_path:
        st.warning("No VTK files found for warpage rendering. Run fsi_mapper.py first.")
        return False

    st.info(f"Rendering warpage from: {Path(vtk_path).name}")

    try:
        import pyvista as pv

        # Decimation 적용 (더 높은 압축률 - Warpage 용)
        mesh = _decimate_mesh_cached(vtk_path, target_reduction=0.8)
        if mesh is None:
            st.error("Failed to load or decimate mesh.")
            return False

        # Warpage 변위 필드 데이터 파싱 (캐싱)
        disp_data = _parse_field_data_cached(vtk_path, "U")
        if disp_data:
            st.caption(
                f"Displacement: min={disp_data['min']:.4f}, "
                f"max={disp_data['max']:.4f}, "
                f"mean={disp_data['mean']:.4f} mm"
            )

        # Warp mesh by displacement if available
        if "U" in mesh.array_names:
            warped = mesh.warp_by_vector("U")
        else:
            warped = mesh

        plotter = pv.Plotter(window_size=[800, 600], off_screen=True)
        plotter.add_mesh(
            mesh,
            color="lightgray",
            opacity=0.3,
            show_edges=False,
        )
        plotter.add_mesh(
            warped,
            scalars="U" if "U" in mesh.array_names else None,
            cmap="coolwarm",
            show_edges=False,
            opacity=0.9,
            lighting=True,
        )
        # 변형 배율 (10배 확대)
        if "U" in mesh.array_names:
            plotter.add_mesh(
                warped,
                scalars="U",
                cmap="coolwarm",
                show_edges=False,
                opacity=0.9,
                lighting=True,
            )
        plotter.add_text("Warpage 3D Rendering (10x scale)", position="upper_left", font_size=12)
        plotter.view_isometric()
        plotter.camera.zoom(1.2)

        img_path = workspace / "report_assets" / "warpage_3d.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(str(img_path), return_img=False)
        plotter.close()

        if img_path.exists():
            st.image(str(img_path), caption="3D Warpage Rendering", use_column_width=True)
            return True
        return False
    except ImportError:
        st.warning("PyVista not installed. Install with: pip install pyvista")
        return False
    except Exception as e:
        st.error(f"Warpage rendering failed: {e}")
        return False


def generate_fiber_orientation_rendering(workspace_root):
    """
    Fiber Orientation 3D 렌더링: 캐싱 + Decimation 적용.
    Fiber 배향 텐서 데이터를 경량화하여 시각화.
    """
    workspace = Path(workspace_root)
    orient_npy = workspace / "fiber_orientation.npy"
    vtk_dir = workspace / "validation_test" / "VTK"

    vtk_path = _find_latest_vtk(vtk_dir, "validation_test_*.vtk")
    if not vtk_path:
        st.warning("No VTK files found for fiber orientation rendering.")
        return False

    if not orient_npy.exists():
        st.warning("fiber_orientation.npy not found. Run fiber_orientator.py first.")
        return False

    st.info(f"Rendering fiber orientation from: {Path(vtk_path).name}")

    try:
        import pyvista as pv

        # Decimation 적용
        mesh = _decimate_mesh_cached(vtk_path, target_reduction=0.7)
        if mesh is None:
            st.error("Failed to load or decimate mesh.")
            return False

        # Fiber orientation 데이터 로드
        a_tensor = np.load(str(orient_npy))  # shape (N, 3, 3)
        # a11 (flow direction orientation) 추출
        a11 = a_tensor[:, 0, 0]

        # 메시에 fiber orientation 스칼라 추가
        n_cells = mesh.n_cells if hasattr(mesh, 'n_cells') else mesh.n_points
        if len(a11) == n_cells:
            mesh.cell_data["fiber_a11"] = a11.astype(np.float32)
        elif len(a11) == mesh.n_points:
            mesh.point_data["fiber_a11"] = a11.astype(np.float32)
        else:
            # 크기가 맞지 않으면 nearest neighbor 매핑
            st.warning(f"Fiber data size ({len(a11)}) doesn't match mesh ({n_cells}). Showing raw data.")
            st.bar_chart(a11[:min(100, len(a11))])
            return False

        plotter = pv.Plotter(window_size=[800, 600], off_screen=True)
        plotter.add_mesh(
            mesh,
            scalars="fiber_a11",
            cmap="plasma",
            show_edges=False,
            opacity=0.9,
            lighting=True,
            scalar_bar_args={"title": "Fiber a11 (MD Orientation)"},
        )
        plotter.add_text("Fiber Orientation 3D Rendering", position="upper_left", font_size=12)
        plotter.view_isometric()
        plotter.camera.zoom(1.2)

        img_path = workspace / "report_assets" / "fiber_orientation_3d.png"
        img_path.parent.mkdir(parents=True, exist_ok=True)
        plotter.screenshot(str(img_path), return_img=False)
        plotter.close()

        if img_path.exists():
            st.image(str(img_path), caption="3D Fiber Orientation Rendering", use_column_width=True)
            return True
        return False
    except ImportError:
        st.warning("PyVista not installed. Install with: pip install pyvista")
        return False
    except Exception as e:
        st.error(f"Fiber orientation rendering failed: {e}")
        return False


# ==================================================================
# Tab 09 Main Render Function
# ==================================================================

def render(WORKSPACE_ROOT, SPEC_JSON):
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("9. Post-process & Reporting")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**3D Visualization**")
        if st.button("🔬 3D Weldline Render", key="3dw"):
            with st.spinner("Rendering weldline 3D (decimated)..."):
                if generate_weldline_rendering(WORKSPACE_ROOT):
                    st.success("Weldline Rendered")
                else:
                    st.error("Weldline Render Failed")

        if st.button("📐 3D Warpage Render", key="3dwp"):
            with st.spinner("Rendering warpage 3D (decimated)..."):
                if generate_warpage_rendering(WORKSPACE_ROOT):
                    st.success("Warpage Rendered")
                else:
                    st.error("Warpage Render Failed")

        if st.button("🧬 3D Fiber Orientation", key="3dfo"):
            with st.spinner("Rendering fiber orientation 3D..."):
                if generate_fiber_orientation_rendering(WORKSPACE_ROOT):
                    st.success("Fiber Orientation Rendered")
                else:
                    st.error("Fiber Orientation Render Failed")

        if st.button("🌈 Polariscope Ray Tracer", key="prt"):
            run_module("polarization_ray_tracer.py")
            st.success("Done")

    with col2:
        st.markdown("**CAD & Export**")
        if st.button("📦 STEP Exporter", key="step"):
            run_module("step_exporter.py")
            st.success("Done")
        if st.button("🔄 Inverse Compensate CAD", key="icc"):
            run_module("cad_inverse_compensator.py")
            st.success("Done")
        if st.button("👁 Pro Viewer Engine", key="pve"):
            run_module("pro_viewer_engine.py")
            st.success("Done")
        
        st.markdown("---")
        st.markdown("**ParaView Auto-Launcher**")
        
        # 1. Try loading persistently from machine_spec.json first
        spec_path = Path(WORKSPACE_ROOT) / "machine_spec.json"
        persistent_path = ""
        if spec_path.exists():
            try:
                _spec = json.loads(spec_path.read_text(encoding="utf-8"))
                persistent_path = _spec.get("postprocess", {}).get("paraview_exe_path", "")
            except Exception:
                pass

        # Search for ParaView default paths
        default_paths = [
            r"D:\Program-Files\blueCFD-Core-2024\AddOns\ParaView\bin\paraview.exe",
            r"C:\Program Files\ParaView 5.12.0\bin\paraview.exe",
            r"C:\Program Files\ParaView 5.11.0\bin\paraview.exe",
            r"C:\Program Files\ParaView 5.10.0\bin\paraview.exe",
            r"C:\Program Files\ParaView 5.9.1\bin\paraview.exe",
            r"C:\Program Files\ParaView 5.9.0\bin\paraview.exe",
        ]
        
        detected_path = ""
        import shutil
        path_in_env = shutil.which("paraview")
        if path_in_env:
            detected_path = path_in_env
        else:
            for p in default_paths:
                if Path(p).exists():
                    detected_path = p
                    break
        
        # Decide initial value: Persistent path > session_state > auto-detected
        init_val = persistent_path if persistent_path else st.session_state.setdefault("paraview_exe_path", detected_path)
        
        paraview_path = st.text_input(
            "🖥️ ParaView Executable Path (수동 입력 시 즉시 영구 저장)",
            value=init_val,
            help="파라뷰 실행파일(paraview.exe)의 전체 절대 경로를 입력하고 Enter를 누르세요. 입력값은 자동 저장됩니다.",
            key="paraview_exe_path_input"
        )
        
        # 2. Persist path to machine_spec.json immediately when changed
        if paraview_path != persistent_path:
            try:
                existing = {}
                if spec_path.exists():
                    try:
                        existing = json.loads(spec_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                existing.setdefault("postprocess", {})
                existing["postprocess"]["paraview_exe_path"] = paraview_path
                spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
                st.session_state["paraview_exe_path"] = paraview_path
                st.toast("💾 ParaView 경로가 영구 저장 설정되었습니다!", icon="💾")
            except Exception:
                pass
        
        if st.button("🖥️ Launch ParaView Viewer", key="launch_pv"):
            if not paraview_path or not Path(paraview_path).exists():
                st.error("❌ ParaView executable not found at specified path. Please configure it correctly.")
            else:
                # Find latest VTK to load
                vtk_dir = Path(WORKSPACE_ROOT) / "validation_test" / "VTK"
                latest_vtk = _find_latest_vtk(vtk_dir, "validation_test_*.vtk")
                
                if not latest_vtk:
                    st.warning("⚠️ No VTK files found in validation_test/VTK. ParaView will open empty.")
                    args = [paraview_path]
                else:
                    st.info(f"📂 Loading latest result into ParaView: {Path(latest_vtk).name}")
                    args = [paraview_path, latest_vtk]
                
                try:
                    import subprocess
                    subprocess.Popen(args, close_fds=True)
                    st.success("🚀 ParaView launched successfully as a background process!")
                except Exception as e:
                    st.error(f"❌ Failed to launch ParaView: {e}")

    with col3:
        st.markdown("**Reporting**")
        if st.button("📄 Generate Report", key="gr"):
            run_module("report_generator.py")
            st.success("Done")
        if st.button("📏 Standardize Report", key="sr"):
            run_module("report_standardizer.py")
            st.success("Done")
        if st.button("📊 Enterprise PPTX", key="epp"):
            run_module("report_generator.py")
            st.success("Done")

    st.markdown("</div>", unsafe_allow_html=True)

    # ==================================================================
    # Section B: Advanced Options Toggle
    # ==================================================================
    with st.expander("⚙️ Advanced Options — 시각화 품질 & 보고서 출력 형식 제어", expanded=False):
        import json
        from pathlib import Path as _Path
        st.markdown("##### 🖥️ 3D 렌더링 품질 설정 (Visualization Quality)")

        col_adv1, col_adv2 = st.columns(2)

        with col_adv1:
            decimate_factor = st.slider(
                "🎯 메시 Decimation 비율",
                min_value=0.0, max_value=0.95,
                value=float(st.session_state.get("vtk_decimate_factor", 0.7)),
                step=0.05,
                help="0 = 원본 유지, 0.7 = 70% 면 수 감소 (빠른 렌더링). 대형 모델은 0.7~0.8 권장.",
                key="adv_decimate_factor",
            )
            st.session_state["vtk_decimate_factor"] = decimate_factor

        with col_adv2:
            vtk_field = st.selectbox(
                "📊 시각화 필드 선택 (VTK Field Name)",
                options=["U", "p", "T", "alpha.water", "fiber_a11", "sigma_VM"],
                index=0,
                help="VTK 파일에서 렌더링할 물리량 필드 이름. 'U' = 속도/변위, 'p' = 압력, 'T' = 온도",
                key="adv_vtk_field",
            )
            st.session_state["vtk_visualization_field"] = vtk_field

        st.markdown("---")
        st.markdown("##### 📄 보고서 출력 형식 (Report Output Format)")
        col_rep1, col_rep2 = st.columns(2)

        with col_rep1:
            report_formats = st.multiselect(
                "📋 출력 형식 선택",
                options=["PDF", "PPTX", "HTML", "JSON", "CSV"],
                default=st.session_state.get("report_formats", ["PDF", "PPTX"]),
                help="보고서 생성 시 출력할 형식을 선택하세요.",
                key="adv_report_formats",
            )
            st.session_state["report_formats"] = report_formats

        with col_rep2:
            dpi = st.number_input(
                "🖼️ 이미지 해상도 (DPI)",
                min_value=72, max_value=600,
                value=int(st.session_state.get("report_dpi", 150)),
                step=50,
                help="보고서 내 이미지 DPI. 300+ = 인쇄용 고해상도.",
                key="adv_report_dpi",
            )
            st.session_state["report_dpi"] = dpi

        if st.button("💾 Post-process Advanced Options 저장 → machine_spec.json", key="save_adv_postprocess"):
            spec_path = _Path(WORKSPACE_ROOT) / "machine_spec.json"
            existing = {}
            if spec_path.exists():
                try:
                    existing = json.loads(spec_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            existing["postprocess"] = {
                "vtk_decimate_factor": decimate_factor,
                "vtk_visualization_field": vtk_field,
                "report_formats": report_formats,
                "report_dpi": dpi,
            }
            spec_path.write_text(json.dumps(existing, indent=4, ensure_ascii=False), encoding="utf-8")
            st.success("✅ Post-process Advanced Options → machine_spec.json 저장 완료")