# -*- coding: utf-8 -*-
"""
structural_homogenizer.py — Multi-scale Structural Homogenization Engine
========================================================================
물리 로직: 유리섬유 배향 텐서(Fiber Orientation Tensor)를 매크로(Macro) 요소의
강성 행렬(Stiffness Matrix)로 직접 변환(Homogenization)한다.

Models:
  - Mori-Tanaka (기본): Eshelby tensor + strain concentration → effective stiffness
  - Halpin-Tsai (보조): Semi-empirical, 빠른 추정용
  - Orientation-weighted interpolation: a_ij tensor → per-cell orthotropic constants

Pipeline:
  1. Load fiber orientation tensors (from fiber_orientation.npy)
  2. Load material properties (matrix + filler from material_db.json)
  3. Per-cell homogenization (Mori-Tanaka or Halpin-Tsai)
  4. Generate CalculiX .inp *ELASTIC, TYPE=ENGINEERING CONSTANTS cards
  5. Compute global stiffness & deformation metrics
  6. Export homogenized_stiffness_map.json

Author: System Architect (Multi-scale Homogenization)
Phase: 6 — Structural Integrity Integration
"""

import os
import sys
import json
import warnings
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field

# ── Path Config ───────────────────────────────────────────────────────────────
WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"
ORIENT_NPY = WORKSPACE / "fiber_orientation.npy"
ORIENT_JSON = WORKSPACE / "fiber_orientation_summary.json"
MATERIAL_DB_JSON = WORKSPACE / "material_db.json"
OUTPUT_HOMOGENIZED = WORKSPACE / "homogenized_stiffness_map.json"
OUTPUT_INP_ORTHO = WORKSPACE / "ortho_material.inp"

# ── Default Material Constants ────────────────────────────────────────────────
DEFAULT_E_MATRIX = 2400.0    # MPa (PC base)
DEFAULT_NU_MATRIX = 0.37
DEFAULT_E_FIBER = 73000.0    # MPa (E-glass)
DEFAULT_NU_FIBER = 0.22
DEFAULT_VF = 0.09            # 9% volume fraction
DEFAULT_AR = 25.0            # L/D aspect ratio


# ==============================================================================
# Data Classes
# ==============================================================================
@dataclass
class OrthotropicConstants:
    """Per-cell orthotropic engineering constants."""
    cell_id: int
    E1: float   # MD – Machine Direction (MPa)
    E2: float   # TD – Transverse Direction (MPa)
    E3: float   # ND – Normal Direction (MPa)
    nu12: float
    nu23: float
    nu13: float
    G12: float
    G23: float
    G13: float
    a11: float  # orientation tensor diagonal
    a22: float
    a33: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "cell_id": self.cell_id,
            "E1_MPa": self.E1, "E2_MPa": self.E2, "E3_MPa": self.E3,
            "nu12": self.nu12, "nu23": self.nu23, "nu13": self.nu13,
            "G12_MPa": self.G12, "G23_MPa": self.G23, "G13_MPa": self.G13,
            "a11": self.a11, "a22": self.a22, "a33": self.a33
        }

    @property
    def stiffness_anisotropy_ratio(self) -> float:
        """E1/E2 ratio – key warpage driver."""
        return self.E1 / max(self.E2, 1.0)


@dataclass
class HomogenizationReport:
    """Complete homogenization results."""
    n_cells: int
    material_grade: str
    method: str  # "Mori-Tanaka" or "Halpin-Tsai"
    per_cell: List[OrthotropicConstants] = field(default_factory=list)
    E1_stats: Dict[str, float] = field(default_factory=dict)
    E2_stats: Dict[str, float] = field(default_factory=dict)
    E3_stats: Dict[str, float] = field(default_factory=dict)
    global_E_md: float = 0.0
    global_E_td: float = 0.0
    global_E_zd: float = 0.0
    anisotropy_ratio: float = 0.0
    estimated_warp_um: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_cells": self.n_cells,
            "material_grade": self.material_grade,
            "method": self.method,
            "E1_MPa": self.E1_stats,
            "E2_MPa": self.E2_stats,
            "E3_MPa": self.E3_stats,
            "global_E_MD_MPa": self.global_E_md,
            "global_E_TD_MPa": self.global_E_td,
            "global_E_ZD_MPa": self.global_E_zd,
            "anisotropy_ratio": self.anisotropy_ratio,
            "estimated_warp_um": self.estimated_warp_um,
            "timestamp": self.timestamp,
            "per_cell_count": len(self.per_cell)
        }


