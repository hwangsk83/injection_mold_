# -*- coding: utf-8 -*-
"""Unit tests for Halpin-Tsai, Mori-Tanaka, orientation tensor trace, stiffness proxy."""

import pytest
import numpy as np


class TestHalpinTsai:
    """Check 39-B, 62: Orthotropic modulus computation."""
    
    @pytest.fixture
    def params(self):
        return {"E_m": 2400.0, "E_f": 73000.0, "nu_m": 0.37, "vf": 0.09, "ar": 25.0}
    
    def test_E_L_greater_than_E_T(self, params):
        from fsi_mapper import halpin_tsai_homogenize
        ht = halpin_tsai_homogenize(**params)
        assert ht["E_L"] > ht["E_T"], f"E_L={ht['E_L']} should be > E_T={ht['E_T']}"
        assert ht["E_L"] > params["E_m"], "Composite E_L must exceed matrix modulus"
    
    def test_all_positve(self, params):
        from fsi_mapper import halpin_tsai_homogenize
        ht = halpin_tsai_homogenize(**params)
        for k, v in ht.items():
            assert v > 0, f"{k}={v} must be positive"
    
    def test_volume_fraction_zero(self, params):
        from fsi_mapper import halpin_tsai_homogenize
        p = {**params, "vf": 0.0}
        ht = halpin_tsai_homogenize(**p)
        assert abs(ht["E_L"] - params["E_m"]) / params["E_m"] < 0.1


class TestOrientationTrace:
    """Check 39-A: Trace Conservation Tr(a)=1.0."""
    
    def test_trace_conservation(self, sample_orientation_tensor):
        a = sample_orientation_tensor
        traces = np.trace(a, axis1=1, axis2=2)
        n_viol = int(np.sum(np.abs(traces - 1.0) > 1e-4))
        assert n_viol == 0, f"{n_viol}/{a.shape[0]} cells violate trace conservation"


class TestStiffnessProxy:
    """Sensitivity analyzer proxy model."""
    
    def test_higher_pressure_increases_stiffness(self):
        from performance_sensitivity_analyzer import stiffness_proxy_model
        lo = stiffness_proxy_model(60.0, 100.0)
        hi = stiffness_proxy_model(100.0, 100.0)
        assert hi["stiffness_index"] > lo["stiffness_index"]
    
    def test_output_range_physical(self):
        from performance_sensitivity_analyzer import stiffness_proxy_model
        r = stiffness_proxy_model(80.0, 100.0)
        assert 3000 < r["E_MD_MPa"] < 12000
        assert 2000 < r["E_TD_MPa"] < 8000


class TestLHS:
    """Latin Hypercube Sampling."""
    
    def test_bounds(self):
        from performance_sensitivity_analyzer import latin_hypercube_sample
        lhs = latin_hypercube_sample(100, 2, seed=42)
        assert lhs.shape == (100, 2)
        assert np.all(lhs >= 0) and np.all(lhs <= 1)
    
    def test_scaling(self):
        from performance_sensitivity_analyzer import latin_hypercube_sample, scale_samples
        lhs = latin_hypercube_sample(50, 2)
        scaled = scale_samples(lhs, [(60, 100), (50, 200)])
        assert np.all(scaled[:, 0] >= 60) and np.all(scaled[:, 0] <= 100)
        assert np.all(scaled[:, 1] >= 50) and np.all(scaled[:, 1] <= 200)


class TestBVH:
    """BVH build and query."""
    
    def test_build_single(self):
        from mass_assembly_manager import BVHNode
        node = BVHNode([0,0,0], [1,1,1], part_idx=0, is_leaf=True)
        assert node.is_leaf
        assert node.part_idx == 0
    
    def test_aabb_intersect(self):
        from mass_assembly_manager import BVHNode
        a = BVHNode([0,0,0], [5,5,5])
        assert a.intersects([2,2,2], [7,7,7])
        assert not a.intersects([6,6,6], [10,10,10])


class TestClearanceDetection:
    """Tight clearance zone detection."""
    
    def test_gap_computation(self):
        from multi_insert_mesher import compute_pairwise_gap, InsertGeometry
        a = InsertGeometry(0, "A", np.array([0,0,0]), np.array([5,5,5]), np.array([2.5,2.5,2.5]), 125)
        b = InsertGeometry(1, "B", np.array([10,10,10]), np.array([15,15,15]), np.array([12.5,12.5,12.5]), 125)
        gap = compute_pairwise_gap(a, b)
        # Distance between closest corners = sqrt(5^2+5^2+5^2) = 8.66
        assert 7 < gap < 10