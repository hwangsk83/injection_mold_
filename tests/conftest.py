# -*- coding: utf-8 -*-
"""
tests/conftest.py -- Pytest fixtures for injection_mold_flow
=============================================================
Provides shared fixtures for unit, integration, and system tests.

Usage:
    pytest tests/unit/ -v          (unit tests only, fast)
    pytest tests/ -v --tb=short    (all tests)
    pytest tests/ -v -m "not slow" (exclude slow/system tests)
"""

import os
import sys
import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add workspace root to Python path
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))


# ==============================================================================
# Core Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def workspace_path():
    """Absolute path to workspace root."""
    return WORKSPACE


@pytest.fixture(scope="function")
def sample_specs():
    """Minimal machine_spec.json fixture."""
    return {
        "clamping_force_ton": 200.0,
        "max_pressure_mpa": 180.0,
        "mesh_resolution": "Medium",
        "projected_area_m2": 0.01125,
        "max_warpage_displacement_mm": 1.5,
        "active_manufacturer": "Generic",
        "active_grade": "PC+GF20"
    }


@pytest.fixture(scope="function")
def sample_orientation_tensor():
    """500 valid fiber orientation tensors (a_ij, trace=1.0)."""
    rng = np.random.default_rng(42)
    n = 500
    a = np.zeros((n, 3, 3))
    a[:, 0, 0] = 0.5 + 0.3 * rng.random(n)
    a[:, 1, 1] = 0.3 + 0.2 * rng.random(n)
    a[:, 2, 2] = 1.0 - a[:, 0, 0] - a[:, 1, 1]
    return a


@pytest.fixture(scope="function")
def sample_material_props():
    """PC+GF20 material properties."""
    return {
        "matrix": {"E_m": 2400.0, "nu_m": 0.37, "CTE": 6.5e-5},
        "filler": {"E_f": 73000.0, "nu_f": 0.22, "vf": 0.09, "ar": 25.0, "CTE_f": 5.0e-6}
    }


@pytest.fixture(scope="function")
def mock_subprocess():
    """Mock subprocess.run to avoid real external calls."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        yield mock_run


@pytest.fixture(scope="function")
def mock_specs_json(tmp_path, sample_specs):
    """Create a temporary machine_spec.json."""
    spec_file = tmp_path / "machine_spec.json"
    with open(spec_file, "w", encoding="utf-8") as f:
        json.dump(sample_specs, f)
    return spec_file


# ==============================================================================
# Markers for test categorization
# ==============================================================================

def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (pure logic, no I/O)")
    config.addinivalue_line("markers", "integration: Integration tests (file I/O)")
    config.addinivalue_line("markers", "system: System tests (external processes)")
    config.addinivalue_line("markers", "slow: Slow tests (>1s)")