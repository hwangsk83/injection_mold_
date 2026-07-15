# -*- coding: utf-8 -*-
"""Common imports and utilities used across UI tabs."""

def create_dummy_case(path):
    """Create a dummy mold case directory structure."""
    import os
    from pathlib import Path
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    (p / "0").mkdir(exist_ok=True)
    (p / "constant" / "triSurface").mkdir(parents=True, exist_ok=True)
    (p / "system").mkdir(exist_ok=True)
    print(f"  [OK] Dummy case created at {p}")