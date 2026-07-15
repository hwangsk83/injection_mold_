# -*- coding: utf-8 -*-
"""
triz_process_optimizer.py
TRIZ Physical Contradiction Resolver via Multi-objective Bayesian Optimization (GPR)
Contradiction: Higher packing pressure -> lower sink mark BUT higher residual stress + longer cycle.

Upgraded Phase 4:
  - Local Minima Detection (EI plateau tracker)
  - Hypervolume Indicator (Pareto front quality)
  - Convergence Quality Metrics (for Check 38 audit)
  - Epoch-by-epoch acquisition function tracing

Objective space:
  f1 = max sink mark depth (um) -> MINIMIZE, target < 5 um
  f2 = max residual stress (MPa) -> MINIMIZE, target < 30 MPa
Design space: [P1, P2, P3] (MPa), [t1, t2, t3] (s)  -- 3-stage packing pressures & durations
"""
import os, json, math
import numpy as np
from pathlib import Path

WORKSPACE = Path(os.getcwd())
SPEC_JSON = WORKSPACE / "machine_spec.json"

# ── Surrogate physics models ───────────────────────────────────────────────────
def sink_mark_model(P1, P2, P3, t1, t2, t3):
    """Sink mark depth (um): decreases with higher packing, diminishing returns."""
    P_eff = (P1 * t1 + P2 * t2 + P3 * t3) / (t1 + t2 + t3 + 1e-9)
    return max(0.1, 12.0 * math.exp(-P_eff / 50.0) + 0.5)

def residual_stress_model(P1, P2, P3, t1, t2, t3):
    """Residual stress (MPa): increases with packing intensity."""
    P_peak = P1
    t_total = t1 + t2 + t3
    stress = 5.0 + 0.18 * P_peak + 0.08 * P_peak * math.log(1 + t_total)
    return stress

# ── GPR Kernel ─────────────────────────────────────────────────────────────────
def rbf_kernel(X1, X2, length_scale=1.0, sigma_f=1.0):
    X1 = np.atleast_2d(X1)
    X2 = np.atleast_2d(X2)
    dists = np.sum((X1[:, None, :] - X2[None, :, :]) ** 2, axis=-1)
    return sigma_f ** 2 * np.exp(-0.5 * dists / length_scale ** 2)

class GPR:
    def __init__(self, noise=1e-4):
        self.noise = noise
        self.X_train = None
        self.y_train = None

    def fit(self, X, y):
        self.X_train = np.array(X)
        self.y_train = np.array(y)

    def predict(self, X_test):
        K   = rbf_kernel(self.X_train, self.X_train) + self.noise * np.eye(len(self.X_train))
        K_s = rbf_kernel(self.X_train, X_test)
        K_ss= rbf_kernel(X_test, X_test)
        try:
            L   = np.linalg.cholesky(K)
            alpha= np.linalg.solve(L.T, np.linalg.solve(L, self.y_train))
            mu  = K_s.T @ alpha
            v   = np.linalg.solve(L, K_s)
            var = np.diag(K_ss) - np.sum(v**2, axis=0)
        except np.linalg.LinAlgError:
            mu  = np.zeros(len(X_test))
            var = np.ones(len(X_test))
        return mu, np.clip(var, 1e-9, None)

def expected_improvement(mu, sigma, f_best, xi=0.01):
    imp   = f_best - mu - xi
    Z     = imp / (sigma + 1e-9)
    from math import erfc
    phi   = np.exp(-0.5 * Z**2) / np.sqrt(2 * np.pi)
    Phi   = 0.5 * np.array([math.erfc(-z / math.sqrt(2)) / 2 for z in Z.flat]).reshape(Z.shape)
    ei    = imp * Phi + sigma * phi
    ei[sigma < 1e-8] = 0.0
    return ei


