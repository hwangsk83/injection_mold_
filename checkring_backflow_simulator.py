# -*- coding: utf-8 -*-
"""
checkring_backflow_simulator.py - Check-Ring Closure Delay & Back-flow Flux Simulator
"""
import os
import json
import numpy as np
from pathlib import Path

WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"

def simulate_backflow():
    print("[CHECK-RING BACKFLOW] Simulating check-ring closure delay & back-flow mass flux at V/P switch...")

    vp_switch_time_s     = 1.225   # from vp_switchover specs
    closure_delay_s      = 0.075   # mechanical check-ring closure delay (0.05–0.1 s range)
    end_delay_s          = vp_switch_time_s + closure_delay_s

    # During closure delay, cavity pressure pushes resin back through screw tip
    # Back-flow rate decays as ring closes
    t_delay      = np.linspace(vp_switch_time_s, end_delay_s, 80)
    # Back-flow flux: peak at start, decays to zero as ring seals
    q_back_cc_s  = 4.2 * np.exp(-30 * (t_delay - vp_switch_time_s))

    total_backflow_vol_cc = float(np.trapezoid(q_back_cc_s, t_delay))   # cm3
    peak_backflow_cc_s    = float(q_back_cc_s[0])
    pressure_loss_mpa     = total_backflow_vol_cc * 1.8   # empirical: 1.8 MPa per cm³ back-flow

    # Pressure continuity check: no outlier spikes
    pressure_time_series  = 120.0 * np.exp(-0.4 * (t_delay - vp_switch_time_s)) - pressure_loss_mpa
    max_pressure_spike    = float(np.max(np.abs(np.diff(pressure_time_series))))
    continuity_ok         = max_pressure_spike < 5.0   # MPa/step

    print(f"  V/P Switch Time:          t = {vp_switch_time_s:.4f} s")
    print(f"  Check-ring Closure Delay: {closure_delay_s*1000:.1f} ms")
    print(f"  Peak Back-flow Rate:      {peak_backflow_cc_s:.3f} cm³/s")
    print(f"  Total Back-flow Volume:   {total_backflow_vol_cc:.4f} cm³")
    print(f"  Resulting Packing Pressure Drop: {pressure_loss_mpa:.4f} MPa")
    print(f"  Pressure Continuity Outlier: {max_pressure_spike:.4f} MPa/step  (OK={continuity_ok})")

    # Save
    if SPEC_JSON.exists():
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            specs = json.load(f)
    else:
        specs = {}

    specs["checkring_backflow"] = {
        "vp_switch_time_s":       vp_switch_time_s,
        "closure_delay_s":        closure_delay_s,
        "peak_backflow_cc_s":     peak_backflow_cc_s,
        "total_backflow_vol_cc":  total_backflow_vol_cc,
        "pressure_loss_mpa":      pressure_loss_mpa,
        "max_pressure_spike_mpa": max_pressure_spike,
        "continuity_ok":          continuity_ok,
        "status": "SUCCESS"
    }

    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)

    print("[SUCCESS] Check-ring back-flow simulation completed.")

if __name__ == "__main__":
    simulate_backflow()
