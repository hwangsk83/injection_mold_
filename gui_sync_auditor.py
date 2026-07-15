# -*- coding: utf-8 -*-
"""
gui_sync_auditor.py -- GUI-Backend Sync Integrity Auditor
==========================================================
AST-based analysis to verify every backend module has a corresponding
UI component in app.py, and vice versa. Detects:
  - Dead UI Links: GUI buttons with no backend function call
  - Orphan Functions: Backend entry points not accessible from UI
  - Stub Handlers: Buttons that show st.info() instead of calling backend

Output: gui_sync_report.json + tab reorganization proposal

Author: System Architect (Stabilization Phase)
"""

import os
import ast
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Set
from dataclasses import dataclass, field
from datetime import datetime

WORKSPACE = Path(os.getcwd())


# ==============================================================================
# Data Classes
# ==============================================================================
@dataclass
class BackendFunction:
    """A public entry-point function in a backend module."""
    name: str
    module: str
    file_path: str
    line: int
    args: List[str] = field(default_factory=list)

@dataclass
class GUIBinding:
    """A UI component (button, toggle, etc.) and what it calls."""
    component_type: str  # "button", "toggle", "selectbox", "slider"
    label: str
    line: int
    calls_module: str    # backend module imported
    calls_function: str  # function called
    status: str          # "ACTIVE", "STUB", "MISSING"

@dataclass
class SyncReport:
    """Complete GUI-Backend sync analysis."""
    total_backend_modules: int
    total_public_functions: int
    total_gui_components: int
    dead_links: List[GUIBinding] = field(default_factory=list)
    orphan_functions: List[BackendFunction] = field(default_factory=list)
    active_bindings: List[GUIBinding] = field(default_factory=list)
    tab_proposal: Dict[str, List[str]] = field(default_factory=dict)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_backend_modules": self.total_backend_modules,
            "total_public_functions": self.total_public_functions,
            "total_gui_components": self.total_gui_components,
            "dead_links": len(self.dead_links),
            "orphan_functions": len(self.orphan_functions),
            "active_bindings": len(self.active_bindings),
            "dead_link_details": [d.__dict__ for d in self.dead_links[:20]],
            "orphan_details": [o.__dict__ for o in self.orphan_functions[:20]],
            "tab_proposal": self.tab_proposal,
            "timestamp": self.timestamp
        }


# ==============================================================================
# Backend Scanner -- extract public functions from all .py modules
# ==============================================================================
KNOWN_ENTRY_PATTERNS = {
    # Module name -> expected entry function pattern
    "fsi_mapper.py": ["run_fsi_mapping", "run_orthotropic_fsi_mapping"],
    "fem_runner.py": ["run_fem_analysis"],
    "doe_optimizer.py": ["run_doe_optimization"],
    "fiber_orientator.py": ["compute_fiber_orientation"],
    "fiber_orientation_solver.py": ["run_fiber_orientation_solver"],
    "structural_homogenizer.py": ["run_structural_homogenizer"],
    "steady_state_cycle_solver.py": ["run_steady_state_cycles"],
    "performance_sensitivity_analyzer.py": ["run_sensitivity_analysis"],
    "mass_assembly_manager.py": ["run_mass_assembly", "MassAssemblyManager"],
    "multi_insert_mesher.py": ["run_multi_insert_mesher", "MultiInsertMesher"],
    "insert_molding_solver.py": ["solve_insert_molding"],
    "twoshot_overmolding_solver.py": ["solve_twoshot_overmolding"],
    "underfill_capillary_solver.py": ["solve_underfill_capillary"],
    "gate_patcher.py": ["generate_gate_dictionaries"],
    "cooling_mesher.py": ["generate_cooling_mesh"],
    "adaptive_mesher.py": ["generate_adaptive_mesh"],
    "system_auditor.py": ["main"],
    "sinkmark_vol_predictor.py": ["predict_sink_marks"],
    "gate_freeze_detector.py": ["detect_gate_freeze"],
    "checkring_backflow_simulator.py": ["simulate_checkring_backflow"],
    "imd_film_fsi_solver.py": ["solve_imd_fsi"],
    "gaim_multiphase_solver.py": ["solve_gaim"],
    "triz_process_optimizer.py": ["run_triz_optimizer"],
    "explicit_drop_solver.py": ["run_explicit_drop"],
    "polarization_ray_tracer.py": ["run_ray_tracer"],
    "step_exporter.py": ["export_step_surface"],
    "runner_balancer.py": ["run_runner_balancing"],
    "report_generator.py": ["generate_report"],
    "material_finetuner.py": ["run_fine_tuning"],
    "expert_process_editor.py": ["main"],
    "expert_solver_settings.py": ["main"],
    "stl_mesher.py": ["main"],
    "flow_stress_solver.py": ["solve_flow_stress"],
    "czm_delamination_solver.py": ["solve_czm"],
    "j_integral_fatigue_solver.py": ["solve_j_integral"],
    "topology_optimizer.py": ["run_gate_optimization"],
    "shrinkage_calculator.py": ["calculate_shrinkage"],
    "material_manager.py": ["load_material_db", "save_material_db"],
    "ai_material_synthesizer.py": ["synthesize_properties"],
    "material_db_expansion.py": ["expand_material_db"],
    "report_standardizer.py": ["standardize_report"],
    "verification_framework.py": ["run_verification"],
    "benchmark_verification.py": ["run_benchmarks"],
}


