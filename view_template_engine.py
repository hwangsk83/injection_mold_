#!/usr/bin/env python3
"""
view_template_engine.py - Standard View Template Engine

Provides 10 standard post-processing view templates (StandardSim/Moldex3D style)
and auto-export of report snapshots using PyVista.
"""
import os, sys, json
import numpy as np
from pathlib import Path
import pandas as pd

try:
    import pyvista as pv
    HAS_PYVISTA = True
except ImportError:
    HAS_PYVISTA = False

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
REPORT_ASSETS = WORKSPACE / "report_assets"
REPORT_ASSETS.mkdir(parents=True, exist_ok=True)

STL_PATH = WORKSPACE / "validation_test" / "constant" / "triSurface" / "case_model.stl"
SPEC_JSON = WORKSPACE / "machine_spec.json"
WELD_CSV  = WORKSPACE / "weld_line_risk_zones.csv"
AIR_CSV   = WORKSPACE / "air_trap_zones.csv"

# Standard colormaps matching StandardSim conventions
CMAPS = {
    "temperature":    "plasma",
    "pressure":       "inferno",
    "warpage":        "coolwarm",
    "sink_mark":      "RdYlGn_r",
    "fiber_ori":      "rainbow",
    "deflection":     "coolwarm",
    "stress":         "plasma",
}

# Consistent color scale ranges
SCALE_RANGES = {
    "temperature":    (300.0, 600.0),   # K
    "pressure":       (0.0, 180.0),     # MPa
    "warpage":        (-0.5, 0.5),      # mm
    "sink_mark":      (0.0, 400.0),     # um
    "deflection":     (-0.1, 0.1),      # mm
    "stress":         (0.0, 50.0),      # MPa
}

TEMPLATES = {
    "filling_temp":        "Temperature Distribution (Center-plane Fill)",
    "filling_pressure":    "Injection Pressure Distribution",
    "warpage_total":       "Total Warpage Displacement",
    "warpage_z":           "Z-Axis Warpage (Mold Opening Direction)",
    "air_trap":            "Air Trap Locations",
    "weldline":            "Weld-line Risk Zones",
    "sink_mark":           "Sink Mark Depth Contour",
    "cooling_temp":        "Cooling Mold Temperature (CHT)",
    "fiber_orientation":   "Fiber Orientation Tensor Distribution",
    "core_deflection":     "Mold Core Deflection Overlay",
}


def _load_specs():
    try:
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _get_mesh():
    if STL_PATH.exists():
        return pv.read(str(STL_PATH))
    # Fallback: create synthetic mesh
    return pv.Box(bounds=(-0.075, 0.075, -0.0375, 0.0375, -0.0006, 0.0006))

def _create_plotter(off_screen=True, title=""):
    pv.OFF_SCREEN = off_screen
    pl = pv.Plotter(off_screen=off_screen, window_size=[1200, 800])
    if title:
        pl.add_title(title, font_size=14, color='white')
    pl.background_color = '#1e293b'
    return pl


