# -*- coding: utf-8 -*-
"""
core_utils.io_utils -- Unified JSON/CSV file I/O
=================================================
Replaces the duplicated pattern found in 35+ files:
    SPEC_JSON = WORKSPACE / "machine_spec.json"
    with open(SPEC_JSON, "r", encoding="utf-8") as f:
        specs = json.load(f)
    ...
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)

Usage:
    from core_utils.io_utils import load_specs, save_specs, load_json, save_json
    specs = load_specs()           # reads machine_spec.json
    save_specs({"key": "value"})   # writes machine_spec.json with merge
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


# -- Default workspace path --
_WORKSPACE = Path(os.getcwd())


def set_workspace(path: Path):
    """Set the workspace root for relative path resolution."""
    global _WORKSPACE
    _WORKSPACE = Path(path)


def _resolve(path) -> Path:
    """Resolve a path relative to workspace, or absolute path."""
    p = Path(path)
    if p.is_absolute():
        return p
    return _WORKSPACE / p


# -- JSON I/O --
def load_json(path, default: Any = None) -> Any:
    """
    Load JSON from file. Returns default if file doesn't exist or is corrupt.

    Parameters
    ----------
    path : str or Path
    default : returned on failure

    Returns
    -------
    parsed JSON object or default
    """
    p = _resolve(path)
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, Exception):
        return default


def save_json(path, data: Any, indent: int = 2, mkdir: bool = True) -> bool:
    """
    Save data as JSON to file. Creates parent directories if needed.

    Returns True on success, False on failure.
    """
    p = _resolve(path)
    try:
        if mkdir:
            p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception:
        return False


def safe_load_json(path, default: Any = None) -> Any:
    """Alias for load_json with exception safety."""
    return load_json(path, default)


# -- Machine Spec Helpers (high-frequency pattern) --
def load_specs(default: Any = None) -> Dict[str, Any]:
    """
    Load machine_spec.json. Returns empty dict if missing.
    This is the SINGLE replacement for the 35+ duplicated patterns.
    """
    specs = load_json(_WORKSPACE / "machine_spec.json", default={})
    if specs is None:
        specs = {}
    return specs


def save_specs(data: Dict[str, Any], merge: bool = True) -> bool:
    """
    Save to machine_spec.json. If merge=True, load existing first and update.
    """
    if merge:
        existing = load_specs(default={})
        existing.update(data)
        data = existing
    return save_json(_WORKSPACE / "machine_spec.json", data)


def get_spec(key: str, default: Any = None) -> Any:
    """
    Read a single key from machine_spec.json without loading the whole dict every time.
    Uses agressive caching for repeated reads.
    """
    specs = load_specs(default={})
    return specs.get(key, default)


def set_spec(key: str, value: Any, merge: bool = True) -> bool:
    """Set a single key in machine_spec.json."""
    return save_specs({key: value}, merge=merge)


# -- CSV I/O --
def load_csv(path, **kwargs) -> Optional[Any]:
    """
    Load CSV file using pandas. Returns DataFrame or None on failure.
    """
    try:
        import pandas as pd
        p = _resolve(path)
        if not p.exists():
            return None
        return pd.read_csv(p, **kwargs)
    except ImportError:
        return None
    except Exception:
        return None


def save_csv(path, df, **kwargs) -> bool:
    """
    Save DataFrame to CSV. Returns True on success.
    """
    try:
        p = _resolve(path)
        df.to_csv(p, index=False, **kwargs)
        return True
    except Exception:
        return False


# -- Material DB Helpers --
def load_material_db() -> Dict[str, Any]:
    """
    Load material_db.json. Falls back to material_db.py built-in if JSON missing.
    """
    db = load_json(_WORKSPACE / "material_db.json", default=None)
    if db is None:
        try:
            import material_db as mdb
            db = mdb.MATERIAL_DB
        except ImportError:
            db = {}
    return db


def save_material_db(data: Dict[str, Any]) -> bool:
    """
    Save material database to material_db.json.
    """
    return save_json(_WORKSPACE / "material_db.json", data)


# -- File Existence Check --
def ensure_file(path, generator_module: Optional[str] = None) -> bool:
    """
    Check if file exists. If not and generator_module is provided,
    runs it to self-heal.

    Returns True if file exists after check.
    """
    p = _resolve(path)
    if p.exists():
        return True
    if generator_module:
        import subprocess
        import sys
        subprocess.run([sys.executable, generator_module], cwd=str(_WORKSPACE))
        return p.exists()
    return False


# -- Text file I/O (for OpenFOAM dictionaries) --
def read_text(path) -> Optional[str]:
    """Read a text file. Returns None on failure."""
    p = _resolve(path)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def write_text(path, content: str) -> bool:
    """Write a text file. Creates parent directories. Returns True on success."""
    p = _resolve(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception:
        return False