def scan_backend_modules() -> Dict[str, List[BackendFunction]]:
    """Scan all .py files for public entry-point functions."""
    modules = {}
    py_files = sorted(WORKSPACE.glob("*.py"))

    for py_file in py_files:
        name = py_file.name
        if name.startswith("_") or name in ("app.py", "gui_sync_auditor.py", "fix_system_auditor.py"):
            continue

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Consider public if: starts with run_*, solve_*, generate_*, compute_*, main, or in known patterns
                is_public = (
                    node.name.startswith(("run_", "solve_", "generate_", "compute_", "predict_",
                                          "detect_", "simulate_", "export_", "standardize_",
                                          "synthesize_", "expand_", "load_", "save_"))
                    or node.name == "main"
                    or node.name in KNOWN_ENTRY_PATTERNS.get(name, [])
                )
                if is_public:
                    functions.append(BackendFunction(
                        name=node.name,
                        module=name,
                        file_path=str(py_file),
                        line=node.lineno
                    ))

        if functions:
            modules[name] = functions

    return modules


# ==============================================================================
# GUI Scanner -- find all UI components and their backend bindings
# ==============================================================================
def scan_gui_components() -> List[GUIBinding]:
    """Parse app.py AST to extract all UI components and their bindings."""
    app_path = WORKSPACE / "app.py"
    if not app_path.exists():
        return []

    bindings = []
    try:
        tree = ast.parse(app_path.read_text(encoding="utf-8"))
    except SyntaxError:
        print("[Auditor] WARNING: app.py has syntax errors. Scanning with reduced AST.")
        # Fallback: scan with compile errors ignored
        import tokenize
        try:
            tree = ast.parse(app_path.read_text(encoding="utf-8"))
        except SyntaxError:
            return bindings

    # Step 1: Collect all imports in app.py
    imports = {}  # alias -> module name
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports[alias.asname or alias.name] = module

    # Step 2: Find all st.button, st.toggle, st.selectbox calls
    for node in ast.walk(tree):
        binding = _extract_binding(node, imports)
        if binding:
            bindings.append(binding)

    return bindings


