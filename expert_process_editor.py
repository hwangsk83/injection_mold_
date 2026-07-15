#!/usr/bin/env python3
"""
expert_process_editor.py - Expert Manual Process Parameter Editor

Allows manual override of multi-stage packing, melt/mold temperatures,
injection speed, and valve gate timing. Stores in manual_override.json.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
OVERRIDE_JSON = WORKSPACE / "manual_override.json"
SPEC_JSON = WORKSPACE / "machine_spec.json"

class ManualProcessOverride:
    def __init__(self):
        self.stage_1_pressure_mpa: float = 100.0
        self.stage_1_time_s: float = 1.5
        self.stage_2_pressure_mpa: float = 80.0
        self.stage_2_time_s: float = 3.0
        self.stage_3_pressure_mpa: float = 40.0
        self.stage_3_time_s: float = 2.0
        self.melt_temp_k: float = 563.15
        self.mold_temp_k: float = 373.15
        self.injection_speed_mps: float = 0.25
        self.valve_gate_timing_s: Dict[int, float] = {}
        self.enabled: bool = False
        self.load_from_json()

    def load_from_json(self):
        try:
            if OVERRIDE_JSON.exists():
                data = json.loads(OVERRIDE_JSON.read_text())
                proc = data.get("process", {})
                self.stage_1_pressure_mpa = proc.get("stage_1_pressure_mpa", 100.0)
                self.stage_1_time_s = proc.get("stage_1_time_s", 1.5)
                self.stage_2_pressure_mpa = proc.get("stage_2_pressure_mpa", 80.0)
                self.stage_2_time_s = proc.get("stage_2_time_s", 3.0)
                self.stage_3_pressure_mpa = proc.get("stage_3_pressure_mpa", 40.0)
                self.stage_3_time_s = proc.get("stage_3_time_s", 2.0)
                self.melt_temp_k = proc.get("melt_temp_k", 563.15)
                self.mold_temp_k = proc.get("mold_temp_k", 373.15)
                self.injection_speed_mps = proc.get("injection_speed_mps", 0.25)
                self.valve_gate_timing_s = proc.get("valve_gate_timing_s", {})
                if isinstance(self.valve_gate_timing_s, dict):
                    self.valve_gate_timing_s = {int(k): v for k, v in self.valve_gate_timing_s.items()}
                self.enabled = proc.get("enabled", False)
        except Exception:
            pass

    def save_to_json(self):
        data = {}
        if OVERRIDE_JSON.exists():
            try: data = json.loads(OVERRIDE_JSON.read_text())
            except: pass
        data["process"] = {
            "enabled": self.enabled,
            "stage_1_pressure_mpa": self.stage_1_pressure_mpa,
            "stage_1_time_s": self.stage_1_time_s,
            "stage_2_pressure_mpa": self.stage_2_pressure_mpa,
            "stage_2_time_s": self.stage_2_time_s,
            "stage_3_pressure_mpa": self.stage_3_pressure_mpa,
            "stage_3_time_s": self.stage_3_time_s,
            "melt_temp_k": self.melt_temp_k,
            "mold_temp_k": self.mold_temp_k,
            "injection_speed_mps": self.injection_speed_mps,
            "valve_gate_timing_s": self.valve_gate_timing_s,
        }
        OVERRIDE_JSON.write_text(json.dumps(data, indent=4))

    def load_auto_optimum(self):
        """Load Auto-Wizard optimal values from machine_spec.json"""
        try:
            if SPEC_JSON.exists():
                specs = json.loads(SPEC_JSON.read_text())
                opt = specs.get("optimum_recipe", {})
                if opt:
                    self.melt_temp_k = opt.get("MeltTemp_K", 563.15)
                    self.mold_temp_k = opt.get("MoldTemp_K", 373.15)
                    self.stage_1_pressure_mpa = opt.get("PackingPressure_MPa", 100.0)
                    self.stage_1_time_s = opt.get("PackingTime_s", 1.5)
        except Exception:
            pass

    def get_pressure_profile(self) -> List[float]:
        return [self.stage_1_pressure_mpa, self.stage_2_pressure_mpa, self.stage_3_pressure_mpa]

    def get_time_profile(self) -> List[float]:
        return [self.stage_1_time_s, self.stage_2_time_s, self.stage_3_time_s]

    def compute_delta_vs_auto(self) -> dict:
        """Compute difference between manual override and auto-optimum values."""
        auto = {}
        try:
            if SPEC_JSON.exists():
                specs = json.loads(SPEC_JSON.read_text())
                opt = specs.get("optimum_recipe", {})
                auto = {"P1": opt.get("PackingPressure_MPa", 100), "T1": opt.get("PackingTime_s", 1.5),
                         "Tmelt": opt.get("MeltTemp_K", 563), "Tmold": opt.get("MoldTemp_K", 373)}
        except: pass

        if not auto:
            return {"note": "No auto-optimum found. Run DOE first."}

        return {
            "P1 (MPa)": {"auto": auto.get("P1", 100), "manual": self.stage_1_pressure_mpa,
                          "delta": self.stage_1_pressure_mpa - auto.get("P1", 100)},
            "T1 (s)": {"auto": auto.get("T1", 1.5), "manual": self.stage_1_time_s,
                        "delta": self.stage_1_time_s - auto.get("T1", 1.5)},
            "Tmelt (K)": {"auto": auto.get("Tmelt", 563), "manual": self.melt_temp_k,
                           "delta": self.melt_temp_k - auto.get("Tmelt", 563)},
            "Tmold (K)": {"auto": auto.get("Tmold", 373), "manual": self.mold_temp_k,
                           "delta": self.mold_temp_k - auto.get("Tmold", 373)},
        }

    def clear_overrides(self):
        self.enabled = False
        self.load_auto_optimum()
        self.save_to_json()


if __name__ == "__main__":
    p = ManualProcessOverride()
    p.load_auto_optimum()
    p.stage_1_pressure_mpa = 110.0
    p.enabled = True
    p.save_to_json()
    print("Delta vs Auto:", json.dumps(p.compute_delta_vs_auto(), indent=2))