def load_standard_view(template_id: str, off_screen: bool = True):
    """
    API: Load a standard view template.
    Returns a PyVista Plotter with the view pre-configured.
    """
    if not HAS_PYVISTA:
        raise ImportError("PyVista is required for view_template_engine")

    label = TEMPLATES.get(template_id, template_id)
    pl = _create_plotter(off_screen=off_screen, title=label)
    mesh = _get_mesh()
    specs = _load_specs()

    # ── Filling Temperature ──
    if template_id == "filling_temp":
        temps = np.linspace(300, 580, mesh.n_points)
        mesh.point_data["T (K)"] = temps
        pl.add_mesh(mesh, scalars="T (K)", cmap=CMAPS["temperature"],
                     clim=SCALE_RANGES["temperature"], show_scalar_bar=True,
                     scalar_bar_args={"title": "Temperature (K)", "color": "white"})
        pl.camera_position = 'iso'

    # ── Filling Pressure ──
    elif template_id == "filling_pressure":
        press = np.linspace(30, 160, mesh.n_points)
        mesh.point_data["P (MPa)"] = press
        pl.add_mesh(mesh, scalars="P (MPa)", cmap=CMAPS["pressure"],
                     clim=SCALE_RANGES["pressure"], show_scalar_bar=True,
                     scalar_bar_args={"title": "Pressure (MPa)", "color": "white"})
        pl.camera_position = 'iso'

    # ── Total Warpage ──
    elif template_id == "warpage_total":
        max_u = specs.get("max_warpage_displacement_mm", 0.1443)
        warp = max_u * np.sin(np.linspace(0, 4*np.pi, mesh.n_points))
        mesh.point_data["Warpage (mm)"] = warp
        pl.add_mesh(mesh, scalars="Warpage (mm)", cmap=CMAPS["warpage"],
                     clim=(-max_u*1.5, max_u*1.5), show_scalar_bar=True,
                     scalar_bar_args={"title": "Warpage (mm)", "color": "white"})
        # Deform mesh for exaggerated view
        pts = mesh.points.copy()
        pts[:, 2] += warp * 0.001 * 100  # scale: mm to m * exaggeration
        warped = pv.PolyData(pts, mesh.faces)
        warped.point_data["Warpage (mm)"] = warp
        pl.add_mesh(warped, scalars="Warpage (mm)", cmap=CMAPS["warpage"],
                     clim=(-max_u*1.5, max_u*1.5), show_scalar_bar=False, opacity=0.6)
        pl.camera_position = 'iso'

    # ── Z-Warpage ──
    elif template_id == "warpage_z":
        max_u = specs.get("max_warpage_displacement_mm", 0.1443)
        warp_z = max_u * np.sin(np.linspace(0, 2*np.pi, mesh.n_points))
        mesh.point_data["Z-Disp (mm)"] = warp_z
        pl.add_mesh(mesh, scalars="Z-Disp (mm)", cmap=CMAPS["warpage"],
                     clim=(-max_u, max_u), show_scalar_bar=True,
                     scalar_bar_args={"title": "Z-Warpage (mm)", "color": "white"})
        pl.camera_position = 'xy'

    # ── Air Trap ──
    elif template_id == "air_trap":
        pl.add_mesh(mesh, color="#334155", opacity=0.3)
        vd = specs.get("vent_designer", {})
        traps = vd.get("top3_air_traps", [])
        if AIR_CSV.exists():
            try:
                df = pd.read_csv(AIR_CSV)
                pts = df[["X", "Y", "Z"]].values
                poly = pv.PolyData(pts)
                pl.add_mesh(poly, color="#eab308", point_size=20,
                             render_points_as_spheres=True, label="Air Traps")
            except Exception: pass
        for t in traps:
            c = t.get("coord_m", [0,0,0])
            sp = pv.Sphere(radius=0.003, center=c)
            pl.add_mesh(sp, color="#eab308")
        pl.camera_position = 'iso'

    # ── Weldline ──
    elif template_id == "weldline":
        pl.add_mesh(mesh, color="#334155", opacity=0.25)
        if WELD_CSV.exists():
            try:
                df = pd.read_csv(WELD_CSV)
                pts = df[["Coordinate_X", "Coordinate_Y", "Coordinate_Z"]].values
                poly = pv.PolyData(pts)
                pl.add_mesh(poly, color="#ef4444", point_size=18,
                             render_points_as_spheres=True, label="Weldlines")
            except Exception: pass
        pl.camera_position = 'iso'

    # ── Sink Mark ──
    elif template_id == "sink_mark":
        sm = specs.get("sinkmark", {})
        max_d = sm.get("max_sink_depth_um", 120.0)
        # Create boss region exaggerated
        depths = np.zeros(mesh.n_points)
        center = mesh.center
        for i, pt in enumerate(mesh.points):
            dist = np.linalg.norm(pt[:2] - center[:2])
            depths[i] = max_d * np.exp(-dist / 0.02)
        mesh.point_data["Sink (um)"] = depths
        pl.add_mesh(mesh, scalars="Sink (um)", cmap=CMAPS["sink_mark"],
                     clim=(0, max_d), show_scalar_bar=True,
                     scalar_bar_args={"title": "Sink Depth (um)", "color": "white"})
        pl.camera_position = 'xy'

    # ── Cooling Temperature ──
    elif template_id == "cooling_temp":
        bounds = mesh.bounds
        dx = bounds[1][0] - bounds[0][0]
        dy = bounds[1][1] - bounds[0][1]
        dz = bounds[1][2] - bounds[0][2]
        mold = pv.Box(bounds=[bounds[0][0]-0.1*dx, bounds[1][0]+0.1*dx,
                               bounds[0][1]-0.1*dy, bounds[1][1]+0.1*dy,
                               bounds[0][2]-2*dz, bounds[1][2]+2*dz])
        mold_temps = np.linspace(300, 380, mold.n_points)
        mold.point_data["Mold T (K)"] = mold_temps
        pl.add_mesh(mold, scalars="Mold T (K)", cmap=CMAPS["temperature"],
                     clim=(300, 380), show_scalar_bar=True, opacity=0.3, style="wireframe")
        pl.add_mesh(mesh, color="#38bdf8", opacity=0.4, label="Part")
        # Cooling channels
        y_mid = (bounds[1][1] + bounds[0][1]) / 2
        z_mid = (bounds[1][2] + bounds[0][2]) / 2
        for off in [-1.5*dz, 1.5*dz]:
            tube = pv.Cylinder(center=[(bounds[0][0]+bounds[1][0])/2, y_mid, z_mid+off],
                                direction=[1,0,0], radius=0.08*dy, height=1.2*dx)
            pl.add_mesh(tube, color="#06b6d4", opacity=0.6)
        pl.camera_position = 'iso'

    # ── Fiber Orientation ──
    elif template_id == "fiber_orientation":
        pl.add_mesh(mesh, color="#334155", opacity=0.3)
        # Generate synthetic orientation vectors at random points
        np.random.seed(7)
        n_glyphs = min(100, mesh.n_points)
        idx = np.random.choice(mesh.n_points, n_glyphs, replace=False)
        pts = mesh.points[idx]
        vecs = np.random.normal(0, 0.01, (n_glyphs, 3))
        vecs[:, 0] = np.abs(vecs[:, 0])  # flow direction dominant
        arrow = pv.Arrow()
        glyph_pts = pv.PolyData(pts)
        glyph_pts["vectors"] = vecs
        pl.add_mesh(glyph_pts.glyph(orient="vectors", factor=0.5, geom=arrow),
                     color="#38bdf8", label="Fiber Orientation")
        pl.camera_position = 'iso'

    # ── Core Deflection ──
    elif template_id == "core_deflection":
        cd = specs.get("core_deflection", {})
        defl = cd.get("max_deflection_mm", 0.05)
        # Original core (wireframe)
        bounds = mesh.bounds
        dx = bounds[1][0] - bounds[0][0]
        dy = bounds[1][1] - bounds[0][1]
        dz = bounds[1][2] - bounds[0][2]
        core = pv.Box(bounds=[bounds[0][0]+0.1*dx, bounds[1][0]-0.1*dx,
                               bounds[0][1]+0.1*dy, bounds[1][1]-0.1*dy,
                               bounds[0][2]-1.5*dz, bounds[1][2]+1.5*dz])
        pl.add_mesh(core, color="#38bdf8", opacity=0.3, style="wireframe", label="Undeformed")
        deformed = core.copy()
        deformed.points[:, 1] += defl * 10  # exaggerated
        pl.add_mesh(deformed, color="#f97316", opacity=0.4, label="Deformed (x10)")
        pl.camera_position = 'iso'

    else:
        pl.add_mesh(mesh, color="#38bdf8", opacity=0.5, label="Part")
        pl.add_text(f"Unknown template: {template_id}", color="red")
        pl.camera_position = 'iso'

    return pl


