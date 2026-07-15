#!/usr/bin/env python3
"""
pro_viewer_engine.py - Professional Post-Processing Viewer

Time-step scrubbing, multi-layer transparency, dynamic cross-sectioning,
and filter tree logging for PyVista-based visualization.
"""
import json, os, sys, numpy as np
from pathlib import Path

try:
    import pyvista as pv
    HAS_PV = True
except ImportError:
    HAS_PV = False

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
VTK_DIR = WORKSPACE / "validation_test" / "VTK"
STL_PATH = WORKSPACE / "validation_test" / "constant" / "triSurface" / "case_model.stl"
SPEC_JSON = WORKSPACE / "machine_spec.json"

class ProViewerEngine:
    """Professional-grade post-processing viewer with time scrubbing,
    multi-layer transparency, and dynamic cross-sectioning."""

    def __init__(self):
        self.pl = None
        self.mesh = None
        self.time_steps = []
        self.current_step = 0
        self.filter_tree = []
        self.layer_opacities = {}
        self.clip_origin = [0, 0, 0]
        self.clip_normal = [0, 0, 1]
        if HAS_PV:
            pv.OFF_SCREEN = True

    def load_mesh(self, mesh_path=None):
        if not HAS_PV:
            raise ImportError("PyVista required")
        path = Path(mesh_path) if mesh_path else STL_PATH
        if path.exists():
            self.mesh = pv.read(str(path))
            self.log_filter("LoadMesh", f"Loaded {path.name} ({self.mesh.n_cells} cells)")
        else:
            self.mesh = pv.Box(bounds=(-0.075, 0.075, -0.0375, 0.0375, -0.0006, 0.0006))
            self.log_filter("LoadMesh", "Created synthetic box mesh")
        return self.mesh

    def load_time_series(self):
        """Load VTK time-step sequence for animation scrubbing."""
        self.time_steps = sorted(VTK_DIR.glob("validation_test_*.vtk"))
        self.log_filter("LoadTimeSeries", f"Found {len(self.time_steps)} time steps")
        return self.time_steps

    def scrub_to_step(self, step_idx: int):
        """Jump to specific time step frame."""
        if not self.time_steps or step_idx >= len(self.time_steps):
            return None
        self.current_step = step_idx
        mesh = pv.read(str(self.time_steps[step_idx]))
        self.log_filter("TimeScrub", f"Frame {step_idx}/{len(self.time_steps)-1}")
        return mesh

    def add_layer(self, layer_id: str, mesh, opacity: float = 0.5, color=None, cmap=None):
        """Add a translucent layer for multi-layer transparency view."""
        self.layer_opacities[layer_id] = {"mesh": mesh, "opacity": opacity, "color": color, "cmap": cmap}
        self.log_filter("AddLayer", f"{layer_id} opacity={opacity}")

    def set_layer_opacity(self, layer_id: str, opacity: float):
        if layer_id in self.layer_opacities:
            self.layer_opacities[layer_id]["opacity"] = max(0.05, min(1.0, opacity))

    def set_clip_plane(self, origin, normal):
        """Set dynamic cross-section plane."""
        self.clip_origin = list(origin)
        self.clip_normal = list(normal)
        self.log_filter("ClipPlane", f"origin={origin}, normal={normal}")

    def render_dynamic_cross_section(self, output_png: str = "cross_section_render.png"):
        """Render a cross-section view with current clip plane."""
        if not HAS_PV:
            return None
        pl = pv.Plotter(off_screen=True, window_size=[1200, 800])
        pl.background_color = '#1e293b'

        if self.mesh:
            clipped = self.mesh.clip(normal=self.clip_normal, origin=self.clip_origin)
            pl.add_mesh(clipped, color="#38bdf8", opacity=0.7, label="Cross-section")

        path = WORKSPACE / output_png
        pl.screenshot(str(path))
        pl.close()
        self.log_filter("RenderCrossSection", f"Saved {output_png}")
        return str(path)

    def render_full_view(self, output_png: str = "pro_viewer_render.png"):
        """Render the complete multi-layer view."""
        if not HAS_PV:
            return None
        pl = pv.Plotter(off_screen=True, window_size=[1200, 800])
        pl.background_color = '#1e293b'

        for lid, data in self.layer_opacities.items():
            m = data["mesh"]
            if data.get("cmap"):
                pl.add_mesh(m, scalars=data.get("cmap"), cmap="viridis",
                             opacity=data["opacity"], label=lid)
            else:
                pl.add_mesh(m, color=data.get("color", "#64748b"),
                             opacity=data["opacity"], label=lid)

        pl.add_title("Pro Viewer: Multi-Layer Composite", font_size=14, color='white')
        pl.add_scalar_bar(title="Scalar Field", color="white")
        pl.camera_position = 'iso'

        path = WORKSPACE / output_png
        pl.screenshot(str(path))
        pl.close()
        return str(path)

    def log_filter(self, filter_name: str, detail: str):
        self.filter_tree.append({"filter": filter_name, "detail": detail, "step": len(self.filter_tree) + 1})
        print(f"  [ProViewer] {filter_name}: {detail}")

    def get_filter_tree_summary(self) -> str:
        lines = ["## ProViewer Filter Tree", ""]
        lines.append("| # | Filter | Detail |")
        lines.append("|---|--------|--------|")
        for f in self.filter_tree:
            lines.append(f"| {f['step']} | {f['filter']} | {f['detail']} |")
        return "\n".join(lines)


def demo_pro_viewer():
    """Demonstrate pro viewer capabilities."""
    viewer = ProViewerEngine()
    viewer.load_mesh()
    viewer.load_time_series()
    viewer.add_layer("Part", viewer.mesh, opacity=0.6, color="#38bdf8")
    viewer.set_clip_plane([0, 0, 0.0003], [0, 0, 1])
    viewer.render_dynamic_cross_section("cross_section_render.png")
    viewer.render_full_view("pro_viewer_render.png")
    print(viewer.get_filter_tree_summary())


if __name__ == "__main__":
    demo_pro_viewer()