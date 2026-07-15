# -*- coding: utf-8 -*-
"""
crystallization_kinetics_solver.py
Avrami-Nakamura Semi-Crystalline Polymer Crystallisation Kinetics Engine
Physics:
  - Avrami-Nakamura model for isothermal & non-isothermal crystallisation
  - Latent heat release DeltaH_c coupled to CHT energy equation
  - Crystallisation shrinkage for PVT correction
Application: POM, PA66, PBT semi-crystalline resins
"""
import os, json, math, sys
import numpy as np
from pathlib import Path

WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"

# Fix unicode print on Windows
if sys.stdout.encoding == 'cp949':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Semi-crystalline resin defaults (POM - tuned for realistic alpha_c)
N_AVRAMI        = 2.5
K0_AVRAMI       = 3.0e4    # Tuned from 2.0e8: lower K0 allows crystallisation at mold temp
EA_ACTIVATION   = 35000.0   # Reduced from 45000: faster kinetics at lower T
R_GAS           = 8.314
T_NUCLEATION    = 523.15
T_INFINITY      = 573.15
DELTA_H_CRYST   = 250.0e3
RHO_POLYMER     = 1430.0
CP_POLYMER      = 2050.0
V_AMORPHOUS     = 0.85e-3
V_CRYSTALLINE   = 0.72e-3
N_TIME      = 500
TIME_MAX_S  = 15.0

def nakamura_rate(alpha_c: float, T_k: float) -> float:
    if T_k <= 273.15 or alpha_c >= 0.999:
        return 0.0
    K_T = K0_AVRAMI * math.exp(-EA_ACTIVATION / (R_GAS * T_k))
    if K_T <= 0:
        return 0.0
    n = N_AVRAMI
    rate = n * K_T**(1.0 / n) * (1.0 - alpha_c) * \
           (-math.log(max(1.0 - alpha_c, 1e-15)))**((n - 1.0) / n)
    return max(rate, 0.0)

def solve_crystallisation(T_profile_k: np.ndarray, dt_s: float):
    n_steps = len(T_profile_k)
    alpha_c = np.zeros(n_steps, dtype=float)
    Q_cryst = np.zeros(n_steps, dtype=float)
    delta_v = np.zeros(n_steps, dtype=float)
    delay_sum = 0.0

    for i in range(1, n_steps):
        T_k = T_profile_k[i]
        ac_prev = alpha_c[i - 1]
        if T_k >= T_INFINITY:
            alpha_c[i] = 0.0
            continue
        if ac_prev >= 0.999:
            alpha_c[i] = 1.0
            continue
        n_sub = 20
        dt_sub = dt_s / n_sub
        ac_sub = ac_prev
        for _ in range(n_sub):
            rate = nakamura_rate(ac_sub, T_k)
            ac_sub += rate * dt_sub
            if ac_sub >= 0.999:
                ac_sub = 1.0
                break
        alpha_c[i] = min(ac_sub, 1.0)
        dalpha_dt = (alpha_c[i] - alpha_c[i - 1]) / max(dt_s, 1e-12)
        Q_cryst[i] = RHO_POLYMER * DELTA_H_CRYST * dalpha_dt
        vol_mix = V_AMORPHOUS * (1.0 - alpha_c[i]) + V_CRYSTALLINE * alpha_c[i]
        delta_v[i] = V_AMORPHOUS - vol_mix
        sensible = RHO_POLYMER * CP_POLYMER * abs(T_profile_k[i] - T_profile_k[i-1]) / max(dt_s, 1e-12)
        if sensible > 0 and Q_cryst[i] > 0.1 * sensible:
            delay_sum += dt_s

    t_half_s = None
    for i in range(1, n_steps):
        if alpha_c[i] >= 0.5 and alpha_c[i-1] < 0.5:
            t_half_s = i * dt_s
            break
    return alpha_c, Q_cryst, delta_v, delay_sum, t_half_s

