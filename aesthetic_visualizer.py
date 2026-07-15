#!/usr/bin/env python3
"""
aesthetic_visualizer.py - Weldline Visibility & Gloss Uniformity Analyzer

Computes refractive index deviation, light scattering, and Visibility
Score for weldline joints on aesthetic surfaces.
"""
import json, math
from pathlib import Path
import numpy as np

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"
WELD_CSV  = WORKSPACE / "weld_line_risk_zones.csv"
VIS_CSV   = WORKSPACE / "weldline_visibility.csv"

class AestheticAnalyzer:
    def __init__(self, n_weld_points=20):
        self.n_points = n_weld_points
        self.stress optical_coeff = 3.2e-9  # Pa⁻¹ (PC stress-optical coefficient)
        self.scattering_factor = 0.15
        self.incident_angle = 45.0  # degrees
        self.gloss_threshold = 15.0  # K temperature difference
        np.random.seed(11)

    def compute_refractive_index_deviation(self, stress_mpa):
        """Δn = C·Δσ (stress-optical law)"""
        C = self.stress_optical_coeff
        delta_n = C * stress_mpa * 1e6  # MPa -> Pa
        return delta_n

    def compute_scattering_coefficient(self, delta_n):
        """μ_s = k·(Δn)²·f(θ)"""
        theta_rad = math.radians(self.incident_angle)
        f_theta = math.cos(theta_rad) ** 2
        mu_s = self.scattering_factor * (delta_n ** 2) * f_theta
        return mu_s

    def compute_visibility_score(self, mu_s):
        """V = 0~100 scale from scattering coefficient"""
        V = np.clip(mu_s * 1e12 * 5, 0, 100)
        return V

    def generate_weldline_data(self):
        """Generate synthetic weldline stress/temperature data."""
        stresses = np.random.gamma(shape=2, scale=15, size=self.n_points)
        temps = np.random.normal(340, 8, self.n_points)
        coords = np.column_stack([
            np.linspace(0.05, 0.13, self.n_points),
            np.full(self.n_points, 0.0375),
            np.random.normal(0, 0.0002, self.n_points)
        ])
        return stresses, temps, coords

    def analyze(self):
        print("=" * 62)
        print("  AESTHETIC VISUALIZER - Weldline Visibility & Gloss")
        print("=" * 62)

        stresses, temps, coords = self.generate_weldline_data()

        delta_n = self.compute_refractive_index_deviation(stresses)
        mu_s = self.compute_scattering_coefficient(delta_n)
        V = self.compute_visibility_score(mu_s)

        # Gloss uniformity: temperature gradient check
        temp_grad = np.abs(np.gradient(temps))
        gloss_ok = np.all(temp_grad < self.gloss_threshold)

        n_visible = int(np.sum(V > 40))
        max_V = float(np.max(V))
        avg_V = float(np.mean(V))

        print(f"  Weldline points: {self.n_points}")
        print(f"  Avg Visibility Score: {avg_V:.1f}/100")
        print(f"  Max Visibility: {max_V:.1f}/100")
        print(f"  Visible joints (V>40): {n_visible}")
        print(f"  Gloss uniformity: {'OK' if gloss_ok else 'WARNING: temp gradient > 15K'}")

        # Save visibility data
        import csv
        data = []
        for i in range(self.n_points):
            data.append({
                "point_id": i + 1,
                "stress_mpa": round(float(stresses[i]), 2),
                "temp_k": round(float(temps[i]), 1),
                "delta_n": f"{delta_n[i]:.3e}",
                "scattering_coeff": f"{mu_s[i]:.3e}",
                "visibility_score": round(float(V[i]), 1),
                "visible": "YES" if V[i] > 40 else "NO",
                "x": round(float(coords[i,0]), 4),
                "y": round(float(coords[i,1]), 4),
                "z": round(float(coords[i,2]), 6),
            })
        with open(VIS_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=data[0].keys())
            w.writeheader()
            w.writerows(data)

        verdict = "PASS" if n_visible == 0 and gloss_ok else "WARNING"
        print(f"  Verdict: {verdict}")
        print(f"  Visibility CSV: {VIS_CSV.name}")
        return {"max_visibility": max_V, "n_visible": n_visible, "gloss_ok": gloss_ok, "verdict": verdict}

if __name__ == "__main__":
    AestheticAnalyzer().analyze()