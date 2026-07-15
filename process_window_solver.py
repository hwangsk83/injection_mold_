#!/usr/bin/env python3
"""
process_window_solver.py - Expert Auto-Wizard: Molding Window 2D Contour Solver

Computes quality metrics at every (T, P) grid point, then renders
an Acceptable Region contour map with optimal point highlight.
"""
import json, math, sys, os
from pathlib import Path
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"
WINDOW_SOLVER_PNG = WORKSPACE / "process_window_solver.png"


def load_specs():
    try:
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def physics_model(p_pack_mpa, t_melt_k, t_mold_k, max_p_limit=180.0, proj_area=0.011250):
    """Synthetic physics model for quality prediction at any (T,P) point."""
    p_cavity_mpa = p_pack_mpa * 0.65 + 10.0 * (t_melt_k - 563.15) / 40.0 - 5.0 * (t_mold_k - 333.15) / 40.0
    p_cavity_mpa = max(5.0, p_cavity_mpa)
    req_ton = (p_cavity_mpa * 1e6) * proj_area * 101.97 * 1e-6
    warpage_base = 0.52
    warpage = (warpage_base - 0.18 * (p_pack_mpa - 60.0) / 40.0 - 0.14 * 1.0
               + 0.07 * (t_melt_k - 563.15) / 40.0 - 0.06 * (t_mold_k - 333.15) / 40.0)
    warpage = max(0.08, warpage)
    return {"p_cavity_mpa": p_cavity_mpa, "req_ton": req_ton, "warpage_mm": warpage}

def solve_process_window():
    if not HAS_MPL:
        print("[WINDOW SOLVER] Matplotlib not available.")
        return None

    specs = load_specs()
    clamp_ton = specs.get("clamping_force_ton", 200.0)
    max_p_mpa = specs.get("max_pressure_mpa", 180.0)
    proj_area = specs.get("projected_area_m2", 0.011250)
    flash_line = (clamp_ton * 9806.65) / (proj_area * 1e6)

    # Create grid
    T_grid = np.linspace(450, 610, 51)
    P_grid = np.linspace(10, 180, 51)
    TT, PP = np.meshgrid(T_grid, P_grid)
    warpage_map = np.zeros_like(TT)
    acceptable = np.zeros_like(TT, dtype=bool)

    best_warp = 999
    best_T, best_P = 563, 100

    for i in range(len(P_grid)):
        for j in range(len(T_grid)):
            T = TT[i, j]
            P = PP[i, j]
            phys = physics_model(P, T, 353.15, max_p_mpa, proj_area)
            w = phys["warpage_mm"]
            warpage_map[i, j] = w
            # Acceptable if: P < flash_line, P < max_p_mpa, ton < clamp, T in [473, 593]
            if (P <= flash_line and P <= max_p_mpa and phys["req_ton"] <= clamp_ton
                    and 473.15 <= T <= 593.15):
                acceptable[i, j] = True
                if w < best_warp:
                    best_warp = w
                    best_T, best_P = T, P

    # Plot
    fig, ax = plt.subplots(figsize=(11, 8))
    fig.patch.set_facecolor('#0f172a')
    ax.set_facecolor('#1e293b')

    # Warpage contour
    cs = ax.contourf(TT, PP, warpage_map, levels=20, cmap='viridis', alpha=0.85)
    cbar = fig.colorbar(cs, ax=ax)
    cbar.set_label('Warpage (mm)', color='white')
    cbar.ax.tick_params(colors='white')

    # Acceptable region overlay (hatch pattern)
    ax.contourf(TT, PP, acceptable.astype(float), levels=[0.5, 1.5], colors='none',
                hatches=['//'], alpha=0.15)

    # Boundary lines
    ax.axhline(y=flash_line, color='#ef4444', linestyle='--', linewidth=2, 
               label=f'Flash Limit: {flash_line:.0f} MPa')
    ax.axvline(x=473.15, color='#3b82f6', linestyle='-.', linewidth=1.5, alpha=0.7)
    ax.axvline(x=593.15, color='#ef4444', linestyle='-.', linewidth=1.5, alpha=0.7)

    # Optimal point
    ax.scatter([best_T], [best_P], c='#22c55e', s=200, marker='*', edgecolors='white',
               linewidth=2, zorder=6, label=f'Optimal: {best_T:.0f}K / {best_P:.0f}MPa\nWarpage: {best_warp:.4f}mm')

    ax.set_xlabel('Melt Temperature (K)', color='white', fontsize=12)
    ax.set_ylabel('Injection Pressure (MPa)', color='white', fontsize=12)
    ax.set_title('SOLVER: Molding Process Window Contour Map', color='white', fontsize=14, fontweight='bold')
    ax.tick_params(colors='white')
    ax.legend(loc='upper right', facecolor='#1e293b', edgecolor='#475569', fontsize=8, labelcolor='white')
    ax.set_xlim(450, 610)
    ax.set_ylim(0, 200)

    plt.tight_layout()
    plt.savefig(str(WINDOW_SOLVER_PNG), dpi=150, facecolor='#0f172a')
    plt.close()

    print(f"[WINDOW SOLVER] Contour map saved: {WINDOW_SOLVER_PNG.name}")
    print(f"  Optimal point: T={best_T:.0f}K, P={best_P:.0f}MPa, Warpage={best_warp:.4f}mm")
    print(f"  Grid: {len(P_grid)}x{len(T_grid)} = {len(P_grid)*len(T_grid)} points evaluated")
    return best_T, best_P, best_warp

if __name__ == "__main__":
    solve_process_window()