# ==============================================================================
# Material Property Loader
# ==============================================================================
def load_material_properties(
    force_grade: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Load matrix and filler properties from material_db.json.
    Returns (matrix_props, filler_props).
    """
    mfg = "Generic"
    grade = "PC+GF20"

    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
                mfg = specs.get("active_manufacturer", "Generic")
                grade = specs.get("active_grade", "PC+GF20")
        except Exception:
            pass

    if force_grade:
        grade = force_grade

    matrix_props = {
        "E_m": DEFAULT_E_MATRIX,
        "nu_m": DEFAULT_NU_MATRIX,
        "CTE": 6.5e-5
    }
    filler_props = {
        "E_f": DEFAULT_E_FIBER,
        "nu_f": DEFAULT_NU_FIBER,
        "vf": DEFAULT_VF,
        "ar": DEFAULT_AR,
        "CTE_f": 5.0e-6
    }

    if MATERIAL_DB_JSON.exists():
        try:
            with open(MATERIAL_DB_JSON, "r", encoding="utf-8") as f:
                db = json.load(f)
                mat_data = db.get(mfg, {}).get(grade, {})
                mech = mat_data.get("Mechanical", {})
                addon = mat_data.get("Additives", None)

                matrix_props["E_m"] = mech.get("YoungsModulus", DEFAULT_E_MATRIX)
                matrix_props["nu_m"] = mech.get("PoissonsRatio", DEFAULT_NU_MATRIX)
                matrix_props["CTE"] = mech.get("CTE", 6.5e-5)

                if addon:
                    filler_props["E_f"] = addon.get("filler_modulus_MPa", DEFAULT_E_FIBER)
                    filler_props["nu_f"] = addon.get("filler_poisson", DEFAULT_NU_FIBER)
                    filler_props["vf"] = addon.get("volume_fraction", DEFAULT_VF)
                    filler_props["ar"] = addon.get("aspect_ratio", DEFAULT_AR)
                    filler_props["CTE_f"] = addon.get("filler_CTE", 5.0e-6)
        except Exception:
            pass

    return matrix_props, filler_props


# ==============================================================================
# Mori-Tanaka Homogenization Model
# ==============================================================================
def eshelby_tensor_spheroid(nu_m: float, ar: float) -> np.ndarray:
    """
    Compute Eshelby tensor S for a spheroidal inclusion (prolate, a1 > a2 = a3).
    
    Based on closed-form expressions for an isotropic matrix with Poisson ratio nu_m
    and inclusion aspect ratio AR = a1/a3 (length/diameter).

    Parameters
    ----------
    nu_m : float — matrix Poisson ratio
    ar   : float — aspect ratio (L/D, >1 for fiber)

    Returns
    -------
    S : (6,6) Eshelby tensor in Voigt notation (11,22,33,12,13,23)
    """
    if ar < 1.0:
        ar = 1.0 / ar  # convert oblate to prolate equivalent

    # For prolate spheroid (ar > 1)
    # g = ar / (ar^2 - 1)^(3/2) * [ar * sqrt(ar^2-1) - arccosh(ar)]
    if ar > 1.001:
        ar2 = ar * ar
        sqrt_term = np.sqrt(ar2 - 1.0)
        g = ar / (sqrt_term ** 3) * (ar * sqrt_term - np.arccosh(ar))
    else:
        # Sphere limit (ar → 1): g = 1/3
        g = 1.0 / 3.0

    nu = nu_m
    denom = 8.0 * np.pi * (1.0 - nu)

    # Closed-form Eshelby components for spheroid (Mura, 1987; Qu & Cherkaoui, 2006)
    S1111 = (1.0 / denom) * (
        (1.0 - 2.0 * nu) * (1.0 - 2.0 * g)
        + (3.0 * ar2 - 1.0) / (ar2 - 1.0) * (1.0 - 2.0 * nu + 2.0 * g)
    ) if ar > 1.001 else (7.0 - 5.0 * nu) / (15.0 * (1.0 - nu))

    S2222 = S3333_val(ar, nu, g, denom)
    S1122 = S1122_val(ar, nu, g, denom)
    S2211 = S2211_val(ar, nu, g, denom)
    S2233 = S2233_val(ar, nu, g, denom)
    S2323 = S2323_val(ar, nu, g, denom)
    S1212 = S1212_val(ar, nu, g, denom)

    # Build 6x6 Eshelby tensor (Voigt: 11,22,33,12,13,23)
    S = np.zeros((6, 6))
    S[0, 0] = S1111
    S[0, 1] = S1122
    S[0, 2] = S1122
    S[1, 0] = S2211
    S[1, 1] = S2222
    S[1, 2] = S2233
    S[2, 0] = S2211
    S[2, 1] = S2233
    S[2, 2] = S2222
    S[3, 3] = 2.0 * S1212  # Voigt factor: epsilon_12 = 2*eps_12_eng
    S[4, 4] = 2.0 * S1212
    S[5, 5] = 2.0 * S2323

    return S


def S3333_val(ar, nu, g, denom):
    """Helper for Eshelby S3333 (same as S2222 for transverse isotropy)."""
    if ar > 1.001:
        ar2 = ar * ar
        return (1.0 / denom) * (
            (1.0 - 2.0 * nu) * (1.0 - 2.0 * g)
            + (3.0 * ar2 - 1.0) / (ar2 - 1.0) * (1.0 - 2.0 * nu + 2.0 * g)
        )
    return (7.0 - 5.0 * nu) / (15.0 * (1.0 - nu))


def S1122_val(ar, nu, g, denom):
    """Helper for Eshelby S1122."""
    if ar > 1.001:
        ar2 = ar * ar
        return (1.0 / denom) * (
            -(1.0 - 2.0 * nu)
            + (ar2 + 1.0) / (ar2 - 1.0) * (1.0 - 2.0 * nu - 2.0 * g)
        )
    return (5.0 * nu - 1.0) / (15.0 * (1.0 - nu))


def S2211_val(ar, nu, g, denom):
    """Helper for Eshelby S2211."""
    if ar > 1.001:
        ar2 = ar * ar
        return (1.0 / denom) * (
            -(1.0 - 2.0 * nu) * ar2 / (ar2 - 1.0)
            + (1.0 / (2.0 * (ar2 - 1.0))) * (3.0 * ar2 / (ar2 - 1.0) - (1.0 - 2.0 * nu)) * (1.0 - 2.0 * g)
        )
    return (5.0 * nu - 1.0) / (15.0 * (1.0 - nu))


def S2233_val(ar, nu, g, denom):
    """Helper for Eshelby S2233."""
    if ar > 1.001:
        ar2 = ar * ar
        return (1.0 / denom) * (
            (1.0 - (1.0 - 2.0 * nu) / (2.0 * (ar2 - 1.0)))
            * (1.0 - 2.0 * g)
        )
    return (4.0 - 5.0 * nu) / (15.0 * (1.0 - nu))


def S2323_val(ar, nu, g, denom):
    """Helper for Eshelby S2323."""
    if ar > 1.001:
        ar2 = ar * ar
        return (1.0 / denom) * (
            (1.0 - 2.0 * nu) * (ar2 + 1.0) / (2.0 * (ar2 - 1.0))
            - (1.0 / 4.0) * (1.0 - 2.0 * nu - (3.0 * ar2 + 1.0) / (ar2 - 1.0)) * (1.0 - 2.0 * g)
        )
    return (4.0 - 5.0 * nu) / (15.0 * (1.0 - nu))


def S1212_val(ar, nu, g, denom):
    """Helper for Eshelby S1212."""
    if ar > 1.001:
        ar2 = ar * ar
        return (1.0 / denom) * (
            -(1.0 - 2.0 * nu) * ar2 / (2.0 * (ar2 - 1.0))
            + (1.0 / 4.0) * (3.0 * ar2 / (ar2 - 1.0) - (1.0 - 2.0 * nu)) * (1.0 - 2.0 * g)
        )
    return (4.0 - 5.0 * nu) / (15.0 * (1.0 - nu))


def isotropic_stiffness_tensor(E: float, nu: float) -> np.ndarray:
    """Build 6x6 isotropic stiffness matrix C in Voigt notation."""
    C = np.zeros((6, 6))
    lam = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu))
    mu = E / (2.0 * (1.0 + nu))
    C[0, 0] = C[1, 1] = C[2, 2] = lam + 2.0 * mu
    C[0, 1] = C[0, 2] = C[1, 0] = C[1, 2] = C[2, 0] = C[2, 1] = lam
    C[3, 3] = C[4, 4] = C[5, 5] = mu
    return C


def mori_tanaka_homogenize(
    E_m: float, nu_m: float,
    E_f: float, nu_f: float,
    vf: float, ar: float
) -> Dict[str, float]:
    """
    Mori-Tanaka mean-field homogenization for aligned short-fiber composite.

    Steps:
      1. Compute Eshelby tensor S (matrix properties + inclusion aspect ratio)
      2. Compute strain concentration tensor A_dilute = [I + S:C_m^{-1}:(C_f - C_m)]^{-1}
      3. Compute Mori-Tanaka concentration: A_MT = A_dilute : [(1-vf)*I + vf*A_dilute]^{-1}
      4. Effective stiffness: C_eff = C_m + vf * (C_f - C_m) : A_MT

    Returns
    -------
    dict with E1, E2, E3, G12, G23, G13, nu12, nu23, nu13 (all MPa or dimensionless)
    """
    # Stiffness tensors in Voigt (6x6)
    C_m = isotropic_stiffness_tensor(E_m, nu_m)
    C_f = isotropic_stiffness_tensor(E_f, nu_f)

    # Eshelby tensor
    S = eshelby_tensor_spheroid(nu_m, ar)

    # Compliance of matrix
    C_m_inv = np.linalg.inv(C_m)
    delta_C = C_f - C_m

    # Dilute strain concentration tensor: A_dil = [I + S : C_m^{-1} : (C_f - C_m)]^{-1}
    I6 = np.eye(6)
    M_dil = I6 + S @ C_m_inv @ delta_C
    A_dil = np.linalg.inv(M_dil)

    # Mori-Tanaka concentration: A_MT = A_dil : [(1-vf)*I + vf*A_dil]^{-1}
    avg_A = (1.0 - vf) * I6 + vf * A_dil
    A_MT = A_dil @ np.linalg.inv(avg_A)

    # Effective stiffness: C_eff = C_m + vf * (C_f - C_m) : A_MT
    C_eff = C_m + vf * delta_C @ A_MT

    # Extract engineering constants from C_eff
    # Compliance S_eff = C_eff^{-1}
    S_eff = np.linalg.inv(C_eff)

    E1 = 1.0 / S_eff[0, 0]
    E2 = 1.0 / S_eff[1, 1]
    E3 = 1.0 / S_eff[2, 2]
    nu12 = -S_eff[0, 1] * E1
    nu13 = -S_eff[0, 2] * E1
    nu23 = -S_eff[1, 2] * E2
    G12 = 1.0 / S_eff[3, 3]
    G13 = 1.0 / S_eff[4, 4]
    G23 = 1.0 / S_eff[5, 5]

    # Physicality checks and clamping
    E1 = max(E1, E_m * 1.01)
    E2 = max(E2, E_m * 0.5)
    E3 = max(E3, E_m * 0.5)
    G12 = max(G12, E_m * 0.1)
    G13 = max(G13, E_m * 0.1)
    G23 = max(G23, E_m * 0.1)

    return {
        "E1": E1, "E2": E2, "E3": E3,
        "nu12": nu12, "nu13": nu13, "nu23": nu23,
        "G12": G12, "G13": G13, "G23": G23
    }


# ==============================================================================
# Halpin-Tsai Homogenization (from fsi_mapper.py — reused)
# ==============================================================================
def halpin_tsai_homogenize(
    E_m: float, E_f: float, nu_m: float,
    vf: float, ar: float
) -> Dict[str, float]:
    """
    Halpin-Tsai semi-empirical composite model.
    Identical to fsi_mapper.halpin_tsai_homogenize() for standalone use.
    """
    xi_L = 2.0 * ar
    eta_L = (E_f / E_m - 1.0) / (E_f / E_m + xi_L)
    E_L = E_m * (1.0 + xi_L * eta_L * vf) / (1.0 - eta_L * vf)

    xi_T = 2.0
    eta_T = (E_f / E_m - 1.0) / (E_f / E_m + xi_T)
    E_T = E_m * (1.0 + xi_T * eta_T * vf) / (1.0 - eta_T * vf)

    G_m = E_m / (2.0 * (1.0 + nu_m))
    nu_f = 0.20
    G_f = E_f / (2.0 * (1.0 + nu_f))
    xi_G = 1.0
    eta_G = (G_f / G_m - 1.0) / (G_f / G_m + xi_G)
    G_12 = G_m * (1.0 + xi_G * eta_G * vf) / (1.0 - eta_G * vf)
    G_13 = G_12
    G_23 = G_m

    nu_12 = nu_m * (1.0 - vf) + nu_f * vf
    nu_13 = nu_12
    nu_23 = nu_m

    return {
        "E1": E_L, "E2": E_T, "E3": E_T,
        "nu12": nu_12, "nu13": nu_13, "nu23": nu_23,
        "G12": G_12, "G13": G_13, "G23": G_23
    }


# ==============================================================================
# Orientation-weighted Orthotropic Mapping
# ==============================================================================
def orientation_weighted_constants(
    a11: float, a22: float, a33: float,
    ud_constants: Dict[str, float]
) -> OrthotropicConstants:
    """
    Apply orientation weighting to UD composite constants:
      E_i_eff = a_ii * E_L + (1 - a_ii) * E_T

    Parameters
    ----------
    a11, a22, a33 : diagonal components of orientation tensor (trace=1)
    ud_constants : dict with 'E1'(E_L), 'E2'(E_T), 'E3', 'G12', etc.

    Returns
    -------
    OrthotropicConstants with orientation-weighted values
    """
    E_L = ud_constants["E1"]
    E_T = ud_constants["E2"]

    # Clamp and normalize orientation values
    a11_c = max(0.0, min(1.0, a11))
    a22_c = max(0.0, min(1.0, a22))
    a33_c = max(0.0, min(1.0, a33))
    s = a11_c + a22_c + a33_c
    if s > 1e-10:
        a11_c /= s
        a22_c /= s
        a33_c /= s

    E1 = a11_c * E_L + (1.0 - a11_c) * E_T
    E2 = a22_c * E_L + (1.0 - a22_c) * E_T
    E3 = a33_c * E_L + (1.0 - a33_c) * E_T

    G12 = ud_constants.get("G12", E_m_default() * 0.3)
    G23 = ud_constants.get("G23", E_m_default() * 0.3)
    G13 = ud_constants.get("G13", E_m_default() * 0.3)

    nu12 = ud_constants.get("nu12", 0.35)
    nu23 = ud_constants.get("nu23", 0.35)
    nu13 = ud_constants.get("nu13", 0.35)

    return OrthotropicConstants(
        cell_id=-1,
        E1=E1, E2=E2, E3=E3,
        nu12=nu12, nu23=nu23, nu13=nu13,
        G12=G12, G23=G23, G13=G13,
        a11=a11_c, a22=a22_c, a33=a33_c
    )


def E_m_default() -> float:
    return DEFAULT_E_MATRIX


# ==============================================================================
# Structural Homogenizer — Main Engine
# ==============================================================================
class StructuralHomogenizer:
    """
    Multi-scale homogenization engine that converts fiber orientation tensor
    field into element-wise orthotropic elastic constants for structural FEA.

    Usage:
        engine = StructuralHomogenizer(method="Mori-Tanaka")
        report = engine.run()
        engine.export_calculix_cards("structural_run.inp")
        engine.export_stiffness_map()
    """

    def __init__(self, method: str = "Mori-Tanaka"):
        """
        Parameters
        ----------
        method : "Mori-Tanaka" or "Halpin-Tsai"
        """
        self.method = method
        self.matrix_props: Dict[str, Any] = {}
        self.filler_props: Dict[str, Any] = {}
        self.ud_constants: Dict[str, float] = {}
        self.a_tensors: Optional[np.ndarray] = None
        self.per_cell: List[OrthotropicConstants] = []
        self.report: Optional[HomogenizationReport] = None

    # ── Step 1: Load inputs ────────────────────────────────────────────────
    def load_materials(self, force_grade: Optional[str] = None):
        """Load matrix and filler properties."""
        self.matrix_props, self.filler_props = load_material_properties(force_grade)
        print(f"[Homogenizer] Matrix: E={self.matrix_props['E_m']} MPa, ν={self.matrix_props['nu_m']}")
        print(f"[Homogenizer] Filler: E={self.filler_props['E_f']} MPa, vf={self.filler_props['vf']}, AR={self.filler_props['ar']}")

    def load_orientation_tensors(self):
        """Load fiber orientation tensors from .npy cache or compute them."""
        if ORIENT_NPY.exists():
            self.a_tensors = np.load(str(ORIENT_NPY))
            print(f"[Homogenizer] Loaded {self.a_tensors.shape[0]} orientation tensors")
        else:
            print("[Homogenizer] No orientation cache. Running fiber_orientator...")
            import subprocess
            res = subprocess.run(
                [sys.executable, "fiber_orientator.py", str(self.filler_props.get("ar", 25.0))],
                capture_output=True, text=True, cwd=str(WORKSPACE)
            )
            if ORIENT_NPY.exists():
                self.a_tensors = np.load(str(ORIENT_NPY))
                print(f"[Homogenizer] Generated {self.a_tensors.shape[0]} orientation tensors")
            else:
                raise FileNotFoundError("fiber_orientation.npy not found after fiber_orientator run.")

    # ── Step 2: Homogenization ─────────────────────────────────────────────
    def homogenize(self) -> HomogenizationReport:
        """Run per-cell homogenization for all cells."""
        if self.a_tensors is None:
            self.load_orientation_tensors()
        if not self.matrix_props:
            self.load_materials()

        E_m = self.matrix_props["E_m"]
        nu_m = self.matrix_props["nu_m"]
        E_f = self.filler_props["E_f"]
        nu_f = self.filler_props.get("nu_f", 0.22)
        vf = self.filler_props["vf"]
        ar = self.filler_props["ar"]

        # Compute UD composite baseline
        if self.method == "Mori-Tanaka":
            print(f"[Homogenizer] Computing Mori-Tanaka UD baseline...")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                self.ud_constants = mori_tanaka_homogenize(E_m, nu_m, E_f, nu_f, vf, ar)
        else:
            print(f"[Homogenizer] Computing Halpin-Tsai UD baseline...")
            self.ud_constants = halpin_tsai_homogenize(E_m, E_f, nu_m, vf, ar)

        print(f"  UD E_L (MD) = {self.ud_constants['E1']:.0f} MPa")
        print(f"  UD E_T (TD) = {self.ud_constants['E2']:.0f} MPa")

        # Per-cell orientation-weighted mapping
        n = self.a_tensors.shape[0]
        self.per_cell = []
        E1_list, E2_list, E3_list = [], [], []

        for i in range(n):
            a11 = float(self.a_tensors[i, 0, 0])
            a22 = float(self.a_tensors[i, 1, 1])
            a33 = float(self.a_tensors[i, 2, 2])
            ortho = orientation_weighted_constants(a11, a22, a33, self.ud_constants)
            ortho.cell_id = i
            self.per_cell.append(ortho)
            E1_list.append(ortho.E1)
            E2_list.append(ortho.E2)
            E3_list.append(ortho.E3)

        E1_arr = np.array(E1_list)
        E2_arr = np.array(E2_list)
        E3_arr = np.array(E3_list)

        # Build report
        from datetime import datetime
        report = HomogenizationReport(
            n_cells=n,
            material_grade="PC+GF20",
            method=self.method,
            per_cell=self.per_cell,
            E1_stats={
                "mean": float(np.mean(E1_arr)),
                "median": float(np.median(E1_arr)),
                "std": float(np.std(E1_arr)),
                "min": float(np.min(E1_arr)),
                "max": float(np.max(E1_arr))
            },
            E2_stats={
                "mean": float(np.mean(E2_arr)),
                "median": float(np.median(E2_arr)),
                "std": float(np.std(E2_arr)),
                "min": float(np.min(E2_arr)),
                "max": float(np.max(E2_arr))
            },
            E3_stats={
                "mean": float(np.mean(E3_arr)),
                "median": float(np.median(E3_arr)),
                "std": float(np.std(E3_arr)),
                "min": float(np.min(E3_arr)),
                "max": float(np.max(E3_arr))
            },
            global_E_md=float(np.median(E1_arr)),
            global_E_td=float(np.median(E2_arr)),
            global_E_zd=float(np.median(E3_arr)),
            anisotropy_ratio=float(np.median(E1_arr) / max(np.median(E2_arr), 1.0)),
            estimated_warp_um=self._estimate_warpage(E1_arr, E2_arr),
            timestamp=datetime.now().isoformat()
        )
        self.report = report
        return report

    def _estimate_warpage(self, E1_arr: np.ndarray, E2_arr: np.ndarray) -> float:
        """Estimate Z-axis warpage from stiffness anisotropy."""
        E_md = float(np.median(E1_arr))
        E_td = float(np.median(E2_arr))
        E_avg = (E_md + E_td) / 2.0
        L_char = 0.150  # m (laptop housing)
        thickness = 0.002  # m
        alpha_avg = 6.5e-5  # /K
        delta_T = 120.0  # K
        anisotropy_ratio = (E_md - E_td) / (E_avg + 1e-9)
        warp_m = (alpha_avg * delta_T * L_char**2) / (8.0 * thickness) * abs(anisotropy_ratio) * 0.12
        return warp_m * 1e6  # μm

    # ── Step 3: Export CalculiX Cards ──────────────────────────────────────
    def export_calculix_cards(self, output_path: Optional[str] = None) -> str:
        """
        Generate CalculiX *ELASTIC, TYPE=ENGINEERING CONSTANTS cards for each element.
        Each element gets its own orthotropic constants based on local fiber orientation.
        """
        if not self.per_cell:
            raise RuntimeError("Run homogenize() first.")

        out_path = Path(output_path) if output_path else OUTPUT_INP_ORTHO
        lines = [
            "** Orthotropic Material Cards — Multi-scale Homogenization",
            f"** Method: {self.method} | Material: {self.report.material_grade if self.report else 'PC+GF20'}",
            f"** Cells: {len(self.per_cell)}",
            "** Each cell has unique *ELASTIC, TYPE=ENGINEERING CONSTANTS based on local a_ij",
            "**"
        ]

        # Group by unique (or near-unique) sets to avoid excessive materials
        # For large meshes, use element sets with tolerance-based grouping
        tolerance_pct = 2.0  # group cells within 2% stiffness difference
        groups = self._group_by_stiffness(tolerance_pct)

        lines.append(f"** {len(groups)} unique material groups (tolerance={tolerance_pct}%)")
        lines.append("**")

        mat_name_map = {}  # cell_id → material name
        for g_idx, (g_name, cell_ids) in enumerate(groups.items()):
            rep_cell = self.per_cell[cell_ids[0]]
            lines.append(f"*MATERIAL, NAME={g_name}")
            lines.append("*ELASTIC, TYPE=ENGINEERING CONSTANTS")
            lines.append(
                f"  {rep_cell.E1:.2f}, {rep_cell.E2:.2f}, {rep_cell.E3:.2f}, "
                f"{rep_cell.nu12:.6f}, {rep_cell.nu13:.6f}, {rep_cell.nu23:.6f}, "
                f"{rep_cell.G12:.2f}, {rep_cell.G13:.2f}, {rep_cell.G23:.2f}"
            )
            # Also write density and expansion
            lines.append("*DENSITY")
            lines.append("1430.0")
            # CTE approximation (matrix CTE weighted by orientation)
            cte_m = self.matrix_props.get("CTE", 6.5e-5)
            cte_f = self.filler_props.get("CTE_f", 5.0e-6)
            alpha_L = (cte_m * self.matrix_props["E_m"] * (1 - self.filler_props["vf"])
                       + cte_f * self.filler_props["E_f"] * self.filler_props["vf"]) / \
                      (self.matrix_props["E_m"] * (1 - self.filler_props["vf"])
                       + self.filler_props["E_f"] * self.filler_props["vf"] + 1e-9)
            alpha_T = cte_m * 1.3  # approximate transverse CTE
            lines.append("*EXPANSION, TYPE=ORTHO")
            lines.append(f"  {alpha_L:.4e}, {alpha_T:.4e}, {alpha_T:.4e}")
            lines.append("")

            for cid in cell_ids:
                mat_name_map[cid] = g_name

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        print(f"[Homogenizer] CalculiX cards exported to {out_path.name} ({len(groups)} material groups)")
        return str(out_path)

    def _group_by_stiffness(self, tolerance_pct: float) -> Dict[str, List[int]]:
        """Group cells by stiffness similarity to reduce material count."""
        groups: Dict[str, List[int]] = {}
        group_idx = 0

        for i, cell in enumerate(self.per_cell):
            found = False
            for g_name, cell_ids in groups.items():
                rep = self.per_cell[cell_ids[0]]
                if (abs(cell.E1 - rep.E1) / max(rep.E1, 1.0) * 100 < tolerance_pct
                        and abs(cell.E2 - rep.E2) / max(rep.E2, 1.0) * 100 < tolerance_pct):
                    cell_ids.append(i)
                    found = True
                    break
            if not found:
                g_name = f"ORTHO_GROUP_{group_idx}"
                groups[g_name] = [i]
                group_idx += 1

        return groups

    # ── Step 4: Export Stiffness Map ───────────────────────────────────────
    def export_stiffness_map(self, output_path: Optional[str] = None) -> str:
        """Export homogenized stiffness map as JSON for visualization."""
        if not self.report:
            raise RuntimeError("Run homogenize() first.")

        out_path = Path(output_path) if output_path else OUTPUT_HOMOGENIZED
        data = self.report.to_dict()
        # Add per_cell summary (not full list for large meshes → sample)
        sample_size = min(200, len(self.per_cell))
        data["per_cell_sample"] = [c.to_dict() for c in self.per_cell[:sample_size]]
        data["per_cell_full_count"] = len(self.per_cell)

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"[Homogenizer] Stiffness map exported to {out_path.name}")
        return str(out_path)

    # ── Step 5: Run Full Pipeline ──────────────────────────────────────────
    def run(self, force_grade: Optional[str] = None) -> HomogenizationReport:
        """Execute complete homogenization pipeline."""
        print("=" * 65)
        print(f"  STRUCTURAL HOMOGENIZER — {self.method}")
        print("=" * 65)

        self.load_materials(force_grade)
        self.load_orientation_tensors()
        report = self.homogenize()

        print(f"\n[Homogenization Results]")
        print(f"  Cells processed       : {report.n_cells}")
        print(f"  Global E_MD (median)  : {report.global_E_md:.0f} MPa")
        print(f"  Global E_TD (median)  : {report.global_E_td:.0f} MPa")
        print(f"  Global E_ZD (median)  : {report.global_E_zd:.0f} MPa")
        print(f"  Anisotropy Ratio      : {report.anisotropy_ratio:.4f}")
        print(f"  Estimated Z-warp      : {report.estimated_warp_um:.2f} μm")
        print(f"  Stiffness E1 range    : [{report.E1_stats['min']:.0f}, {report.E1_stats['max']:.0f}] MPa")
        print("=" * 65)

        return report

# ==============================================================================
# Module Entry Point
# ==============================================================================
def run_structural_homogenizer(
    method: str = "Mori-Tanaka",
    material_grade: Optional[str] = None
) -> HomogenizationReport:
    """
    Top-level entry point for structural homogenization.

    Parameters
    ----------
    method : "Mori-Tanaka" or "Halpin-Tsai"
    material_grade : e.g., "PC+GF20", "PC", "ABS+Talc15"

    Returns
    -------
    HomogenizationReport
    """
    engine = StructuralHomogenizer(method=method)
    report = engine.run(force_grade=material_grade)

    # Auto-export
    engine.export_calculix_cards()
    engine.export_stiffness_map()

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-scale Structural Homogenizer")
    parser.add_argument("--method", default="Mori-Tanaka",
                        choices=["Mori-Tanaka", "Halpin-Tsai"],
                        help="Homogenization method")
    parser.add_argument("--grade", default=None,
                        help="Material grade (e.g., PC+GF20)")
    args = parser.parse_args()

    report = run_structural_homogenizer(method=args.method, material_grade=args.grade)
    print(f"\n[DONE] Homogenization complete. Report saved to {OUTPUT_HOMOGENIZED}")