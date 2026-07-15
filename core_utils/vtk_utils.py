# -*- coding: utf-8 -*-
"""
core_utils.vtk_utils -- PyVista Rendering & VTK Helpers
=========================================================
Replaces 8+ duplicated VTK loading/rendering patterns.

Usage:
    from core_utils.vtk_utils import load_vtk_mesh, render_stl, screenshot_iso
"""

import os
import numpy as np
from pathlib import Path
from typing import Optional, Any, List, Tuple


def load_vtk_mesh(path, default=None):
    """Load a VTK/STL file via PyVista. Returns mesh or default."""
    p = Path(path)
    if not p.exists():
        return default
    try:
        import pyvista as pv
        return pv.read(str(p))
    except Exception:
        return default


def load_latest_vtk(vtk_dir, pattern="*.vtk") -> Any:
    """Load the most recent VTK file from a directory."""
    import pyvista as pv
    d = Path(vtk_dir)
    if not d.exists():
        return None
    files = sorted(d.glob(pattern), key=lambda f: f.stat().st_mtime)
    if not files:
        return None
    return pv.read(str(files[-1]))


def render_stl_overlay(
    stl_path: str,
    overlay_points: Optional[np.ndarray] = None,
    point_color: str = "#ef4444",
    output_png: Optional[str] = None,
    camera_position: str = 'iso',
    opacity: float = 0.3,
    off_screen: bool = True
) -> bool:
    """
    Render an STL mesh with optional point overlay. Saves to PNG.
    
    Returns True on success.
    """
    p_stl = Path(stl_path)
    if not p_stl.exists():
        return False

    try:
        import pyvista as pv
        pv.OFF_SCREEN = off_screen
        plotter = pv.Plotter(off_screen=off_screen)
        
        mesh = pv.read(str(p_stl))
        plotter.add_mesh(mesh, color="#38bdf8", opacity=opacity, label="Part")
        
        if overlay_points is not None and len(overlay_points) > 0:
            poly = pv.PolyData(overlay_points)
            plotter.add_mesh(poly, color=point_color, point_size=15,
                           render_points_as_spheres=True, label="Overlay")
        
        plotter.camera_position = camera_position
        
        if output_png:
            plotter.screenshot(str(output_png))
        plotter.close()
        return True
    except Exception:
        return False


def render_deformed_mesh(
    stl_path: str,
    displacement_field: np.ndarray,
    scale_factor: float = 10.0,
    output_png: Optional[str] = None,
    cmap: str = "viridis"
) -> bool:
    """
    Render a deformed mesh with displacement coloring.
    """
    p = Path(stl_path)
    if not p.exists():
        return False
    try:
        import pyvista as pv
        pv.OFF_SCREEN = True
        plotter = pv.Plotter(off_screen=True)
        mesh = pv.read(str(p))
        pts = mesh.points.copy()
        pts[:, 2] += displacement_field * scale_factor
        warped = pv.PolyData(pts, mesh.faces)
        plotter.add_mesh(warped, scalars=np.abs(displacement_field * scale_factor),
                        cmap=cmap, label="Deformed")
        plotter.camera_position = 'iso'
        if output_png:
            plotter.screenshot(str(output_png))
        plotter.close()
        return True
    except Exception:
        return False


def screenshot_iso(plotter, output_path: str):
    """Set iso view and save screenshot."""
    plotter.camera_position = 'iso'
    plotter.screenshot(str(output_path))