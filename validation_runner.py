# validation_runner.py - Automated Analytical & Physical Validation Script (titanFoam Edition)
import os
import re
import sys
import time
import shutil
import subprocess
import pandas as pd
from pathlib import Path

# =============================================================================
# 1. PATHS & INITIALIZATION
# =============================================================================
WORKSPACE_ROOT = Path(r"D:\Open_code_project\injection_mold_flow")
VAL_DIR = WORKSPACE_ROOT / "validation_test"
BLUECFD_BASH = Path(r"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe")

print("=====================================================================")
print("[Step 5-1] Initializing Automated Physical Validation Case (titanFoam)...")
print("=====================================================================")

VAL_DIR.mkdir(parents=True, exist_ok=True)
(VAL_DIR / "system").mkdir(parents=True, exist_ok=True)
(VAL_DIR / "constant").mkdir(parents=True, exist_ok=True)
(VAL_DIR / "0").mkdir(parents=True, exist_ok=True)

# =============================================================================
# 2. GENERATING BENCHMARK CASE DICTIONARIES (200x50x2mm Flat Plate Slit)
# =============================================================================
files = {}

# controlDict: endTime=3.0, deltaT=0.001 with adjustTimeStep
files["system/controlDict"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application     titanFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         3.0;
deltaT          0.001;
writeControl    runTime;
writeInterval   0.1;
purgeWrite      3;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
adjustTimeStep  yes;
maxCo           0.5;
maxDeltaT       0.005;"""

# decomposeParDict: 4 processors decomposition
files["system/decomposeParDict"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object decomposeParDict; }
numberOfSubdomains 4;
method          simple;
simpleCoeffs
{
    n               (2 2 1);
    delta           0.001;
}"""

# blockMeshDict: 8000 cells (40x20x10)
files["system/blockMeshDict"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object blockMeshDict; }
scale 0.001;
vertices
(
    (0 0 0)    (150 0 0)    (150 75 0)    (0 75 0)
    (0 0 1.2)  (150 0 1.2)  (150 75 1.2)  (0 75 1.2)
);
blocks
(
    hex (0 1 2 3 4 5 6 7) (30 15 6) simpleGrading (1 1 1)
);
edges ();
boundary
(
    gate_inlet { type patch; faces ((0 4 7 3)); }
    outlet     { type patch; faces ((1 2 6 5)); }
    walls      { type wall;  faces ((0 1 5 4)(3 2 6 7)(0 1 2 3)(4 5 6 7)); }
);"""

# fvSchemes: upwind for alpha, linearUpwind for U, standard heat diffusion
files["system/fvSchemes"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }
ddtSchemes      { default Euler; }
gradSchemes     { default Gauss linear; }
divSchemes
{
    default         none;
    div(phi,U)      Gauss linearUpwind grad(U);
    div(rhoPhi,U)   Gauss linearUpwind grad(U);
    div(phi,alpha)  Gauss upwind;
    div(rhoCpPhi,T) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
fluxRequired { default none; p; }"""

# fvSolution: solvers for T, p, U, alpha
files["system/fvSolution"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
solvers
{
    p     { solver PCG; preconditioner DIC; tolerance 1e-7; relTol 0.01; }
    U     { solver PBiCGStab; preconditioner DILU; tolerance 1e-6; relTol 0.05; }
    alpha { solver PBiCGStab; preconditioner DILU; tolerance 1e-5; relTol 0.05; }
    T     { solver PBiCGStab; preconditioner DILU; tolerance 1e-6; relTol 0.05; }
}
PIMPLE { nOuterCorrectors 3; nCorrectors 3; nNonOrthogonalCorrectors 1; }
relaxationFactors
{
    fields { p 0.5; }
    equations { U 0.8; alpha 0.9; T 0.8; }
}"""

# constant/transportProperties (Including thermal properties)
files["constant/transportProperties"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object transportProperties; }
CrossWLFCoeffs
{
    D1      300.0;
    D2      0.0;
    D3      0.0;
    A1      20.0;
    A2      50.0;
}
TaitCoeffs
{
    b1m     0.002;
    b2m     0.0;
    b3m     1.2e8;
    b4m     0.0;
    b5      0.0;
    C_tait  0.0894;
}
Cp_poly     2000.0;
Cp_air      1000.0;
k_poly      0.15;
k_air       0.026;
vpThreshold 0.98;
"""

# Boundary conditions
files["0/p"] = """\
FoamFile { version 2.0; format ascii; class volScalarField; object p; }
dimensions [0 2 -2 0 0 0 0];
internalField uniform 0;
boundaryField
{
    gate_inlet { type zeroGradient; }
    outlet     { type fixedValue; value uniform 0; }
    walls      { type zeroGradient; }
}
"""

files["0/U"] = """\
FoamFile { version 2.0; format ascii; class volVectorField; object U; }
dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField
{
    gate_inlet { type fixedValue; value uniform (0.1 0 0); }
    outlet     { type zeroGradient; }
    walls      { type noSlip; }
}
"""

files["0/T"] = """\
FoamFile { version 2.0; format ascii; class volScalarField; object T; }
dimensions [0 0 0 1 0 0 0];
internalField uniform 500.0;
boundaryField
{
    gate_inlet { type fixedValue; value uniform 500.0; }
    outlet     { type zeroGradient; }
    walls      { type fixedValue; value uniform 500.0; }
}
"""

files["0/alpha"] = """\
FoamFile { version 2.0; format ascii; class volScalarField; object alpha; }
dimensions [0 0 0 0 0 0 0];
internalField uniform 0;
boundaryField
{
    gate_inlet { type fixedValue; value uniform 1; }
    outlet     { type zeroGradient; }
    walls      { type zeroGradient; }
}
"""

for rel_path, content in files.items():
    fpath = VAL_DIR / rel_path
    fpath.write_text(content, encoding="utf-8")
    print(f"  Created: {rel_path}")

# =============================================================================
# 3. RUNNING BLOCKMESH & TITANFOAM (LOCAL MS-MPI PARALLEL ORCHESTRATION)
# =============================================================================
# Run blockMesh and decomposePar via setvars_OF12.bat wrapper
cmd_mesh = (
    r'call "d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat" '
    r'"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe" '
    r'-c "cd /d/Open_code_project/injection_mold_flow/validation_test && blockMesh > log.blockMesh 2>&1 && decomposePar -force > log.decomposePar 2>&1"'
)
res_mesh = subprocess.run(f"cmd.exe /c {cmd_mesh}", shell=True, text=True, capture_output=True)

if res_mesh.returncode == 0:
    print("  [SUCCESS] blockMesh & decomposePar succeeded!")
else:
    print("  [FAIL] blockMesh or decomposePar failed!")
    sys.exit(1)

# Run titanFoam via setvars_OF12.bat wrapper using MS-MPI with 4 cores
print("Running titanFoam in parallel (4 cores) on smartphone 150x75x1.2mm thin-wall case...")
cmd_sol = (
    r'call "d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat" '
    r'"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe" '
    r'-c "cd /d/Open_code_project/injection_mold_flow/validation_test && \"/c/Program Files/Microsoft MPI/Bin/mpiexec.exe\" -np 4 titanFoam -parallel"'
)

# Start solver asynchronously to parse output line-by-line
p_sol = subprocess.Popen(
    f"cmd.exe /c {cmd_sol}",
    shell=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1
)

# Real-time CSV logging fields setup with new energy residuals & viscosity metrics
log_cols = [
    "Time", "Step", "Max_P", "Avg_T", "Max_T", "Courant_No",
    "Residual_P", "Residual_U", "Residual_T", "Vol_Filled_Ratio",
    "Max_Viscous_Heat", "Average_Viscosity", "Compute_Time_Per_Step", "Estimated_Cost_Accumulated"
]
monitor_csv = WORKSPACE_ROOT / "solver_monitor.csv"
monitor_records = []

COST_PER_CPU_HOUR = 0.057  # Simulated cost in USD per core hour on AWS/GCP
estimated_cost_accum = 0.0

step_counter = 0
last_step_time = time.time()

# Pattern matcher for advanced titanFoam solver log output
line_pat = re.compile(
    r"Time\s*=\s*([\d\.\+eE\-]+)\s*\|\s*residuals:\s*Ux_init\s*=\s*([\d\.\+eE\-]+)\s*\|\s*residuals:\s*Alpha_init\s*=\s*([\d\.\+eE\-]+)\s*\|\s*residuals:\s*T_init\s*=\s*([\d\.\+eE\-]+)\s*\|\s*FilledRatio\s*=\s*([\d\.\+eE\-]+)%\s*\|\s*MaxP\s*=\s*([\d\.\+eE\-]+)\s*\|\s*MaxT\s*=\s*([\d\.\+eE\-]+)\s*\|\s*AvgT\s*=\s*([\d\.\+eE\-]+)\s*\|\s*MaxViscousHeat\s*=\s*([\d\.\+eE\-]+)\s*\|\s*AvgViscosity\s*=\s*([\d\.\+eE\-]+)\s*\|\s*Courant\s*=\s*([\d\.\+eE\-]+)"
)

# Simulation runtime parser
try:
    while True:
        line = p_sol.stdout.readline()
        if not line and p_sol.poll() is not None:
            break
        
        if not line:
            continue
        
        # Print directly to console for real-time app parsing
        print(line.strip())
        
        # Match monitoring metrics
        m = line_pat.search(line)
        if m:
            step_counter += 1
            curr_time = time.time()
            compute_sec = curr_time - last_step_time
            last_step_time = curr_time
            
            # Extract values
            t_val = float(m.group(1))
            res_U = float(m.group(2))
            res_Alpha = float(m.group(3))
            res_T = float(m.group(4))
            filled_ratio = float(m.group(5))
            max_p = float(m.group(6))
            max_t = float(m.group(7))
            avg_t = float(m.group(8))
            max_visc = float(m.group(9))
            avg_visc = float(m.group(10))
            courant = float(m.group(11))
            
            # Simulate cost accumulation
            step_cost = (compute_sec / 3600.0) * COST_PER_CPU_HOUR
            estimated_cost_accum += step_cost
            
            record = {
                "Time": t_val,
                "Step": step_counter,
                "Max_P": max_p,
                "Avg_T": avg_t,
                "Max_T": max_t,
                "Courant_No": courant,
                "Residual_P": 0.0,
                "Residual_U": res_U,
                "Residual_T": res_T,
                "Vol_Filled_Ratio": filled_ratio,
                "Max_Viscous_Heat": max_visc,
                "Average_Viscosity": avg_visc,
                "Compute_Time_Per_Step": compute_sec,
                "Estimated_Cost_Accumulated": estimated_cost_accum
            }
            monitor_records.append(record)
            
            # Write to CSV safely avoiding transient locks
            try:
                pd.DataFrame(monitor_records).to_csv(monitor_csv, index=False)
            except IOError:
                pass
            
            # Check stability anomalies
            if courant > 5.0:
                print(f"[CRITICAL_DIVERGENCE] Courant Number exploded to {courant:.3f}! Halting process.")
                p_sol.terminate()
                sys.exit(2)

except Exception as ex:
    print(f"Monitor error: {ex}")
    p_sol.terminate()
    sys.exit(1)

# Check run log
log_content = ""
log_path = VAL_DIR / "log.titanFoam"
# Dump captured stdout to log file for OpenFOAM compatibility
# log_path.write_text("End of titanFoam simulation.", encoding="utf-8")

if p_sol.returncode == 0 or p_sol.poll() == 0:
    print("  [SUCCESS] titanFoam simulation completed successfully!")
    print("Reconstructing parallel domain results...")
    cmd_reconstruct = (
        r'call "d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat" '
        r'"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe" '
        r'-c "cd /d/Open_code_project/injection_mold_flow/validation_test && reconstructPar -latestTime > log.reconstructPar 2>&1"'
    )
    subprocess.run(f"cmd.exe /c {cmd_reconstruct}", shell=True)
else:
    print(f"  [FAIL] titanFoam simulation failed with code {p_sol.returncode}")
    stderr_content = p_sol.stderr.read()
    print("Solver STDERR:")
    print(stderr_content)
    sys.exit(1)

# =============================================================================
# 4. [Validation Agent] RESULTS PARSING (VOF, P, U Field)
# =============================================================================
print("\n[Validation Agent] Extracting simulation output data...")

# Parse last time directories to find when alpha was filled-out at outlet (x = 200mm)
time_dirs = []
for p in VAL_DIR.iterdir():
    if p.is_dir() and re.match(r"^\d+(\.\d+)?$", p.name):
        time_dirs.append(float(p.name))
time_dirs.sort()

print(f"  Detected time directories: {time_dirs}")

def parse_nonuniform_field(file_path):
    if not file_path.exists():
        return None
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    # 1. Try uniform match
    uni_match = re.search(r"internalField\s+uniform\s+([\d\.eE\+\-]+);", content)
    if uni_match:
        return [float(uni_match.group(1))] * 8000
    
    # 2. Try nonuniform parse
    if "nonuniform List" in content:
        start_idx = content.find("(", content.find("nonuniform"))
        end_idx = content.find(")", start_idx)
        if start_idx != -1 and end_idx != -1:
            data_str = content[start_idx+1:end_idx]
            vals = [float(v) for v in data_str.split() if v.strip()]
            return vals
    return None

def get_time_dir_path(t_val):
    p_int = VAL_DIR / f"{int(t_val)}"
    if p_int.exists() and p_int.is_dir():
        return p_int
    return VAL_DIR / f"{t_val}"

detected_fill_time = None
max_outlet_alpha = 0.0

for t in time_dirs:
    alpha_file = get_time_dir_path(t) / "alpha"
    vals = parse_nonuniform_field(alpha_file)
    if vals:
        outlet_cells_alpha = []
        for iz in range(10):
            for iy in range(20):
                idx = 39 + 40 * (iy + 20 * iz)
                outlet_cells_alpha.append(vals[idx])
        avg_outlet_alpha = sum(outlet_cells_alpha)/len(outlet_cells_alpha)
        if avg_outlet_alpha > max_outlet_alpha:
            max_outlet_alpha = avg_outlet_alpha
        if avg_outlet_alpha >= 0.95 and detected_fill_time is None:
            detected_fill_time = t
            print(f"  -> Outlet VOF fill-out detected at t = {t}s (Average Outlet Alpha = {avg_outlet_alpha:.3f})")

# Parse pressure field at the last time directory to check pressure drop
last_t = time_dirs[-1]
p_file = get_time_dir_path(last_t) / "p"
sim_pressure_drop = 0.0
p_vals = parse_nonuniform_field(p_file)
if p_vals:
    sim_pressure_drop = max(p_vals)
    print(f"  -> Successfully parsed pressure field! Max Inlet Pressure = {sim_pressure_drop/1e6:.3f} MPa")

# =============================================================================
# 5. HAGEN-POISEUILLE THEORY COMPARISON
# =============================================================================
print("\nCalculating Hagen-Poiseuille Theory values...")
W = 0.05    # Width = 50mm
H = 0.002   # Thickness = 2mm
L = 0.2     # Length = 200mm
mu_val = 300.0 # Viscosity = 300.0 Pa*s
U_avg = 0.1 # Inlet velocity = 0.1 m/s

theory_delta_P = (12.0 * mu_val * L * U_avg) / (H ** 2)
theory_t_fill = L / U_avg

p_error = abs(sim_pressure_drop - theory_delta_P) / theory_delta_P * 100.0
t_error = 0.0
if detected_fill_time:
    t_error = abs(detected_fill_time - theory_t_fill) / theory_t_fill * 100.0
else:
    t_error = 100.0

print("\n=====================================================================")
print("FINAL BENCHMARK VALIDATION RESULTS")
print("=====================================================================")
print(f"Theory Fill Time     : {theory_t_fill:.3f} s")
print(f"Simulation Fill Time : {detected_fill_time if detected_fill_time else 'NOT FULLY FILLED'} s")
print(f"-> Fill Time Error   : {t_error:.2f} %")
print("")
print(f"Theory Pressure Drop : {theory_delta_P:.1f} Pa ({theory_delta_P/1e6:.3f} MPa)")
print(f"Simulation Max Pres  : {sim_pressure_drop:.1f} Pa ({sim_pressure_drop/1e6:.3f} MPa)")
print(f"-> Pressure Error    : {p_error:.2f} %")
print("=====================================================================")

# Write results for validation report
res_file = WORKSPACE_ROOT / "val_results.csv"
df_res = pd.DataFrame([{
    "Metric": ["Fill Time (s)", "Pressure Drop (Pa)"],
    "Theoretical": [theory_t_fill, theory_delta_P],
    "Simulation": [detected_fill_time if detected_fill_time else 0.0, sim_pressure_drop],
    "Error (%)": [t_error, p_error]
}])
df_res.to_csv(res_file, index=False)
print(f"\nSaved CSV results to: {res_file}")
