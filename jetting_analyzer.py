#!/usr/bin/env python3
"""
jetting_analyzer.py - Jetting S-Curve 3D Path Tracker

Analyzes Rayleigh-Taylor instability at the gate exit and tracks
the S-curve jetting trajectory in 3D space.
"""
import json, math, csv
from pathlib import Path
import numpy as np

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"
JET_CSV = WORKSPACE / "jetting_path.csv"

class JettingAnalyzer:
    def __init__(self, gate_coords=(0.075, 0.0375, 0.0), injection_speed_mps=0.25):
        self.gate_x, self.gate_y, self.gate_z = gate_coords
        self.v0 = injection_speed_mps
        self.time_steps = 200
        self.dt = 0.001  # 0.001s resolution
        self.rho = 1200.0  # kg/m3 polymer density
        self.sigma = 0.035  # N/m surface tension
        self.d_nozzle = 0.002  # 2mm gate diameter
        np.random.seed(23)

    def compute_weber_number(self):
        return self.rho * self.v0 ** 2 * self.d_nozzle / self.sigma

    def compute_jetting_amplitude(self, we):
        we_crit = 8.0
        if we <= we_crit:
            return 0.0
        return 0.005 * (we / we_crit - 1.0)

    def trace_s_curve(self):
        we = self.compute_weber_number()
        A = self.compute_jetting_amplitude(we)
        print(f"  Weber number: {we:.2f} (crit=8.0)")
        print(f"  Jetting amplitude: {A*1000:.3f} mm")

        t = np.linspace(0, self.time_steps * self.dt, self.time_steps)
        path = []
        for i, ti in enumerate(t):
            v = self.v0 * (1.0 - 0.3 * np.exp(-30 * ti))
            dx = v * self.dt
            x = self.gate_x + np.sum([v * self.dt for _ in range(i+1)]) if i > 0 else self.gate_x + dx
            y_osc = A * np.sin(2 * np.pi * ti / 0.05) * np.exp(-2 * ti)
            z_osc = A * 0.3 * np.cos(4 * np.pi * ti / 0.05) * np.exp(-2 * ti)
            path.append({
                "t_s": round(ti, 4),
                "x": round(x, 5),
                "y": round(self.gate_y + y_osc, 5),
                "z": round(self.gate_z + z_osc, 6),
                "amplitude_mm": round(abs(y_osc)*1000, 4),
            })

        # Save path
        with open(JET_CSV, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["t_s", "x", "y", "z", "amplitude_mm"])
            w.writeheader()
            w.writerows(path)

        # Analyze risk
        max_amp = max(p["amplitude_mm"] for p in path)
        n_risky = sum(1 for p in path if p["amplitude_mm"] > 0.5)
        risky = n_risky > 20
        print(f"  Max amplitude: {max_amp:.3f} mm")
        print(f"  Risky steps (>0.5mm): {n_risky}/{self.time_steps}")
        print(f"  Jetting risk: {'WARNING: S-curve jetting detected' if risky else 'STABLE flow'}")
        return {"weber": round(we, 2), "max_amplitude_mm": round(max_amp, 3),
                "risky_steps": n_risky, "is_risky": risky}

if __name__ == "__main__":
    JettingAnalyzer().trace_s_curve()