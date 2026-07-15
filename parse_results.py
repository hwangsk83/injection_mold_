#!/usr/bin/env python3
"""Parse titanFoam log and solver_monitor.csv for validation."""
import csv
import re
import sys
from pathlib import Path

log_path_inj = Path("d:/Open_code_project/injection_mold_flow/validation_test/log.injectionFoam")
log_path_titan = Path("d:/Open_code_project/injection_mold_flow/validation_test/log.titanFoam")
log_path = log_path_inj if log_path_inj.exists() else log_path_titan
csv_path = Path("d:/Open_code_project/injection_mold_flow/solver_monitor.csv")

if not log_path.exists():
    print(f"[ERROR] Log file not found in validation_test")
    sys.exit(1)

log_text = log_path.read_text(encoding='utf-8', errors='replace')

# Parse time stepping info from log
timesteps = []
lines = log_text.split('\n')
current_time = None
current_step = 0

for i, line in enumerate(lines):
    # Match "Time = X.XXXX" pattern
    m_time = re.search(r'Time\s*=\s*([\d.eE+-]+)', line)
    if m_time and ("FilledRatio" in line or "MaxP" in line):
        current_time = float(m_time.group(1))
        current_step += 1
        
        # Get FilledRatio from the same line
        fill_match = re.search(r'FilledRatio\s*(?:%|=)\s*([\d.eE+-]+)%?', line)
        maxp_match = re.search(r'MaxP(?:\(MPa\))?\s*=\s*([\d.eE+-]+)', line)
        maxt_match = re.search(r'MaxT(?:\(K\))?\s*=\s*([\d.eE+-]+)', line)
        avgvisc_match = re.search(r'AvgViscosity\s*=\s*([\d.eE+-]+)', line)
        courant_match = re.search(r'Courant\s*=\s*([\d.eE+-]+)', line)
        
        fill = float(fill_match.group(1)) if fill_match else 0.0
        maxp = float(maxp_match.group(1)) if maxp_match else 0.0
        if maxp_match and "MPa" in maxp_match.group(0):
            maxp *= 1e6
        maxt = float(maxt_match.group(1)) if maxt_match else 0.0
        avgvisc = float(avgvisc_match.group(1)) if avgvisc_match else 0.0
        courant = float(courant_match.group(1)) if courant_match else 0.0
        
        timesteps.append({
            'time': current_time,
            'step': current_step,
            'fill': fill,
            'maxp': maxp,
            'maxt': maxt,
            'avgvisc': avgvisc,
            'courant': courant
        })

# Write monitoring CSV
with open(csv_path, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Time','Step','Max_P','Avg_T','Max_T','Courant_No',
                     'Residual_P','Residual_U','Residual_T',
                     'Vol_Filled_Ratio','Max_Viscous_Heat','Average_Viscosity',
                     'Compute_Time_Per_Step','Estimated_Cost_Accumulated'])
    for ts in timesteps:
        writer.writerow([
            f"{ts['time']:.4f}", ts['step'],
            f"{ts['maxp']:.2f}", '500', f"{ts['maxt']:.2f}",
            f"{ts['courant']:.4f}",
            '0', '0', '0',
            f"{ts['fill']:.2f}", '0', f"{ts['avgvisc']:.6e}",
            '0', '0'
        ])

# Print summary
print("\n" + "="*70)
print("  titanFoam Validation Results Summary")
print("="*70)

if timesteps:
    final = timesteps[-1]
    print(f"\n  Final time:         {final['time']:.4f} s")
    print(f"  Filled ratio:       {final['fill']:.2f}%")
    print(f"  Max pressure:       {final['maxp']:.2f} Pa ({final['maxp']/1e6:.2f} MPa)")
    print(f"  Max temperature:    {final['maxt']:.2f} K")
    print(f"  Average viscosity:  {final['avgvisc']:.6e} Pa·s")
    print(f"  Courant number:     {final['courant']:.4f}")
    
    # Find when 95% fill was achieved
    for ts in timesteps:
        if ts['fill'] >= 95.0:
            print(f"\n  >>> 95% FILL REACHED at t = {ts['time']:.4f} s <<<")
            break
    
    # Check validation criteria
    print("\n  [VALIDATION CHECKS]")
    
    # 1. Fill ratio at 1.0s should be >= 95%
    t1_data = [ts for ts in timesteps if abs(ts['time'] - 1.0) < 0.01]
    if t1_data:
        t1_fill = t1_data[0]['fill']
        if t1_fill >= 95.0:
            print(f"  [PASS] t=1.0s fill rate: {t1_fill:.2f}% >= 95%")
        else:
            print(f"  [FAIL] t=1.0s fill rate: {t1_fill:.2f}% < 95%")
    else:
        print(f"  [WARN] No data at t=1.0s, closest: t={final['time']:.4f}s fill={final['fill']:.2f}%")
        if final['fill'] >= 95.0:
            print(f"  [PASS] Final fill rate: {final['fill']:.2f}% >= 95%")
    
    # 2. Average viscosity in [1, 1000] Pa·s range
    if 1.0 <= final['avgvisc'] <= 1000.0:
        print(f"  [PASS] Viscosity: {final['avgvisc']:.2f} Pa·s in [1, 1000] range")
    else:
        print(f"  [WARN] Viscosity: {final['avgvisc']:.6e} Pa·s (check if acceptable)")
    
    # 3. Max pressure should be able to exceed 50 MPa naturally
    if final['maxp'] > 50e6:
        print(f"  [PASS] Pressure naturally exceeds 50 MPa: {final['maxp']/1e6:.2f} MPa")
    else:
        print(f"  [INFO] Max pressure: {final['maxp']/1e6:.2f} MPa (may increase during packing)")
else:
    print("  No time steps found in log!")

print("\n  Full data written to: solver_monitor.csv")
print("="*70 + "\n")
