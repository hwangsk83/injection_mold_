# -*- coding: utf-8 -*-
"""
steady_state_cycle_solver.py — Cyclic Thermal Equilibrium Solver for Injection Molding
======================================================================================
물리 로직: 1회 사출이 아닌, 금형이 열적 평형(Thermal Equilibrium)에 도달할 때까지
10회 이상의 사출 사이클을 모사한다.

Physics:
  - Each cycle: Fill → Pack → Cool → Eject
  - Residual heat from cycle N becomes initial condition for cycle N+1
  - Convergence criterion: |T_mold_surface(N) - T_mold_surface(N-1)|_max < 2K
  - Lumped-parameter thermal model (fast analytical approximation)

Pipeline:
  1. Define mold thermal properties (mass, Cp, k, h_conv)
  2. Define process conditions (melt T, mold T_initial, cycle time)
  3. Run N cycles with thermal propagation
  4. Track cycle-to-cycle mold surface temperature
  5. Detect steady-state convergence
  6. Compute quality metrics (warpage/shrinkage sensitivity to thermal drift)

Output:
  - cycle_temperature_history.csv : Full thermal tracking
  - steady_state_convergence.json : Convergence report & quality assessment

Author: System Architect (Steady-State Cycle Solver)
Phase: 6 — Structural Integrity Integration
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from datetime import datetime

# ── Path Config ───────────────────────────────────────────────────────────────
WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"
OUTPUT_HISTORY_CSV = WORKSPACE / "cycle_temperature_history.csv"
OUTPUT_CONVERGENCE = WORKSPACE / "steady_state_convergence.json"

# ── Mold Thermal Defaults ─────────────────────────────────────────────────────
# Typical P20 tool steel mold (laptop housing: ~400x300x150 mm mold block)
MOLD_MASS_KG = 85.0             # kg (simplified mold half)
MOLD_CP = 460.0                 # J/(kg·K) — tool steel P20
MOLD_K = 29.0                   # W/(m·K) — tool steel thermal conductivity
MOLD_AREA_M2 = 0.45             # m² — effective heat transfer area (cavity + cooling)
H_CONV_COOLANT = 2500.0         # W/(m²·K) — water cooling channel convection
H_CONV_AIR = 15.0               # W/(m²·K) — natural convection to ambient
T_COOLANT = 298.15              # K (25°C) — cooling water inlet temperature
T_AMBIENT = 298.15              # K (25°C) — shop floor ambient

# ── Process Defaults ──────────────────────────────────────────────────────────
T_MELT = 563.15                  # K (290°C) — PC melt temperature
T_MOLD_INITIAL = 353.15          # K (80°C) — mold initial temperature
CYCLE_TIME = 25.0                # s — total cycle time
FILL_TIME = 3.0                  # s — fill stage
PACK_TIME = 8.0                  # s — pack/hold stage
COOL_TIME = 12.0                 # s — active cooling stage
EJECT_MOLD_OPEN_TIME = 2.0       # s — mold open/eject

# Heat input per shot (energy from melt): Q_melt = m_shot * Cp_polymer * (T_melt - T_eject)
MASS_SHOT_KG = 0.15              # kg — shot weight
CP_POLYMER = 1850.0              # J/(kg·K)
T_EJECT = 403.15                 # K (130°C) — ejection temperature


# ==============================================================================
# Data Classes
# ==============================================================================
@dataclass
class CycleResult:
    """Results for a single molding cycle."""
    cycle_id: int
    T_mold_surface: float       # K — average mold cavity surface temp at cycle end
    T_mold_max: float           # K — max mold temperature
    T_mold_min: float           # K — min mold temperature
    Q_melt_input: float         # J — heat input from melt
    Q_coolant_extracted: float  # J — heat removed by coolant
    Q_ambient_loss: float       # J — heat lost to ambient
    delta_T_surface: float      # K — surface temperature change from previous cycle
    max_delta_T: float          # K — max temperature change from previous cycle


@dataclass
class SteadyStateReport:
    """Complete steady-state convergence analysis."""
    n_cycles: int
    converged: bool
    convergence_cycle: int      # cycle at which convergence was detected
    final_delta_T_max: float    # K — final cycle-to-cycle variation
    T_surface_final: float      # K — final equilibrium mold surface temp
    T_surface_initial: float    # K — initial mold temp
    T_surface_rise: float       # K — total temperature rise
    quality_impact: Dict[str, float] = field(default_factory=dict)
    cycle_history: List[Dict[str, float]] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "n_cycles": self.n_cycles,
            "converged": self.converged,
            "convergence_cycle": self.convergence_cycle,
            "final_delta_T_max_K": self.final_delta_T_max,
            "T_surface_final_K": self.T_surface_final,
            "T_surface_initial_K": self.T_surface_initial,
            "T_surface_rise_K": self.T_surface_rise,
            "quality_impact": self.quality_impact,
            "cycle_history": self.cycle_history,
            "timestamp": self.timestamp
        }


# ==============================================================================
# Thermal Physics Engine
# ==============================================================================
def compute_heat_input() -> float:
    """
    Compute heat input per shot (Q_melt).
    Q = m_shot * Cp * (T_melt - T_eject)
    """
    return MASS_SHOT_KG * CP_POLYMER * (T_MELT - T_EJECT)


def compute_cooling_heat_removal(T_mold: float, t_cool: float) -> float:
    """
    Compute heat extracted by cooling channels during cool time.
    Q_cool = h_conv * A * (T_mold - T_coolant) * t_cool
    """
    delta_T = max(T_mold - T_COOLANT, 0.1)
    return H_CONV_COOLANT * MOLD_AREA_M2 * 0.6 * delta_T * t_cool  # 0.6 = effective contact area


def compute_ambient_heat_loss(T_mold: float, t_open: float) -> float:
    """
    Compute heat lost to ambient during mold open/eject.
    Q_amb = h_air * A * (T_mold - T_ambient) * t_open
    """
    delta_T = max(T_mold - T_AMBIENT, 0.1)
    return H_CONV_AIR * MOLD_AREA_M2 * delta_T * t_open


def update_mold_temperature(
    T_mold: float,
    Q_melt: float,
    t_cycle: float
) -> Tuple[float, float, float, float]:
    """
    Update mold temperature for one complete cycle.

    Physics:
      T_new = T_old + (Q_melt - Q_cool - Q_amb) / (mold_mass * Cp)

    Returns (T_new, Q_cool, Q_amb, delta_T)
    """
    # Step 1: Melt fills cavity → heat transfer to mold
    Q_cool = compute_cooling_heat_removal(T_mold, COOL_TIME)
    Q_amb = compute_ambient_heat_loss(T_mold, EJECT_MOLD_OPEN_TIME)

    # Net heat balance
    Q_net = Q_melt - Q_cool - Q_amb
    delta_T = Q_net / (MOLD_MASS_KG * MOLD_CP)

    # Clamp to physical range
    T_new = T_mold + delta_T
    T_new = max(T_COOLANT + 5.0, min(T_new, T_MELT - 20.0))

    return T_new, Q_cool, Q_amb, delta_T


# ==============================================================================
# Quality Impact Estimator
# ==============================================================================
def estimate_quality_impact(
    T_initial: float,
    T_final: float,
    n_cycles: int
) -> Dict[str, float]:
    """
    Estimate how thermal drift affects part quality.

    Key relationships:
      - Warpage ∝ ΔT across part thickness → proportional to |T_mold - T_eject|
      - Shrinkage ∝ (T_melt - T_mold) → higher mold temp = less shrinkage
      - Dimensional stability ∝ σ(T_surface over last 3 cycles)

    Returns dict with quality metrics.
    """
    T_drift = T_final - T_initial
    T_mean = (T_initial + T_final) / 2.0

    # Warpage sensitivity: larger T difference = more warpage
    # Typical: 1K mold T change → ~0.005 mm warpage change
    warpage_change_mm = abs(T_drift) * 0.005

    # Shrinkage: higher mold temp → lower shrinkage (polymer relaxes more)
    # d(shrinkage)/dT_mold ≈ -0.02%/K
    shrinkage_change_pct = -T_drift * 0.02

    # Dimensional stability: based on final temperature variance
    # σ_T_final / T_mean → stability index (lower is better)
    stability_index = abs(T_drift) / T_mean * 100  # percent

    # Pass/fail criteria
    warpage_pass = warpage_change_mm < 0.1  # mm
    shrinkage_pass = abs(shrinkage_change_pct) < 0.5  # percent

    return {
        "warpage_change_mm": round(warpage_change_mm, 4),
        "shrinkage_change_pct": round(shrinkage_change_pct, 3),
        "stability_index_pct": round(stability_index, 3),
        "thermal_drift_K": round(T_drift, 2),
        "warpage_pass": warpage_pass,
        "shrinkage_pass": shrinkage_pass,
        "overall_pass": warpage_pass and shrinkage_pass
    }


# ==============================================================================
# Steady-State Cycle Solver — Main Engine
# ==============================================================================
class SteadyStateCycleSolver:
    """
    Multi-cycle injection molding thermal equilibrium solver.

    Usage:
        solver = SteadyStateCycleSolver(n_cycles=10, convergence_threshold=2.0)
        report = solver.run()
        solver.export_history()
    """

    def __init__(
        self,
        n_cycles: int = 15,
        convergence_threshold: float = 2.0,
        convergence_window: int = 3
    ):
        """
        Parameters
        ----------
        n_cycles : max cycles to simulate before forced stop
        convergence_threshold : maximum allowed T change (K) for convergence
        convergence_window : number of consecutive cycles below threshold to declare steady-state
        """
        self.n_cycles = n_cycles
        self.convergence_threshold = convergence_threshold
        self.convergence_window = convergence_window
        self.T_initial: float = T_MOLD_INITIAL
        self.cycle_results: List[CycleResult] = []
        self.report: Optional[SteadyStateReport] = None

    def load_specs(self):
        """Load process specs from machine_spec.json if available."""
        global T_MELT, T_MOLD_INITIAL, T_COOLANT, CYCLE_TIME, MASS_SHOT_KG

        if SPEC_JSON.exists():
            try:
                with open(SPEC_JSON, "r", encoding="utf-8") as f:
                    specs = json.load(f)

                if "melt_temperature" in specs:
                    T_MELT = float(specs["melt_temperature"])
                if "mold_temperature" in specs:
                    T_MOLD_INITIAL = float(specs["mold_temperature"])
                    self.T_initial = T_MOLD_INITIAL
                if "coolant_temperature" in specs:
                    T_COOLANT = float(specs["coolant_temperature"])
                if "cycle_time" in specs:
                    CYCLE_TIME = float(specs["cycle_time"])
                if "shot_weight_kg" in specs:
                    MASS_SHOT_KG = float(specs["shot_weight_kg"])

                print(f"[CycleSolver] Loaded specs: T_melt={T_MELT}K, T_mold_0={T_MOLD_INITIAL}K, "
                      f"T_coolant={T_COOLANT}K")
            except Exception as e:
                print(f"[CycleSolver] Warning: Failed to load specs: {e}")

    def run_cycle(self, cycle_id: int, T_mold_prev: float) -> CycleResult:
        """
        Execute a single molding cycle.

        Parameters
        ----------
        cycle_id : cycle number (1-indexed)
        T_mold_prev : mold temperature at start of cycle (K)

        Returns
        -------
        CycleResult
        """
        Q_melt = compute_heat_input()
        T_new, Q_cool, Q_amb, delta_T = update_mold_temperature(T_mold_prev, Q_melt, CYCLE_TIME)

        # Track local extrema (simplified: surface temp = bulk temp)
        T_surface = T_new
        T_max = T_new + 3.0  # hot spots ~3K above average
        T_min = T_new - 2.0  # cooling channel proximity ~2K below average

        return CycleResult(
            cycle_id=cycle_id,
            T_mold_surface=T_surface,
            T_mold_max=T_max,
            T_mold_min=T_min,
            Q_melt_input=Q_melt,
            Q_coolant_extracted=Q_cool,
            Q_ambient_loss=Q_amb,
            delta_T_surface=T_surface - T_mold_prev,
            max_delta_T=abs(T_surface - T_mold_prev)
        )

    def check_convergence(self, results: List[CycleResult]) -> Tuple[bool, int]:
        """
        Check if thermal equilibrium has been reached.

        Convergence: max(|T_i - T_{i-1}|) < threshold for `convergence_window` consecutive cycles.
        """
        if len(results) < self.convergence_window + 1:
            return False, -1

        # Check last N cycles
        recent = results[-self.convergence_window:]
        max_delta = max(r.max_delta_T for r in recent)

        if max_delta < self.convergence_threshold:
            return True, results[-1].cycle_id
        return False, -1

    def run(self) -> SteadyStateReport:
        """
        Execute the full multi-cycle simulation until convergence or max cycles.

        Returns
        -------
        SteadyStateReport
        """
        print("=" * 65)
        print("  STEADY-STATE CYCLE SOLVER -- Thermal Equilibrium")
        print("=" * 65)

        self.load_specs()
        self.cycle_results = []

        T_mold = self.T_initial
        Q_melt = compute_heat_input()
        print(f"\n[Init] T_mold_initial = {T_mold:.1f} K")
        print(f"[Init] Q_melt per shot = {Q_melt/1000:.2f} kJ")
        print(f"[Init] Max cycles = {self.n_cycles}, Convergence < {self.convergence_threshold} K")
        print(f"\n{'Cycle':>6s} | {'T_surface':>10s} | {'ΔT_max':>8s} | {'Q_cool':>10s} | Status")
        print("-" * 65)

        converged = False
        convergence_cycle = -1

        for cycle in range(1, self.n_cycles + 1):
            result = self.run_cycle(cycle, T_mold)
            self.cycle_results.append(result)
            T_mold = result.T_mold_surface

            # Status indicator
            if cycle == 1:
                status = "Start"
            elif result.max_delta_T < self.convergence_threshold:
                status = "✓ Stable"
            else:
                status = "→ Heating"

            print(f"  {cycle:4d}  | {result.T_mold_surface:8.2f} K | "
                  f"{result.max_delta_T:6.3f} K | {result.Q_coolant_extracted/1000:8.2f} kJ | {status}")

            # Check convergence
            is_conv, conv_cycle = self.check_convergence(self.cycle_results)
            if is_conv and not converged:
                converged = True
                convergence_cycle = conv_cycle
                print(f"  >>> THERMAL EQUILIBRIUM REACHED at Cycle {conv_cycle}")
                # Run 2 more cycles for confirmation
                for extra in range(2):
                    confirm_cycle = cycle + 1 + extra
                    if confirm_cycle > self.n_cycles:
                        break
                    result = self.run_cycle(confirm_cycle, T_mold)
                    self.cycle_results.append(result)
                    T_mold = result.T_mold_surface
                    print(f"  {confirm_cycle:4d}  | {result.T_mold_surface:8.2f} K | "
                          f"{result.max_delta_T:6.3f} K | Confirm")
                break

        # Build final report
        final_T = T_mold
        T_rise = final_T - self.T_initial

        quality = estimate_quality_impact(self.T_initial, final_T, len(self.cycle_results))

        history = []
        for r in self.cycle_results:
            history.append({
                "cycle": r.cycle_id,
                "T_surface_K": round(r.T_mold_surface, 3),
                "T_max_K": round(r.T_mold_max, 3),
                "T_min_K": round(r.T_mold_min, 3),
                "delta_T_K": round(r.delta_T_surface, 4),
                "max_delta_T_K": round(r.max_delta_T, 4)
            })

        self.report = SteadyStateReport(
            n_cycles=len(self.cycle_results),
            converged=converged,
            convergence_cycle=convergence_cycle,
            final_delta_T_max=self.cycle_results[-1].max_delta_T,
            T_surface_final=round(final_T, 3),
            T_surface_initial=round(self.T_initial, 3),
            T_surface_rise=round(T_rise, 3),
            quality_impact=quality,
            cycle_history=history,
            timestamp=datetime.now().isoformat()
        )

        # Summary
        print("\n" + "=" * 65)
        print("  STEADY-STATE ANALYSIS RESULTS")
        print("=" * 65)
        print(f"  Cycles simulated      : {self.report.n_cycles}")
        print(f"  Converged             : {'YES' if converged else 'NO'}")
        if converged:
            print(f"  Convergence at cycle  : {convergence_cycle}")
        print(f"  Final ΔT_max          : {self.report.final_delta_T_max:.4f} K")
        print(f"  T_surface (initial)   : {self.report.T_surface_initial:.1f} K")
        print(f"  T_surface (final)     : {self.report.T_surface_final:.1f} K")
        print(f"  Temperature rise      : {T_rise:.2f} K")
        print(f"\n[Quality Impact]")
        print(f"  Warpage change        : {quality['warpage_change_mm']:.4f} mm {'✓' if quality['warpage_pass'] else '✗'}")
        print(f"  Shrinkage change      : {quality['shrinkage_change_pct']:.3f}% {'✓' if quality['shrinkage_pass'] else '✗'}")
        print(f"  Stability index       : {quality['stability_index_pct']:.3f}%")
        print(f"  Overall quality       : {'PASS' if quality['overall_pass'] else 'FAIL'}")
        print("=" * 65)

        return self.report

    def export_history(self, output_path: Optional[str] = None):
        """Export cycle temperature history as CSV."""
        if not self.cycle_results:
            raise RuntimeError("Run solve() first.")

        out_path = Path(output_path) if output_path else OUTPUT_HISTORY_CSV
        lines = ["cycle,T_surface_K,T_max_K,T_min_K,delta_T_K,max_delta_T_K"]

        for r in self.cycle_results:
            lines.append(
                f"{r.cycle_id},{r.T_mold_surface:.4f},{r.T_mold_max:.4f},"
                f"{r.T_mold_min:.4f},{r.delta_T_surface:.6f},{r.max_delta_T:.6f}"
            )

        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[CycleSolver] Temperature history exported to {out_path.name}")

    def export_convergence_report(self, output_path: Optional[str] = None):
        """Export steady-state convergence report as JSON."""
        if not self.report:
            raise RuntimeError("Run solve() first.")

        out_path = Path(output_path) if output_path else OUTPUT_CONVERGENCE
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(self.report.to_dict(), f, indent=2)
        print(f"[CycleSolver] Convergence report exported to {out_path.name}")

    def export_all(self):
        """Export both history CSV and convergence JSON."""
        self.export_history()
        self.export_convergence_report()


# ==============================================================================
# Module Entry Point
# ==============================================================================
def run_steady_state_cycles(
    n_cycles: int = 15,
    convergence_threshold: float = 2.0
) -> SteadyStateReport:
    """
    Top-level entry point for steady-state cycle analysis.

    Parameters
    ----------
    n_cycles : maximum number of cycles
    convergence_threshold : thermal convergence threshold (K)

    Returns
    -------
    SteadyStateReport
    """
    solver = SteadyStateCycleSolver(
        n_cycles=n_cycles,
        convergence_threshold=convergence_threshold
    )
    report = solver.run()
    solver.export_all()
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Steady-State Cycle Solver")
    parser.add_argument("--cycles", type=int, default=15,
                        help="Maximum number of cycles")
    parser.add_argument("--threshold", type=float, default=2.0,
                        help="Convergence threshold (K)")
    args = parser.parse_args()

    report = run_steady_state_cycles(
        n_cycles=args.cycles,
        convergence_threshold=args.threshold
    )

    if report.converged:
        print(f"\n[RESULT] Mold reached thermal steady-state at cycle {report.convergence_cycle}.")
        print(f"[RESULT] Final mold surface: {report.T_surface_final:.1f} K")
    else:
        print(f"\n[RESULT] Mold did NOT converge within {args.cycles} cycles.")
        print(f"[RESULT] Final ΔT_max = {report.final_delta_T_max:.3f} K")