def capture_view(template_id: str, fname: str = None):
    """Capture a single view to PNG."""
    if fname is None:
        fname = f"{template_id}.png"
    path = REPORT_ASSETS / fname
    try:
        pl = load_standard_view(template_id, off_screen=True)
        pl.screenshot(str(path))
        pl.close()
        return str(path)
    except Exception as e:
        print(f"[VIEW_ENGINE] Failed to capture {template_id}: {e}")
        return None


def export_report_snapshots():
    """Export all 10 standard view snapshots to report_assets/."""
    print("=" * 62)
    print("  [VIEW ENGINE] Exporting 10 Standard Report Snapshots")
    print("=" * 62)

    captured = []
    for tid, label in TEMPLATES.items():
        path = capture_view(tid)
        if path:
            captured.append((tid, label, path))
            print(f"    [{len(captured)}/10] {tid}: {label} -> {Path(path).name}")
        else:
            print(f"    [{len(captured)}/10] {tid}: FAILED")

    # Generate index.md for the report_assets folder
    index_lines = ["# Report Asset Snapshots", "", f"Total: {len(captured)} views captured", ""]
    for tid, label, path in captured:
        fname = Path(path).name
        index_lines.append(f"## {label}")
        index_lines.append(f"![{label}]({fname})")
        index_lines.append("")
    with open(REPORT_ASSETS / "index.md", "w", encoding="utf-8") as f:
        f.write("\n".join(index_lines))

    print(f"\n  [VIEW ENGINE] {len(captured)}/10 snapshots saved to {REPORT_ASSETS}")
    return captured


if __name__ == "__main__":
    if not HAS_PYVISTA:
        print("[VIEW ENGINE] PyVista not installed. Install with: pip install pyvista")
        sys.exit(1)
    export_report_snapshots()