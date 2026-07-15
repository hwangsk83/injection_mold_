# -*- coding: utf-8 -*-
"""
core_utils -- Unified utility modules for injection_mold_flow
==============================================================
Provides DRY (Don't Repeat Yourself) implementations of common patterns
used across 108+ backend modules.

Submodules:
  - io_utils       : JSON/CSV load/save, machine_spec.json I/O
  - vtk_utils      : PyVista mesh loading, rendering helpers
  - logger         : Unified structured logging
  - mesh_utils     : trimesh common operations (bounds, area, watertight)
  - subprocess_utils: Self-heal subprocess runner, OpenFOAM command wrapper
  - gc_manager     : Memory management with garbage collection hooks

Usage:
  from core_utils.io_utils import load_specs, save_specs
  from core_utils.logger import get_logger
  from core_utils.vtk_utils import load_vtk_mesh, screenshot_iso
"""

__version__ = "1.0.0"
__all__ = ["io_utils", "vtk_utils", "logger", "mesh_utils", "subprocess_utils", "gc_manager"]