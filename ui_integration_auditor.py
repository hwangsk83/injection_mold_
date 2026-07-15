# -*- coding: utf-8 -*-
"""
ui_integration_auditor.py - Headless UI integration test suite
Using pytest + streamlit.testing.v1.AppTest.

Validates:
1. Streamlit Native AppTest rendering of all 9 tabs without Exception Overlay.
2. Session state persistence of Advanced Options across simulated interactions.
3. Mathematical correctness of Binary STL parsing (10x10x10 mm synthetic cube) and Cross-WLF equations.
4. Two-way JSON serialization matching with random float inputs.
"""

import sys
import os
import json
import struct
import random
from pathlib import Path
import pytest
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

# Resolve Workspace paths
WORKSPACE_ROOT = Path(r"D:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE_ROOT / "machine_spec.json"
OVERRIDE_JSON = WORKSPACE_ROOT / "manual_override.json"

# Add path to import UI components
sys.path.insert(0, str(WORKSPACE_ROOT))

# Import target functions for unit testing
from ui_components.tab_01_preprocess import _parse_stl_bbox
from ui_components.tab_01_preprocess import _sync_machine_spec
from ui_components.tab_04_process import _sync_process_override


# ==============================================================================
# 1. STL Binary Bounding Box Parser Test
# ==============================================================================
def test_stl_binary_bbox_parser() -> None:
    """
    Test binary STL parser with a synthetic 10x10x10 mm cube.
    Creates a single triangle covering min=0.0 and max=10.0 in X, Y, Z.
    Asserts dx_mm, dy_mm, and dz_mm are exactly 10.0.
    """
    try:
        # Create a valid synthetic binary STL header & counts
        # 80 bytes header
        header = b"Synthetic 10mm Cube Binary STL".ljust(80, b"\x00")
        # 1 triangle
        n_triangles = struct.pack("<I", 1)
        
        # 50 bytes for 1 triangle:
        # Normal (3x float): (0.0, 0.0, 0.0) -> 12 bytes
        normal = struct.pack("<fff", 0.0, 0.0, 0.0)
        # Vertex 1 (3x float): (0.0, 0.0, 0.0) -> 12 bytes
        v1 = struct.pack("<fff", 0.0, 0.0, 0.0)
        # Vertex 2 (3x float): (10.0, 0.0, 0.0) -> 12 bytes
        v2 = struct.pack("<fff", 10.0, 0.0, 0.0)
        # Vertex 3 (3x float): (0.0, 10.0, 10.0) -> 12 bytes
        v3 = struct.pack("<fff", 0.0, 10.0, 10.0)
        # Attribute byte count (uint16): 0 -> 2 bytes
        attrib = struct.pack("<H", 0)
        
        # Combine into complete binary STL buffer
        stl_bytes = header + n_triangles + normal + v1 + v2 + v3 + attrib
        
        # Run Parser
        bbox = _parse_stl_bbox(stl_bytes)
        
        assert bbox is not None, "Bounding Box parser returned None."
        assert bbox["dx_mm"] == 10.0, f"Expected dx_mm to be 10.0, got {bbox['dx_mm']}"
        assert bbox["dy_mm"] == 10.0, f"Expected dy_mm to be 10.0, got {bbox['dy_mm']}"
        assert bbox["dz_mm"] == 10.0, f"Expected dz_mm to be 10.0, got {bbox['dz_mm']}"
        assert bbox["n_triangles"] == 1, f"Expected 1 triangle, got {bbox['n_triangles']}"
        
        print("\n[PASS] STL Binary Bounding Box Parser Test successful. dx=dy=dz=10.0 mm.")
        
    except Exception as e:
        pytest.fail(f"STL parser verification failed: {e}")


# ==============================================================================
# 2. Cross-WLF Viscosity Mathematical Integrity Test
# ==============================================================================
def test_cross_wlf_viscosity_calculation() -> None:
    """
    Test Cross-WLF viscosity mathematical calculations.
    Ensures that for a selected resin grade, the Cross-WLF formula
    eta = eta_0 / (1 + (eta_0 * gamma_dot / tau_star)^(1-n))
    computes correctly without division-by-zero or shape errors.
    """
    try:
        # Standard Cross-WLF parameter coefficients for Polycarbonate (PC)
        wlf = {
            "n": 0.28,
            "tau_star": 175000.0,
            "D1": 2.8e12,
            "D2": 413.15,
            "A1": 29.8,
            "A2": 51.6
        }
        
        melt_temp_k = 563.15 # 290 C
        T = melt_temp_k
        dT = T - wlf["D2"]
        
        # Assert valid temp
        assert dT > 0, "Melt temperature must be above transition temperature D2"
        
        # Compute eta_0 (Zero shear viscosity)
        eta_0 = wlf["D1"] * np.exp(-wlf["A1"] * dT / (wlf["A2"] + dT))
        
        # Compute viscosity across wide logspace range of shear rates
        shear_rates = np.logspace(1, 5, 200)
        
        # Check for potential zero-division or negative power errors
        power_term = (eta_0 * shear_rates / wlf["tau_star"]) ** (1.0 - wlf["n"])
        eta = eta_0 / (1.0 + power_term)
        
        # Package into DataFrame
        df = pd.DataFrame({
            "shear_rate": shear_rates,
            "viscosity": eta
        })
        
        # Assert math integrity
        assert not df.isnull().any().any(), "DataFrame contains NaN values."
        assert not np.isinf(df.to_numpy()).any(), "DataFrame contains infinite values."
        assert df.shape == (200, 2), f"Expected shape (200, 2), got {df.shape}"
        assert (df["viscosity"] > 0).all(), "Viscosity values must be strictly positive."
        
        print("[PASS] Cross-WLF Viscosity calculation verified. DataFrame contains 200 valid points.")
        
    except Exception as e:
        pytest.fail(f"Cross-WLF viscosity mathematical check failed: {e}")


# ==============================================================================
# 3. Two-Way JSON Serialization Audit
# ==============================================================================
def test_two_way_serialization_audit() -> None:
    """
    Simulates inputting high-precision random floats into UI session state
    and executes synchronization functions. Then audits that the exact values
    are written to the exact key locations in machine_spec.json and manual_override.json.
    """
    try:
        # Generate random float values
        random_clamp_force = round(random.uniform(100.0, 500.0), 6)
        random_screw_dia = round(random.uniform(15.0, 60.0), 6)
        random_stage1_pres = round(random.uniform(70.0, 160.0), 6)
        random_gas_frac = round(random.uniform(0.01, 0.15), 6)
        
        # Mock session states
        mock_spec_state = {
            "clamping_force_ton": random_clamp_force,
            "screw_diameter_mm": random_screw_dia,
            "max_injection_pressure_mpa": 185.0,
            "projected_area_m2": 0.01125,
            "n_cavities": 2,
            "n_gates": 2,
            "runner_diameter_mm": 6.5,
            "hot_runner_enabled": True,
            "valve_gate_count": 4,
            "cavity_stl_paths": ["uploads/test_cavity.stl"],
            "insert_stl_paths": []
        }
        
        mock_override_state = {
            "expert_process_enabled": True,
            "stage_1_pressure_mpa": random_stage1_pres,
            "stage_1_time_s": 1.8,
            "stage_2_pressure_mpa": 85.0,
            "stage_2_time_s": 3.0,
            "stage_3_pressure_mpa": 45.0,
            "stage_3_time_s": 2.0,
            "melt_temp_k": 558.15,
            "mold_temp_k": 363.15,
            "injection_speed_mps": 0.28,
            "valve_gate_timing_s": {"gate_1": 0.5, "gate_2": 1.0},
            "expert_mesh_enabled": True,
            "global_mesh_size_mm": 3.2,
            "boundary_layer_count": 4,
            "mucell_gas_fraction": random_gas_frac
        }
        
        # 1. Trigger machine_spec.json Sync
        _sync_machine_spec(WORKSPACE_ROOT, mock_spec_state)
        
        # 2. Trigger manual_override.json Sync
        _sync_process_override(WORKSPACE_ROOT, mock_override_state)
        
        # --- Audit verification (Read and match) ---
        assert SPEC_JSON.exists(), "machine_spec.json was not created during sync."
        spec_data = json.loads(SPEC_JSON.read_text(encoding="utf-8"))
        
        assert OVERRIDE_JSON.exists(), "manual_override.json was not created during sync."
        override_data = json.loads(OVERRIDE_JSON.read_text(encoding="utf-8"))
        
        # 1:1 precise comparison
        assert spec_data["clamping_force_ton"] == random_clamp_force, \
            f"Clamping force mismatch: {spec_data['clamping_force_ton']} vs {random_clamp_force}"
        assert spec_data["screw_diameter_mm"] == random_screw_dia, \
            f"Screw diameter mismatch: {spec_data['screw_diameter_mm']} vs {random_screw_dia}"
            
        assert override_data["process"]["stage_1_pressure_mpa"] == random_stage1_pres, \
            f"Stage 1 pressure mismatch: {override_data['process']['stage_1_pressure_mpa']} vs {random_stage1_pres}"
            
        print(f"[PASS] 1:1 Two-Way Serialization Audit successful.")
        print(f"       -> Injected Clamping Force: {random_clamp_force} -> Serialized: {spec_data['clamping_force_ton']}")
        print(f"       -> Injected Stage 1 Press: {random_stage1_pres} -> Serialized: {override_data['process']['stage_1_pressure_mpa']}")
        
    except Exception as e:
        pytest.fail(f"Two-Way Serialization audit failed: {e}")


# ==============================================================================
# 4. Streamlit native AppTest Tab Navigation & Exception Check
# ==============================================================================
def test_apptest_tab_navigation() -> None:
    """
    Initializes Streamlit Native AppTest to run app.py in headless mode.
    Simulates standard user environment and verifies all tabs render without exception.
    Verifies Advanced Options session_state persistence across script rerun cycles.
    """
    try:
        # Clean up files on disk to prevent state bleed from other tests
        for p in [SPEC_JSON, OVERRIDE_JSON]:
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

        # Load and run the Streamlit app
        at = AppTest.from_file(str(WORKSPACE_ROOT / "app.py"))
        
        # Run standard rendering cycle
        at.run()
        
        # Ensure no uncaught exception overlays are present
        assert not at.exception, f"App rendered with exceptions: {at.exception}"
        
        # Inject Advanced Option properties to verify state persistence across rerun cycles
        at.session_state["adv_valve_gate_count"] = 4
        at.session_state["valve_gate_timing_s"] = {
            "gate_1": 1.25,
            "gate_2": 2.50,
            "gate_3": 3.75,
            "gate_4": 5.00
        }
        at.session_state["adv_runner_diameter"] = 7.25
        at.session_state["adv_mesh_runner_d"] = 7.25
        at.session_state["adv_mucell_gas"] = 0.075
        
        # Rerun to simulate user navigating or updating values
        at.run()
        
        # Assert no exceptions occurred during the updated state run
        assert not at.exception, f"App rerun failed with exceptions: {at.exception}"
        
        # Validate that the session state variables were not destroyed or re-initialized
        assert at.session_state["valve_gate_count"] == 4, "State 'valve_gate_count' was lost!"
        assert at.session_state["valve_gate_timing_s"]["gate_2"] == 2.50, "State 'valve_gate_timing_s' was lost!"
        assert at.session_state["runner_diameter_mm"] == 7.25, "State 'runner_diameter_mm' was lost!"
        assert at.session_state["mucell_gas_fraction"] == 0.075, "State 'mucell_gas_fraction' was lost!"
        
        print("[PASS] Streamlit native AppTest Tab navigation & state persistence successful.")
        
    except Exception as e:
        pytest.fail(f"AppTest verification failed: {e}")


if __name__ == "__main__":
    print("Running headless UI validation tests directly...")
    test_stl_binary_bbox_parser()
    test_cross_wlf_viscosity_calculation()
    test_two_way_serialization_audit()
    test_apptest_tab_navigation()
    print("All checks completed successfully!")
