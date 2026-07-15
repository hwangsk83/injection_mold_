#!/usr/bin/env python3
"""
expert_manual_mesher.py - Expert Manual Mesh Configuration Editor

Allows manual override of mesh size, refinement zones, and boundary
layer settings. Maintains backward compatibility with Auto-Mesher.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
OVERRIDE_JSON = WORKSPACE / "manual_override.json"

class ManualMeshConfig:
    def __init__(self):
        self.global_size_mm: float = 4.0
        self.pin_points: List[dict] = []
        self.boundary_layer_count: int = 2
        self.enabled: bool = False
        self.load_from_json()

    def load_from_json(self):
        try:
            if OVERRIDE_JSON.exists():
                data = json.loads(OVERRIDE_JSON.read_text())
                mesh = data.get("mesh", {})
                self.global_size_mm = mesh.get("global_size_mm", 4.0)
                self.pin_points = mesh.get("pin_points", [])
                self.boundary_layer_count = mesh.get("boundary_layer_count", 2)
                self.enabled = mesh.get("enabled", False)
        except Exception:
            pass

    def save_to_json(self):
        data = {}
        if OVERRIDE_JSON.exists():
            try:
                data = json.loads(OVERRIDE_JSON.read_text())
            except:
                pass
        data["mesh"] = {
            "enabled": self.enabled,
            "global_size_mm": self.global_size_mm,
            "pin_points": self.pin_points,
            "boundary_layer_count": self.boundary_layer_count,
        }
        OVERRIDE_JSON.write_text(json.dumps(data, indent=4))

    def set_global_size(self, size_mm: float):
        self.global_size_mm = max(0.01, min(size_mm, 50.0))
        self.enabled = True
        self.save_to_json()

    def add_pin_point(self, x: float, y: float, z: float, radius_mm: float = 5.0,
                       local_size_mm: float = 1.0):
        self.pin_points.append({
            "x": x, "y": y, "z": z,
            "radius_mm": radius_mm,
            "local_size_mm": local_size_mm
        })
        self.enabled = True
        self.save_to_json()

    def remove_pin_point(self, index: int):
        if 0 <= index < len(self.pin_points):
            self.pin_points.pop(index)
            self.save_to_json()

    def set_boundary_layers(self, count: int):
        self.boundary_layer_count = max(0, min(count, 10))
        self.save_to_json()

    def clear_overrides(self):
        self.global_size_mm = 4.0
        self.pin_points = []
        self.boundary_layer_count = 2
        self.enabled = False
        self.save_to_json()

    def generate_mesh_overrides_summary(self) -> str:
        lines = ["## Manual Mesh Overrides", ""]
        if not self.enabled:
            lines.append("No manual overrides active. Using Auto-Mesher defaults.")
            return "\n".join(lines)
        lines.append(f"- Global Size: {self.global_size_mm:.2f} mm")
        lines.append(f"- Boundary Layers: {self.boundary_layer_count}")
        lines.append(f"- Pin Points: {len(self.pin_points)}")
        for i, pt in enumerate(self.pin_points):
            lines.append(f"  - P{i+1}: ({pt['x']:.2f}, {pt['y']:.2f}, {pt['z']:.2f}) R={pt['radius_mm']:.1f}mm, Local={pt['local_size_mm']:.2f}mm")
        return "\n".join(lines)


if __name__ == "__main__":
    cfg = ManualMeshConfig()
    cfg.set_global_size(3.5)
    cfg.add_pin_point(0.075, 0.0375, 0.0006, 3.0, 0.5)
    cfg.set_boundary_layers(3)
    print(cfg.generate_mesh_overrides_summary())