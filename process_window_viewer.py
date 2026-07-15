#!/usr/bin/env python3
"""
process_window_viewer.py - Molding Window Auto-Design UI

Generates a 2D process window chart (Pressure vs Temperature) with
Flash Line, Short-shot Line, Degradation Line, and Freeze-off Line.
"""
import json, math
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
DOE_CSV   = WORKSPACE / "doe_results.csv"
WINDOW_PNG = WORKSPACE / "process_window.png"


def load_specs():
    try:
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def generate_process_window():
    if not HAS_MPL:
        print("[WINDOW] Matplotlib not available. Install: pip install matplotlib")
        return

    specs = load_specs()
    clamp_ton = specs.get("clamping_force_ton", 200.0)
    max_p_mpa = specs.get("max_pressure_mpa", 180.0)
    proj_area = specs.get("projected_area_m2", 0.011250)
    opt = specs.get("optimum_recipe", {})

    # ── Material parameters (PC) ──
    Tg = 423.15
    T_deg = 623.15
    T_min = Tg + 50
    T_max = T_deg - 30

    # ── Calculate boundary lines ──
    # Flash line: P_max = ClampingForce / Area
    p_flash = (clamp_ton * 9806.65) / (proj_area * 1e6)  # MPa

    # Short-shot line: P_min ~ viscosity * L * Q / (2*h^3)
    L_flow = 0.15
    h_cavity = 0.0012
    Q = 50e-6 / 1.0
    eta_ref = 320.0  # Pa.s at reference condition
    p_short_ref = eta_ref * L_flow * Q / (2.0 * h_cavity ** 3) * 1e-6

    # Temperature-dependent short-shot (higher T -> lower viscosity -> lower required P)
    T_vals = np.linspace(T_min - 20, T_max + 20, 100)
    P_short = []
    P_flash_line = []
    T_deg_line = []

    for T in T_vals:
        # WLF shift: eta drops as T rises
        eta_ratio = math.exp(-0.02 * (T - Tg))
        P_short.append(max(1, p_short_ref * eta_ratio))
        P_flash_line.append(p_flash)
        T_deg_line.append(1)

    # ── Plot ──
    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor('#0f172a')
    ax.set_facecolor('#1e293b')

    # Fill operating window
    ax.fill_between(T_vals, np.array(P_short), np.array(P_flash_line),
                    where=(np.array(T_vals) >= T_min) & (np.array(T_vals) <= T_max),
                    color='#10b981', alpha=0.25, label='Optimal Operating Window')

    # Flash line
    ax.axhline(y=p_flash, color='#ef4444', linestyle='--', linewidth=2,
               label=f'Flash Line: P_max = {p_flash:.0f} MPa')

    # Short-shot line
    ax.plot(T_vals, P_short, color='#f59e0b', linestyle='--', linewidth=2,
            label='Short-Shot Boundary (P_min)')

    # Degradation line
    ax.axvline(x=T_deg, color='#ef4444', linestyle='-.', linewidth=2,
               label=f'Degradation: T_max = {T_deg:.0f} K')

    # Freeze-off line
    ax.axvline(x=T_min, color='#3b82f6', linestyle='-.', linewidth=2,
               label=f'Freeze-off: T_min = {T_min:.0f} K')

    # Plot DOE runs
    if DOE_CSV.exists():
        import pandas as pd
        df = pd.read_csv(DOE_CSV)
        temps = df["MeltTemp_K"].values
        press = df["PackPressure_MPa"].values
        ax.scatter(temps, press, c='#fbbf24', s=60, edgecolors='white', linewidth=1,
                   zorder=5, label='DOE L9 Runs')
        for i, (t, p) in enumerate(zip(temps, press)):
            ax.annotate(f"R{i+1}", (t, p), textcoords="offset points", xytext=(0, 8),
                         fontsize=7, color='white', ha='center')

    # Mark optimal recipe
    if opt:
        opt_t = opt.get("MeltTemp_K", 563.15)
        opt_p = opt.get("PackingPressure_MPa", 100.0)
        ax.scatter([opt_t], [opt_p], c='#22c55e', s=150, marker='*', edgecolors='white',
                    linewidth=2, zorder=6, label=f'Optimal: {opt_t}K / {opt_p}MPa')

    ax.set_xlabel('Melt Temperature (K)', color='white', fontsize=12)
    ax.set_ylabel('Injection Pressure (MPa)', color='white', fontsize=12)
    ax.set_title('Molding Process Window - Laptop Housing (PC)', color='white', fontsize=14, fontweight='bold')
    ax.tick_params(colors='white')
    ax.grid(True, which='both', ls='--', color='#334155', alpha=0.7)
    ax.legend(loc='upper right', facecolor='#1e293b', edgecolor='#475569', fontsize=9, labelcolor='white')
    ax.set_xlim(T_min - 20, T_max + 20)
    ax.set_ylim(0, max(p_flash * 1.2, 200))

    plt.tight_layout()
    plt.savefig(str(WINDOW_PNG), dpi=150, facecolor='#0f172a')
    plt.close()

    print(f"[WINDOW] Process window chart saved: {WINDOW_PNG.name}")
    print(f"  Flash line: {p_flash:.0f} MPa")
    print(f"  Optimal window: T=[{T_min:.0f}, {T_max:.0f}] K, P=[{P_short[-1]:.1f}, {p_flash:.0f}] MPa")
    return str(WINDOW_PNG)


if __name__ == "__main__":
    generate_process_window()