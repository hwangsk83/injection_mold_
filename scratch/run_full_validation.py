import os
import sys
import shutil
import subprocess
import time
from pathlib import Path

WORKSPACE_ROOT = Path(r"d:\Open_code_project\injection_mold_flow")
VAL_DIR = WORKSPACE_ROOT / "validation_test"
sys.path.append(str(WORKSPACE_ROOT))

from gate_patcher import generate_gate_dictionaries

# 1. Setup Gate parameters
gates = [
    {
        "Shape": "Rectangular",
        "X": 0.0,
        "Y": 25.0,
        "Z": 1.0,
        "W": 20.0,
        "H": 2.0
    }
]
u_inlet_vector = [0.5, 0.0, 0.0]

print("--- [STEP 1] Generating dictionaries ---")
success = generate_gate_dictionaries(VAL_DIR, gates, u_inlet_vector)
if not success:
    print("Failed to generate gate dictionaries.")
    sys.exit(1)
print("Successfully generated topoSetDict, createPatchDict, and 0/U.")

# Clean old run directories
print("--- [STEP 2] Cleaning old simulation directories ---")
for p in VAL_DIR.glob("processor*"):
    shutil.rmtree(p, ignore_errors=True)
for p in VAL_DIR.iterdir():
    if p.is_dir() and p.name.replace(".", "").isdigit() and p.name != "0":
        shutil.rmtree(p, ignore_errors=True)

# Run mesh generation & decomposition natively
print("--- [STEP 3] Running blockMesh, topoSet, and createPatch ---")
os.chdir(str(VAL_DIR))

SETVARS = r"d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"

def run_native_cmd(cmd, logfile):
    # Call setvars first, then inject MPI path to prevent setvars from erasing it, then change directory!
    full_cmd = f'call "{SETVARS}" && set "PATH=C:\\Program Files\\Microsoft MPI\\Bin;%PATH%" && cd /d "{VAL_DIR}" && {cmd}'
    print(f"Executing: {cmd} -> {logfile}")
    with open(logfile, "w", encoding="utf-8") as f:
        p = subprocess.run(full_cmd, shell=True, stdout=f, stderr=subprocess.STDOUT, text=True)
    
    # Check if the command was successful by parsing logfile
    if Path(logfile).exists():
        log_text = Path(logfile).read_text(encoding="utf-8", errors="ignore")
        if "FOAM FATAL ERROR" in log_text or "Floating point exception" in log_text:
            return False
        if "End" in log_text or "Reconstructed" in log_text or "Reconstructing" in log_text:
            return True
    return p.returncode == 0

if not run_native_cmd("blockMesh", "log.blockMesh"):
    print("[ERROR] blockMesh failed.")
    sys.exit(1)
print("blockMesh succeeded.")

if not run_native_cmd("topoSet", "log.topoSet"):
    print("[ERROR] topoSet failed.")
    sys.exit(1)
print("topoSet succeeded.")

if not run_native_cmd("createPatch -overwrite", "log.createPatch"):
    print("[ERROR] createPatch failed.")
    sys.exit(1)
print("createPatch succeeded.")

# decomposePar
print("--- [STEP 4] Running decomposePar ---")
if not run_native_cmd("decomposePar -force", "log.decomposePar"):
    print("[ERROR] decomposePar failed.")
    sys.exit(1)
print("decomposePar succeeded.")

# Run injectionFoam in parallel
print("--- [STEP 5] Running injectionFoam parallel (4 cores) ---")
sol_cmd = "mpiexec -np 4 injectionFoam -parallel"

t0 = time.time()
sol_success = run_native_cmd(sol_cmd, "log.injectionFoam")
dt = time.time() - t0

if sol_success:
    print(f"Simulation completed successfully in {dt:.1f} seconds.")
else:
    print("[ERROR] Simulation failed. Check log.injectionFoam.")
    sys.exit(1)

# reconstructPar
print("--- [STEP 6] Reconstructing parallel results ---")
run_native_cmd("reconstructPar -latestTime", "log.reconstructPar")
print("reconstructPar completed.")

# Parse results
print("--- [STEP 7] Parsing results ---")
os.chdir(str(WORKSPACE_ROOT))
subprocess.run(sys.executable + " parse_results.py", shell=True)
print("--- ALL STEPS COMPLETE ---")
