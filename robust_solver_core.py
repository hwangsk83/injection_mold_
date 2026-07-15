#!/usr/bin/env python3
"""
robust_solver_core.py - Numerical Robustness Engine

Provides auto-stabilization for non-orthogonal meshes, under-relaxation
auto-tuning, and geometric defect detection with ghost-cell interpolation.
"""
import json, math
from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"
SOLVER_CSV = WORKSPACE / "solver_monitor.csv"

class NonOrthogonalCorrector:
    """Automatically adjusts nNonOrthogonalCorrectors based on mesh quality."""
    def __init__(self, max_non_ortho_angle: float = 30.0):
        self.max_angle = max_non_ortho_angle
        self.recommended_correctors = 1

    def assess_mesh(self, non_ortho_max: float) -> int:
        if non_ortho_max <= 30:
            self.recommended_correctors = 0
        elif non_ortho_max <= 50:
            self.recommended_correctors = 1
        elif non_ortho_max <= 70:
            self.recommended_correctors = 2
        else:
            self.recommended_correctors = 3
        print(f"  [NonOrthoCorrector] Angle={non_ortho_max:.1f}deg -> nCorrectors={self.recommended_correctors}")
        return self.recommended_correctors


class AutoUnderRelaxation:
    """Auto-tunes under-relaxation factor based on residual convergence rate."""
    def __init__(self, initial_alpha: float = 0.7):
        self.alpha = initial_alpha
        self.prev_residual = None
        self.oscillation_count = 0
        self.total_steps = 0

    def update(self, current_residual: float) -> float:
        self.total_steps += 1
        if self.prev_residual is not None:
            ratio = current_residual / max(self.prev_residual, 1e-12)
            if ratio > 0.9:  # slow convergence
                self.alpha = max(0.1, self.alpha * 0.8)
            elif ratio > 0.5:
                self.alpha = max(0.1, self.alpha * 0.95)
            else:
                self.alpha = min(0.99, self.alpha * 1.02)

            # Detect oscillation: alternating residual sign change
            if self.prev_residual * current_residual < 0:
                self.oscillation_count += 1

        self.prev_residual = current_residual
        return self.alpha

    def is_oscillating(self) -> bool:
        return self.oscillation_count > 5

    def get_stability_report(self) -> dict:
        osc_ratio = self.oscillation_count / max(self.total_steps, 1)
        return {
            "current_alpha": round(self.alpha, 6),
            "oscillation_count": self.oscillation_count,
            "total_steps": self.total_steps,
            "oscillation_ratio": round(osc_ratio, 4),
            "stable": not self.is_oscillating(),
        }


class GeometricDefectHandler:
    """Handles non-manifold edges via ghost-cell averaging interpolation."""

    @staticmethod
    def detect_non_manifold_faces(faces: np.ndarray) -> list:
        edge_dict = {}
        non_manifold_edges = []
        for i, face in enumerate(faces):
            nv = len(face)
            for j in range(nv):
                e = tuple(sorted([int(face[j]), int(face[(j+1) % nv])]))
                edge_dict.setdefault(e, []).append(i)
        for edge, face_ids in edge_dict.items():
            if len(face_ids) > 2:
                non_manifold_edges.append({"edge": edge, "face_count": len(face_ids)})
        return non_manifold_edges

    @staticmethod
    def ghost_cell_interpolate(cell_values: np.ndarray, neighbor_graph: Dict[int, list],
                                defect_cell_idx: int) -> float:
        neighbors = neighbor_graph.get(defect_cell_idx, [])
        if not neighbors:
            return float(np.mean(cell_values))
        return float(np.mean([cell_values[n] for n in neighbors if 0 <= n < len(cell_values)]))


class MeshQualityAuditor:
    """Audits mesh quality metrics and raises warnings for critical defects."""

    @staticmethod
    def audit(aspect_ratios: List[float], skewness: List[float], non_ortho: List[float]) -> dict:
        ar_violations = sum(1 for ar in aspect_ratios if ar > 20)
        sk_violations = sum(1 for sk in skewness if sk > 4)
        no_violations = sum(1 for no in non_ortho if no > 70)

        total_cells = max(len(aspect_ratios), 1)
        report = {
            "total_cells": total_cells,
            "AR_violations": ar_violations,
            "AR_pct": round(ar_violations / total_cells * 100, 2),
            "skewness_violations": sk_violations,
            "skewness_pct": round(sk_violations / total_cells * 100, 2),
            "non_ortho_violations": no_violations,
            "non_ortho_pct": round(no_violations / total_cells * 100, 2),
        }
        if ar_violations > total_cells * 0.05:
            print(f"  [MeshAuditor] WARNING: {ar_violations} cells ({report['AR_pct']}%) exceed AR>20!")
        if no_violations > total_cells * 0.10:
            print(f"  [MeshAuditor] WARNING: {no_violations} cells ({report['non_ortho_pct']}%) exceed 70 deg!")
        return report


def simulate_geometric_noise():
    """Inject geometric noise into the case model to test robustness."""
    print("[ROBUSTNESS TEST] Injecting geometric noise...")
    specs = {}
    if SPEC_JSON.exists():
        specs = json.loads(SPEC_JSON.read_text())

    # Simulate 50 noisy cells with high AR
    n_cells = 500
    np.random.seed(42)
    aspect_ratios = np.random.lognormal(mean=0.5, sigma=0.8, size=n_cells)
    skewness = np.abs(np.random.normal(1.5, 1.0, n_cells))
    non_ortho = np.abs(np.random.normal(25, 20, n_cells))
    non_ortho = np.clip(non_ortho, 10, 85)

    # Audit mesh quality
    auditor = MeshQualityAuditor()
    report = auditor.audit(aspect_ratios, skewness, non_ortho)
    print(f"  Injected cells: {n_cells}, AR_violations={report['AR_violations']}, "
          f"nonOrtho_violations={report['non_ortho_violations']}")

    # Test NonOrthogonalCorrector
    nocr = NonOrthogonalCorrector()
    nocr.assess_mesh(float(np.max(non_ortho)))

    # Test AutoUnderRelaxation
    aur = AutoUnderRelaxation()
    residuals = np.abs(np.random.normal(0, 1, 30)) * np.exp(-np.linspace(0, 3, 30))
    for r in residuals:
        aur.update(float(r))
    stab = aur.get_stability_report()
    print(f"  AutoUnderRelaxation: alpha={stab['current_alpha']:.4f}, "
          f"stable={stab['stable']}, oscill={stab['oscillation_count']}")

    return {"mesh_quality": report, "stability": stab}


if __name__ == "__main__":
    simulate_geometric_noise()