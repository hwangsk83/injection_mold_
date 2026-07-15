#!/usr/bin/env python3
"""
expert_solver_settings.py - Expert Solver Settings Override

Allows manual tuning of numerical solver parameters:
Damping, Iterations, CFL, fracture coupling coefficient.
Stores in manual_override.json.
"""
import json
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
OVERRIDE_JSON = WORKSPACE / "manual_override.json"

class ManualSolverConfig:
    def __init__(self):
        self.relaxation_factor: float = 0.7
        self.n_outer_correctors: int = 1
        self.n_correctors: int = 2
        self.n_non_orthogonal: int = 1
        self.max_iter: int = 1000
        self.convergence_tolerance: float = 1e-6
        self.fracture_coupling_coeff: float = 1.0
        self.explicit_time_step_s: float = 0.0  # 0 = auto
        self.enabled: bool = False
        self.load_from_json()

    def load_from_json(self):
        try:
            if OVERRIDE_JSON.exists():
                data = json.loads(OVERRIDE_JSON.read_text())
                sol = data.get("solver", {})
                self.relaxation_factor = sol.get("relaxation_factor", 0.7)
                self.n_outer_correctors = sol.get("n_outer_correctors", 1)
                self.n_correctors = sol.get("n_correctors", 2)
                self.n_non_orthogonal = sol.get("n_non_orthogonal", 1)
                self.max_iter = sol.get("max_iter", 1000)
                self.convergence_tolerance = sol.get("convergence_tolerance", 1e-6)
                self.fracture_coupling_coeff = sol.get("fracture_coupling_coeff", 1.0)
                self.explicit_time_step_s = sol.get("explicit_time_step_s", 0.0)
                self.enabled = sol.get("enabled", False)
        except Exception:
            pass

    def save_to_json(self):
        data = {}
        if OVERRIDE_JSON.exists():
            try: data = json.loads(OVERRIDE_JSON.read_text())
            except: pass
        data["solver"] = {
            "enabled": self.enabled,
            "relaxation_factor": self.relaxation_factor,
            "n_outer_correctors": self.n_outer_correctors,
            "n_correctors": self.n_correctors,
            "n_non_orthogonal": self.n_non_orthogonal,
            "max_iter": self.max_iter,
            "convergence_tolerance": self.convergence_tolerance,
            "fracture_coupling_coeff": self.fracture_coupling_coeff,
            "explicit_time_step_s": self.explicit_time_step_s,
        }
        OVERRIDE_JSON.write_text(json.dumps(data, indent=4))

    def validate(self) -> list:
        violations = []
        if not (0.1 <= self.relaxation_factor <= 0.99):
            violations.append(f"Relaxation factor {self.relaxation_factor} out of [0.1, 0.99]")
        if self.n_outer_correctors < 1:
            violations.append("n_outer_correctors must be >= 1")
        if self.n_correctors < 1:
            violations.append("n_correctors must be >= 1")
        if self.max_iter < 100:
            violations.append("max_iter must be >= 100")
        if self.convergence_tolerance <= 0:
            violations.append("convergence_tolerance must be > 0")
        if not (0.1 <= self.fracture_coupling_coeff <= 2.0):
            violations.append(f"fracture_coupling_coeff {self.fracture_coupling_coeff} out of [0.1, 2.0]")
        return violations

    def clear_overrides(self):
        self.relaxation_factor = 0.7
        self.n_outer_correctors = 1
        self.n_correctors = 2
        self.n_non_orthogonal = 1
        self.max_iter = 1000
        self.convergence_tolerance = 1e-6
        self.fracture_coupling_coeff = 1.0
        self.explicit_time_step_s = 0.0
        self.enabled = False
        self.save_to_json()


if __name__ == "__main__":
    cfg = ManualSolverConfig()
    cfg.relaxation_factor = 0.85
    cfg.max_iter = 5000
    cfg.enabled = True
    cfg.save_to_json()
    print("Violations:", cfg.validate())