def _extract_binding(node, imports) -> Optional[GUIBinding]:
    """Extract GUI binding from an AST Call node."""
    if not isinstance(node, ast.Call):
        return None

    # Check if it's st.button(...), st.toggle(...), st.selectbox(...)
    func = node.func
    component_type = None

    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id == "st":
            component_type = func.attr  # e.g., "button", "toggle"
    if not component_type or component_type not in ("button", "toggle", "selectbox", "slider", "checkbox"):
        return None

    # Extract label (first positional arg, usually a string)
    label = ""
    if node.args:
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant):
            label = first_arg.value
        elif isinstance(first_arg, ast.JoinedStr):
            label = "f-string"

    # Now check if this button is inside a try/except block that calls a backend
    # We need to find the parent function or with block
    # Simplified: check the entire parent scope for subprocess.run or import-based calls

    # Default: assume STUB unless we can trace to a backend call
    status = "STUB"
    calls_module = ""
    calls_function = ""

    # Traverse parent nodes for subprocess.run or import calls
    for parent in ast.walk(node):
        if isinstance(parent, ast.Call):
            calls_module, calls_function, status = _detect_backend_call(parent, imports)
            if status == "ACTIVE":
                break

    return GUIBinding(
        component_type=component_type,
        label=label,
        line=node.lineno,
        calls_module=calls_module,
        calls_function=calls_function,
        status=status
    )


def _detect_backend_call(call_node, imports) -> Tuple[str, str, str]:
    """Detect if a call node references a backend module."""
    # Case 1: subprocess.run(["python", "module_name.py"])
    if isinstance(call_node.func, ast.Attribute):
        if (isinstance(call_node.func.value, ast.Name)
                and call_node.func.value.id == "subprocess"
                and call_node.func.attr == "run"):
            if call_node.args:
                args = call_node.args[0]
                if isinstance(args, ast.List):
                    for elt in args.elts:
                        if isinstance(elt, ast.Constant) and elt.value.endswith(".py"):
                            return elt.value, "subprocess", "ACTIVE"

    # Case 2: from module import function
    if isinstance(call_node.func, ast.Name):
        name = call_node.func.name
        if name in imports:
            return imports[name], name, "ACTIVE"

    # Case 3: module.function() pattern
    if isinstance(call_node.func, ast.Attribute):
        if isinstance(call_node.func.value, ast.Name):
            mod = call_node.func.value.id
            if mod in imports:
                return imports[mod], call_node.func.attr, "ACTIVE"

    return "", "", "STUB"


# ==============================================================================
# Comparison: Find mismatches
# ==============================================================================
def detect_orphan_functions(
    backend_functions: Dict[str, List[BackendFunction]],
    gui_bindings: List[GUIBinding]
) -> List[BackendFunction]:
    """Find backend functions not referenced by any GUI component."""
    # Build set of all modules referenced by GUI
    gui_modules: Set[str] = set()
    for b in gui_bindings:
        if b.calls_module:
            gui_modules.add(b.calls_module.replace(".py", ""))

    orphans = []
    for module, funcs in backend_functions.items():
        module_base = module.replace(".py", "")
        if module_base not in gui_modules:
            # Check if it's expected to be headless (no GUI needed)
            headless_modules = {
                "system_auditor", "create_test_case", "check_files",
                "parse_results", "rebuild_0", "validation_runner",
                "run_full_test", "solve_and_monitor", "titan_v59_runner",
                "run_titan_final", "run_titan_v6", "run_titan_v7",
                "run_titan_v8", "run_titan_v9", "run_phase10_standardization"
            }
            if module_base not in headless_modules:
                orphans.extend(funcs)
    return orphans


def detect_dead_links(bindings: List[GUIBinding]) -> List[GUIBinding]:
    """Find GUI components marked as STUB."""
    return [b for b in bindings if b.status == "STUB"]