def run_crystallisation_solver():
    print("[CRYSTALLISATION KINETICS] Avrami-Nakamura Semi-Crystalline Solver")
    print("=" * 65)
    T_melt_k = 563.15
    T_mold_k = 353.15
    tau_cool = 1.5
    t_arr = np.linspace(0, TIME_MAX_S, N_TIME)
    dt_s = t_arr[1] - t_arr[0]
    T_profile = T_mold_k + (T_melt_k - T_mold_k) * np.exp(-t_arr / tau_cool)

    print(f"  T_melt = {T_melt_k:.1f} K, T_mold = {T_mold_k:.1f} K")
    print(f"  tau_cool = {tau_cool:.2f} s, steps = {N_TIME}")
    print(f"  Avrami: n={N_AVRAMI}, K0={K0_AVRAMI:.1e}, Ea={EA_ACTIVATION:.0f} J/mol")
    print(f"  Delta H_c = {DELTA_H_CRYST/1e3:.0f} kJ/kg")

    alpha_c, Q_cryst, delta_v, delay_sum, t_half = solve_crystallisation(T_profile, dt_s)
    alpha_final = float(alpha_c[-1])
    Q_max = float(np.max(Q_cryst)) / 1e6
    delta_v_final = float(delta_v[-1])
    total_shrink_mm3 = delta_v_final * 1e6
    tc50_actual = t_half if t_half else TIME_MAX_S

    T_target = T_mold_k + 0.5 * (T_melt_k - T_mold_k)
    if T_target > T_mold_k:
        t_sensible = -tau_cool * math.log((T_target - T_mold_k) / (T_melt_k - T_mold_k + 1e-9))
    else:
        t_sensible = TIME_MAX_S
    cooling_delay_s = tc50_actual - max(t_sensible, 0)
    T_elevation_k = DELTA_H_CRYST * alpha_final / CP_POLYMER

    print(f"\n-- Results --")
    print(f"  Final crystallinity : {alpha_final*100:.2f}%")
    print(f"  Peak latent heat    : {Q_max:.2f} MW/m3")
    print(f"  Cryst half-time     : {tc50_actual:.2f} s")
    print(f"  Sensible half-time  : {max(t_sensible,0):.2f} s")
    print(f"  Cooling delay       : {cooling_delay_s:.2f} s")
    print(f"  Total delay (10%+)  : {delay_sum:.2f} s")
    print(f"  Shrinkage           : {delta_v_final:.4e} m3/kg")
    print(f"  Equivalent T rise   : +{T_elevation_k:.2f} K")

    if SPEC_JSON.exists():
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            specs = json.load(f)
    else:
        specs = {}

    specs["crystallisation_kinetics"] = {
        "model": "Avrami-Nakamura",
        "resin_type": "Semi-crystalline (POM-default)",
        "n_avrami": N_AVRAMI,
        "K0": K0_AVRAMI,
        "Ea_activation": EA_ACTIVATION,
        "Delta_H_cryst_kJ_kg": DELTA_H_CRYST / 1e3,
        "final_crystallinity_pct": round(alpha_final * 100, 2),
        "peak_latent_heat_MW_m3": round(Q_max, 3),
        "crystallisation_half_time_s": round(tc50_actual, 3),
        "cooling_delay_latent_s": round(cooling_delay_s, 3),
        "total_delay_s": round(delay_sum, 3),
        "cryst_shrinkage_m3_kg": float(delta_v_final),
        "shrink_mm3_per_g": round(total_shrink_mm3, 4),
        "temp_elevation_K": round(T_elevation_k, 2),
        "status": "SUCCESS",
        "version": "Phase5"
    }
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)

    print("\n" + "=" * 65)
    print("[SUCCESS] Crystallisation Kinetics Solver completed (Phase 5).")
    print(f"  Crystallinity     : {alpha_final*100:.1f}%")
    print(f"  Cooling Delay     : {cooling_delay_s:.2f} s")
    print(f"  Shrinkage         : {delta_v_final:.4e} m3/kg")
    print(f"  Temp Elev.        : +{T_elevation_k:.1f} K")
    print("=" * 65)

if __name__ == "__main__":
    run_crystallisation_solver()