def _hypervolume(f1_vals, f2_vals, ref_point=(10.0, 50.0)):
    """
    Compute 2-D hypervolume indicator (area dominated by Pareto front).
    ref_point = (ref_sink_um, ref_stress_MPa) must dominate all points.
    """
    # Sort by f1 ascending
    pareto = np.column_stack([f1_vals, f2_vals])
    pareto = pareto[np.argsort(pareto[:, 0])]
    hv = 0.0
    prev_f1 = ref_point[0]
    for f1, f2 in pareto:
        if f2 < ref_point[1]:
            hv += (ref_point[1] - max(f2, ref_point[1]*0.01)) * \
                  (prev_f1 - max(f1, ref_point[0]*0.01))
        prev_f1 = f1
    return hv


def _convert_numpy(obj):
    """Recursively convert numpy types to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_numpy(v) for v in obj]
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, tuple):
        return list(_convert_numpy(v) for v in obj)
    return obj


def run_triz_optimizer():
    print("[TRIZ OPTIMIZER] Running Multi-objective Bayesian Optimization (GPR) for packing contradiction...")
    print("=" * 65)
    np.random.seed(2025)

    # ── Design space bounds ──────────────────────────────────────────────────
    # X = [P1(MPa), P2(MPa), P3(MPa), t1(s), t2(s), t3(s)]
    lb = np.array([ 60.0,  40.0,  20.0,  1.0,  1.5,  1.0])
    ub = np.array([140.0, 100.0,  60.0,  3.5,  4.0,  3.5])

    # ── Latin Hypercube initial sampling (15 pts) ────────────────────────────
    n_init = 15
    lhs = np.zeros((n_init, 6))
    for j in range(6):
        perm = np.random.permutation(n_init)
        lhs[:, j] = (perm + np.random.uniform(0,1, n_init)) / n_init
    X_obs = lb + lhs * (ub - lb)

    y1_obs = np.array([sink_mark_model(*row) for row in X_obs])
    y2_obs = np.array([residual_stress_model(*row) for row in X_obs])

    # ── Bayesian loop: 30 epochs ─────────────────────────────────────────────
    n_epochs     = 30
    n_candidates = 300
    convergence_history = []
    ei_history           = []
    hypervolume_history  = []
    local_minima_plateau_epochs = 0
    ei_plateau_window    = []

    gpr1 = GPR(noise=0.05)
    gpr2 = GPR(noise=0.05)

    print(f"── Bayesian Optimization Loop ({n_epochs} epochs) ──")

    for epoch in range(n_epochs):
        # Normalize design space for GPR
        X_norm = (X_obs - lb) / (ub - lb)

        gpr1.fit(X_norm, y1_obs)
        gpr2.fit(X_norm, y2_obs)

        # Random candidate sampling
        X_cand_raw = lb + np.random.uniform(0, 1, (n_candidates, 6)) * (ub - lb)
        X_cand     = (X_cand_raw - lb) / (ub - lb)

        mu1, var1 = gpr1.predict(X_cand)
        mu2, var2 = gpr2.predict(X_cand)
        sig1 = np.sqrt(var1)
        sig2 = np.sqrt(var2)

        # Acquisition: EI on weighted scalarized objective (Chebyshev)
        f_best1 = float(np.min(y1_obs))
        f_best2 = float(np.min(y2_obs))
        ei1 = expected_improvement(mu1, sig1, f_best1, xi=0.02)
        ei2 = expected_improvement(mu2, sig2, f_best2, xi=0.5)
        # Combined acquisition
        acq = 0.55 * ei1 + 0.45 * ei2
        best_idx = int(np.argmax(acq))
        max_ei = float(np.max(acq))
        ei_history.append(max_ei)

        # ── Local Minima (EI Plateau) Detection ────────────────────────────
        ei_plateau_window.append(max_ei)
        if len(ei_plateau_window) > 5:
            ei_plateau_window.pop(0)
        if len(ei_plateau_window) == 5:
            # Check if EI is stagnating (relative change < 1%)
            ei_range = max(ei_plateau_window) - min(ei_plateau_window)
            if max(ei_plateau_window) > 0 and ei_range / max(ei_plateau_window) < 0.01:
                local_minima_plateau_epochs += 1

        x_new = X_cand_raw[best_idx]
        y1_new = sink_mark_model(*x_new)
        y2_new = residual_stress_model(*x_new)

        X_obs  = np.vstack([X_obs, x_new])
        y1_obs = np.append(y1_obs, y1_new)
        y2_obs = np.append(y2_obs, y2_new)

        # Track Pareto front
        convergence_history.append((float(np.min(y1_obs)), float(np.min(y2_obs))))

        # Hypervolume
        # Build current Pareto set
        dominated = np.zeros(len(X_obs), dtype=bool)
        for i in range(len(X_obs)):
            for j in range(len(X_obs)):
                if i == j: continue
                if y1_obs[j] <= y1_obs[i] and y2_obs[j] <= y2_obs[i] and \
                   (y1_obs[j] < y1_obs[i] or y2_obs[j] < y2_obs[i]):
                    dominated[i] = True
                    break
        current_pareto_idx = np.where(~dominated)[0]
        hv = _hypervolume(y1_obs[current_pareto_idx], y2_obs[current_pareto_idx])
        hypervolume_history.append(hv)

        if (epoch + 1) % 10 == 0 or epoch == 0:
            print(f"  Epoch {epoch+1:3d}: Best sink={float(np.min(y1_obs)):.4f} um, "
                  f"Best stress={float(np.min(y2_obs)):.4f} MPa, "
                  f"HV={hv:.2f}, maxEI={max_ei:.4f}"
                  f"{' [PLATEAU]' if local_minima_plateau_epochs > 3 else ''}")

    # ── Final convergence assessment ──────────────────────────────────────────
    # Late-stage hypervolume convergence: check last 10 epochs
    if len(hypervolume_history) >= 10:
        hv_start = np.mean(hypervolume_history[-10:-5])
        hv_end   = np.mean(hypervolume_history[-5:])
        hv_convergence_rate = abs(hv_end - hv_start) / max(hv_start, 1.0)
        hv_global_converged = hv_convergence_rate < 0.01
    else:
        hv_convergence_rate = 1.0
        hv_global_converged = False

    # Local minima flag: EI plateau for > 5 epochs
    local_minima_detected = local_minima_plateau_epochs > 5

    print()
    print(f"── Convergence Audit Metrics ──")
    print(f"  EI Plateau Epochs          : {local_minima_plateau_epochs}")
    print(f"  Local Minima Detected      : {local_minima_detected}")
    print(f"  HV Convergence Rate (late) : {hv_convergence_rate*100:.2f}%")
    print(f"  HV Global Converged        : {hv_global_converged}")
    print()

    # ── Pareto-front extraction ──────────────────────────────────────────────
    dominated = np.zeros(len(X_obs), dtype=bool)
    for i in range(len(X_obs)):
        for j in range(len(X_obs)):
            if i == j: continue
            if y1_obs[j] <= y1_obs[i] and y2_obs[j] <= y2_obs[i] and \
               (y1_obs[j] < y1_obs[i] or y2_obs[j] < y2_obs[i]):
                dominated[i] = True
                break
    pareto_idx = np.where(~dominated)[0]

    # ── Select single best recipe: closest to ideal point ─────────────────────
    f1_pareto = y1_obs[pareto_idx]
    f2_pareto = y2_obs[pareto_idx]
    f1_min, f1_max = f1_pareto.min(), f1_pareto.max()
    f2_min, f2_max = f2_pareto.min(), f2_pareto.max()
    f1_n = (f1_pareto - f1_min) / (f1_max - f1_min + 1e-9)
    f2_n = (f2_pareto - f2_min) / (f2_max - f2_min + 1e-9)
    dist_to_utopia = np.sqrt(f1_n**2 + f2_n**2)
    best_pareto_local = int(np.argmin(dist_to_utopia))
    best_global_idx   = pareto_idx[best_pareto_local]
    best_recipe       = X_obs[best_global_idx]
    best_sm           = float(y1_obs[best_global_idx])
    best_rs           = float(y2_obs[best_global_idx])

    # Constraint satisfaction checks
    sm_ok = best_sm < 5.0
    rs_ok = best_rs < 30.0
    converged = len(pareto_idx) >= 3  # meaningful Pareto frontier

    # Final hypervolume
    final_hv = _hypervolume(y1_obs[pareto_idx], y2_obs[pareto_idx])

    print(f"── [PARETO RESULT] Optimal 3-Stage Packing Recipe ──")
    print(f"  Stage 1: P = {best_recipe[0]:.1f} MPa,  t = {best_recipe[3]:.2f} s")
    print(f"  Stage 2: P = {best_recipe[1]:.1f} MPa,  t = {best_recipe[4]:.2f} s")
    print(f"  Stage 3: P = {best_recipe[2]:.1f} MPa,  t = {best_recipe[5]:.2f} s")
    print(f"  Predicted Sink Mark: {best_sm:.4f} um  (target < 5 um, OK={sm_ok})")
    print(f"  Predicted Residual Stress: {best_rs:.4f} MPa  (target < 30 MPa, OK={rs_ok})")
    print(f"  Pareto Front Size: {len(pareto_idx)} solutions")
    print(f"  Hypervolume Indicator: {final_hv:.4f}")
    print(f"  HV Global Converged: {hv_global_converged}")
    print(f"  Local Minima Detected: {local_minima_detected}")
    print()

    # ── Save to machine_spec.json ─────────────────────────────────────────────
    if SPEC_JSON.exists():
        with open(SPEC_JSON, "r", encoding="utf-8") as f:
            specs = json.load(f)
    else:
        specs = {}

    specs["triz_optimizer"] = {
        "n_epochs":               n_epochs,
        "n_pareto_solutions":     int(len(pareto_idx)),
        "converged":              converged,
        "hypervolume_final":      final_hv,
        "hv_global_converged":    hv_global_converged,
        "local_minima_detected":  local_minima_detected,
        "ei_plateau_epochs":      local_minima_plateau_epochs,
        "hv_convergence_rate_pct": round(hv_convergence_rate * 100, 3),
        "best_recipe": {
            "P1_mpa": float(best_recipe[0]), "t1_s": float(best_recipe[3]),
            "P2_mpa": float(best_recipe[1]), "t2_s": float(best_recipe[4]),
            "P3_mpa": float(best_recipe[2]), "t3_s": float(best_recipe[5]),
        },
        "best_sink_mark_um":           best_sm,
        "best_residual_stress_mpa":    best_rs,
        "constraints_met":             {"sink_mark_lt5um": sm_ok, "stress_lt30mpa": rs_ok},
        "convergence_history":         convergence_history,
        "hypervolume_history":         hypervolume_history,
        "ei_history":                  ei_history,
        "pareto_f1":                   f1_pareto.tolist(),
        "pareto_f2":                   f2_pareto.tolist(),
        "status":                      "SUCCESS",
        "version":                     "Phase4"
    }
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(_convert_numpy(specs), f, indent=4)

    print("=" * 65)
    print("[SUCCESS] TRIZ multi-objective Bayesian optimization completed (Phase 4).")
    print(f"  Constraints Met : Sink {sm_ok} / Stress {rs_ok}")
    print(f"  Hypervolume     : {final_hv:.4f}")
    print(f"  Local Minima    : {'DETECTED' if local_minima_detected else 'NONE'}")
    print(f"  Global Converged: {hv_global_converged}")
    print("=" * 65)

if __name__ == "__main__":
    run_triz_optimizer()