# ==============================================================================
# Tab Reorganization Proposal
# ==============================================================================
def propose_tab_reorganization(backend_functions: Dict[str, List[BackendFunction]]) -> Dict[str, List[str]]:
    """
    Propose a logical tab reorganization based on backend module categories.
    """
    proposal = {
        "Pre-process": [
            "stl_mesher.py", "cad_cleaner.py", "gate_patcher.py",
            "gate_picker.py", "gate_aligner.py", "gate_advisor.py"
        ],
        "Mesh": [
            "adaptive_mesher.py", "cooling_mesher.py",
            "multi_insert_mesher.py", "expert_manual_mesher.py"
        ],
        "Process": [
            "process_controller.py", "process_window_solver.py",
            "doe_optimizer.py", "runner_balancer.py",
            "multistage_flow_controller.py", "multistage_packing_binder.py"
        ],
        "Material": [
            "material_manager.py", "material_db_expansion.py",
            "ai_material_synthesizer.py", "material_finetuner.py"
        ],
        "Structural": [
            "structural_homogenizer.py", "steady_state_cycle_solver.py",
            "performance_sensitivity_analyzer.py", "mass_assembly_manager.py",
            "fiber_orientation_solver.py", "fsi_mapper.py", "fem_runner.py"
        ],
        "Quality": [
            "defect_analyzer.py", "sinkmark_vol_predictor.py",
            "gate_freeze_detector.py", "checkring_backflow_simulator.py",
            "jetting_analyzer.py", "surface_quality_solver.py",
            "weld_strength_mapper.py"
        ],
        "V&V": [
            "system_auditor.py", "benchmark_verification.py",
            "verification_framework.py", "comparison_engine.py"
        ],
        "Expert": [
            "expert_process_editor.py", "expert_solver_settings.py",
            "triz_process_optimizer.py", "rl_svg_optimizer.py",
            "shear_imbalance_optimizer.py", "plastic_failure_bridge.py"
        ],
        "Post-process": [
            "report_generator.py", "report_standardizer.py",
            "step_exporter.py", "die_compensation_solver.py",
            "cad_inverse_compensator.py", "optical_biref_calc.py",
            "aesthetic_visualizer.py", "pro_viewer_engine.py"
        ],
    }
    return proposal


# ==============================================================================
# Main Auditor
# ==============================================================================
def run_gui_sync_audit() -> SyncReport:
    """Execute complete GUI-Backend sync audit."""
    print("=" * 65)
    print("  GUI SYNC AUDITOR -- Backend-GUI Binding Integrity")
    print("=" * 65)

    # Step 1: Scan backend
    print("[Auditor] Scanning backend modules...")
    backend = scan_backend_modules()
    total_funcs = sum(len(v) for v in backend.values())
    print(f"  Found {len(backend)} backend modules with {total_funcs} public functions")

    # Step 2: Scan GUI
    print("[Auditor] Scanning app.py GUI components...")
    gui_bindings = scan_gui_components()
    print(f"  Found {len(gui_bindings)} UI components")

    # Step 3: Compare
    dead_links = detect_dead_links(gui_bindings)
    orphans = detect_orphan_functions(backend, gui_bindings)
    active = [b for b in gui_bindings if b.status == "ACTIVE"]

    print(f"\n[Results]")
    print(f"  Active bindings  : {len(active)}")
    print(f"  Dead UI links    : {len(dead_links)}")
    print(f"  Orphan functions : {len(orphans)}")

    if dead_links:
        print(f"\n  [DEAD LINKS]")
        for dl in dead_links[:5]:
            print(f"    - {dl.component_type}: '{dl.label}' (line {dl.line}) -> STUB")

    if orphans:
        print(f"\n  [ORPHAN FUNCTIONS]")
        for orf in orphans[:5]:
            print(f"    - {orf.module}::{orf.name} (line {orf.line})")

    # Step 4: Tab proposal
    tab_proposal = propose_tab_reorganization(backend)
    print(f"\n  [TAB PROPOSAL] {len(tab_proposal)} logical tabs proposed")

    report = SyncReport(
        total_backend_modules=len(backend),
        total_public_functions=total_funcs,
        total_gui_components=len(gui_bindings),
        dead_links=dead_links,
        orphan_functions=orphans,
        active_bindings=active,
        tab_proposal=tab_proposal,
        timestamp=datetime.now().isoformat()
    )

    # Export
    out_path = WORKSPACE / "gui_sync_report.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"\n[Auditor] Report exported to {out_path.name}")
    print("=" * 65)

    return report


if __name__ == "__main__":
    report = run_gui_sync_audit()
    print(f"\n[DONE] {report.total_gui_components} components analyzed, "
          f"{len(report.dead_links)} dead links, {len(report.orphan_functions)} orphans")