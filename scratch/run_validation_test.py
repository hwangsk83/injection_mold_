import os
import sys
import shutil
import subprocess
import time
import re
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
        "W": 50.0,
        "H": 2.0
    }
]
u_inlet_vector = [0.2, 0.0, 0.0]

print("--- [STEP 1] Generating dictionaries ---")
success = generate_gate_dictionaries(VAL_DIR, gates, u_inlet_vector)
if not success:
    print("Failed to generate gate dictionaries.")
    sys.exit(1)
print("Successfully generated topoSetDict, createPatchDict, and 0/U.")

# Write fresh 0/p, 0/alpha, and 0/T fields with standard dimensions for injectionFoam
d0 = VAL_DIR / "0"
d0.mkdir(parents=True, exist_ok=True)

# 0/p (Standard pressure: Pa)
p_content = """FoamFile { version 2.0; format ascii; class volScalarField; object p; }
dimensions [1 -1 -2 0 0 0 0];
internalField uniform 1e5;
boundaryField
{
    gate_inlet
    {
        type            mixed;
        refValue        uniform 1e5;
        refGradient     uniform 0;
        valueFraction   uniform 0;
        value           uniform 1e5;
    }
    outlet     { type fixedValue; value uniform 1e5; }
    walls      { type zeroGradient; }
}
"""
(d0 / "p").write_text(p_content, encoding="utf-8")

# 0/alpha (Volume fraction)
alpha_content = """FoamFile { version 2.0; format ascii; class volScalarField; object alpha; }
dimensions [0 0 0 0 0 0 0];
internalField uniform 0;
boundaryField
{
    gate_inlet { type fixedValue; value uniform 1; }
    outlet     { type zeroGradient; }
    walls      { type zeroGradient; }
}
"""
(d0 / "alpha").write_text(alpha_content, encoding="utf-8")

# 0/T (Temperature: K)
t_content = """FoamFile { version 2.0; format ascii; class volScalarField; object T; }
dimensions [0 0 0 1 0 0 0];
internalField uniform 500.0;
boundaryField
{
    gate_inlet { type fixedValue; value uniform 500.0; }
    outlet     { type zeroGradient; }
    walls      { type fixedValue; value uniform 333.0; }
}
"""
(d0 / "T").write_text(t_content, encoding="utf-8")
print("Successfully wrote fresh standard-dimensional fields 0/p, 0/alpha, and 0/T.")

# Inject ABS Material properties into constant/transportProperties
from material_db import MATERIAL_DB
selected_material = "ABS"
mat = MATERIAL_DB[selected_material]
wlf = mat["CrossWLF"]
tait = mat["Tait"]

transport_properties_content = f"""FoamFile {{ version 2.0; format ascii; class dictionary; object transportProperties; }}
rheologyModel   CrossWLF;

CrossWLFCoeffs
{{
    D1      {wlf['D1']:.6e};
    D2      {wlf['D2']:.2f};
    D3      {wlf['D3']:.2f};
    A1      {wlf['A1']:.2f};
    A2      {wlf['A2']:.2f};
}}
TaitCoeffs
{{
    b1m     {tait['b1m']:.6e};
    b2m     {tait['b2m']:.6e};
    b3m     {tait['b3m']:.6e};
    b4m     {tait['b4m']:.6e};
    b5      {tait['b5']:.2f};
    C_tait  {tait['C_tait']:.6f};
}}
vpThreshold 0.98;
"""
(VAL_DIR / "constant" / "transportProperties").write_text(transport_properties_content, encoding="utf-8")
print(f"Successfully injected real material properties for {selected_material} into constant/transportProperties.")


# Set variables and batch generator config
SETVARS = r"d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"

def run_cmd(cmd, logfile=None):
    temp_bat = VAL_DIR / "temp_run.bat"
    bat_content = f"""@echo off
call "{SETVARS}"
set "PATH=C:\\Program Files\\Microsoft MPI\\Bin;%PATH%"
cd /d "{VAL_DIR}"
{cmd}
"""
    temp_bat.write_text(bat_content, encoding="utf-8")
    
    cmd_str = f"temp_run.bat"
    if logfile:
        log_path = VAL_DIR / logfile
        if log_path.exists():
            try:
                os.remove(log_path)
            except OSError:
                pass
        cmd_str += f" > \"{logfile}\" 2>&1"
        
    proc = subprocess.run(cmd_str, shell=True, cwd=str(VAL_DIR))
    
    if temp_bat.exists():
        try:
            os.remove(temp_bat)
        except OSError:
            pass
            
    # Check logfile content for success
    if logfile:
        log_path = VAL_DIR / logfile
        if log_path.exists():
            log_text = log_path.read_text(encoding="utf-8", errors="ignore")
            if "FOAM FATAL ERROR" in log_text or "Floating point exception" in log_text:
                print(f"Log {logfile} contains FOAM FATAL ERROR or Floating point exception.")
                return False
            if "End" in log_text:
                return True
                
    return proc.returncode == 0

def patch_boundary(fpath, patch_name, new_block_content):
    if not fpath.exists():
        print(f"[WARN] Field file not found: {fpath}")
        return False
    content = fpath.read_text(encoding='utf-8', errors='ignore')
    match = re.search(rf'\b{re.escape(patch_name)}\b\s*\{{', content)
    if not match:
        print(f"[WARN] Boundary {patch_name} not found in {fpath.name}")
        return False
    
    start_idx = match.start()
    brace_idx = match.end() - 1
    brace_count = 1
    end_idx = brace_idx + 1
    
    while brace_count > 0 and end_idx < len(content):
        if content[end_idx] == '{':
            brace_count += 1
        elif content[end_idx] == '}':
            brace_count -= 1
        end_idx += 1
        
    if brace_count == 0:
        new_block = f"{patch_name}\n    {{\n{new_block_content}\n    }}"
        content = content[:start_idx] + new_block + content[end_idx:]
        fpath.write_text(content, encoding='utf-8')
        print(f"Patched {patch_name} in {fpath.parent.name}/{fpath.name}")
        return True
    return False

# Clean old run directories
print("--- [STEP 2] Cleaning old simulation directories ---")
for p in VAL_DIR.glob("processor*"):
    shutil.rmtree(p, ignore_errors=True)
for p in VAL_DIR.iterdir():
    if p.is_dir() and p.name.replace(".", "").isdigit() and p.name != "0":
        shutil.rmtree(p, ignore_errors=True)

# Set controlDict back to start from 0 and use optimized writeInterval
cd_path = VAL_DIR / "system" / "controlDict"
c_content = cd_path.read_text(encoding='utf-8')
c_content = re.sub(r'startFrom\s+[^;]+;', 'startFrom startTime;', c_content)
c_content = re.sub(r'writeInterval\s+[^;]+;', 'writeInterval 0.05;', c_content)
cd_path.write_text(c_content, encoding='utf-8')
print("Configured controlDict writeInterval to 0.05s for optimized completion.")

# Run blockMesh, topoSet, createPatch
print("--- [STEP 3] Running blockMesh, topoSet, and createPatch ---")
os.chdir(str(VAL_DIR))

if not run_cmd("blockMesh", logfile="log.blockMesh"):
    print("blockMesh failed.")
    sys.exit(1)
print("blockMesh succeeded.")

if not run_cmd("topoSet", logfile="log.topoSet"):
    print("topoSet failed.")
    sys.exit(1)
print("topoSet succeeded.")

if not run_cmd("createPatch -overwrite", logfile="log.createPatch"):
    print("createPatch failed.")
    sys.exit(1)
print("createPatch succeeded.")

# decomposePar
print("--- [STEP 4] Running decomposePar ---")
if not run_cmd("decomposePar -force", logfile="log.decomposePar"):
    print("decomposePar failed.")
    sys.exit(1)
print("decomposePar succeeded.")

# Run injectionFoam in parallel with real-time V/P switchover monitoring
print("--- [STEP 5] Running injectionFoam parallel (Filling Phase) ---")
sol_cmd = "mpiexec -np 4 injectionFoam -parallel"

# Run asynchronously using batch file to set up environment
temp_bat = VAL_DIR / "temp_run.bat"
bat_content = f"""@echo off
call "{SETVARS}"
set "PATH=C:\\Program Files\\Microsoft MPI\\Bin;%PATH%"
cd /d "{VAL_DIR}"
{sol_cmd}
"""
temp_bat.write_text(bat_content, encoding="utf-8")

log_file = open("log.injectionFoam", "w", encoding="utf-8")
p_sol = subprocess.Popen("temp_run.bat", shell=True, cwd=str(VAL_DIR), stdout=log_file, stderr=subprocess.STDOUT)

vp_triggered = False
try:
    while True:
        # Wait a bit
        time.sleep(0.5)
        
        # Read log file and check FilledRatio
        if os.path.exists("log.injectionFoam"):
            with open("log.injectionFoam", "r", encoding="utf-8", errors="ignore") as lf:
                log_text = lf.read()
            
            # Find the latest FilledRatio
            ratios = re.findall(r'FilledRatio\s*=\s*([\d\.]+)%', log_text)
            if ratios:
                latest_ratio = float(ratios[-1])
                print(f"Real-Time Vol_Filled_Ratio: {latest_ratio:.2f}%")
                
                # V/P Switchover is now fully handled natively at C++ runtime level to eliminate race conditions!
                if False:
                    print("\n==========================================")
                    print(f"  [V/P SWITCH] Vol_Filled_Ratio reached {latest_ratio:.2f}%!")
                    print("  Pausing solver to apply Packing conditions...")
                    print("==========================================\n")
                    
                    # Terminate solver process and its entire child tree recursively on Windows
                    print(f"Force-killing solver process tree (PID {p_sol.pid})...")
                    subprocess.run(f"taskkill /F /T /PID {p_sol.pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    p_sol.wait()
                    time.sleep(2.0)
                    vp_triggered = True
                    break
        
        # If solver finished on its own
        if p_sol.poll() is not None:
            print("Solver completed filling stage natively.")
            break
            
except KeyboardInterrupt:
    p_sol.terminate()
    sys.exit(1)

if temp_bat.exists():
    try: os.remove(temp_bat)
    except OSError: pass

# If V/P switchover triggered, modify fields and resume
if vp_triggered:
    # 1. Reconstruct latest time-step data
    print("Reconstructing latest time-step data for patching...")
    run_cmd("reconstructPar -latestTime", logfile="log.reconstructPar")
    
    # Identify latest time directory
    time_dirs = []
    for p in VAL_DIR.iterdir():
        if p.is_dir() and re.match(r"^\d+(\.\d+)?$", p.name) and p.name != "0":
            time_dirs.append(float(p.name))
    time_dirs.sort()
    
    if not time_dirs:
        print("[ERROR] No time directory found for patching.")
        sys.exit(1)
        
    latest_time_str = f"{time_dirs[-1]}"
    if latest_time_str.endswith(".0"):
        latest_time_str = latest_time_str[:-2]
        
    print(f"Latest reconstructed time directory: {latest_time_str}")
    latest_dir = VAL_DIR / latest_time_str
    
    # 2. Patch boundary conditions inside latest time directory
    # U boundary: set gate_inlet to zeroGradient
    u_fpath = latest_dir / "U"
    u_patch_content = "        type            zeroGradient;"
    patch_boundary(u_fpath, "gate_inlet", u_patch_content)
    
    # p boundary: set gate_inlet to fixedValue 8e7 (80 MPa)
    p_fpath = latest_dir / "p"
    p_patch_content = "        type            fixedValue;\n        value           uniform 8e7;"
    patch_boundary(p_fpath, "gate_inlet", p_patch_content)
    
    # 3. Clean processor directories for re-decomposition
    print("Cleaning processor directories for re-decomposition...")
    for p in VAL_DIR.glob("processor*"):
        shutil.rmtree(p, ignore_errors=True)
        
    # 4. Modify controlDict to start from latest time-step
    c_content = cd_path.read_text(encoding='utf-8')
    c_content = re.sub(r'startFrom\s+[^;]+;', 'startFrom latestTime;', c_content)
    cd_path.write_text(c_content, encoding='utf-8')
    print("Updated system/controlDict to start from latestTime.")
    
    # 5. Re-decompose Par
    print("Re-decomposing case for the Packing Phase...")
    if not run_cmd("decomposePar -force", logfile="log.decomposePar_packing"):
        print("[ERROR] decomposePar failed for packing.")
        sys.exit(1)
    print("Re-decomposition succeeded.")
    
    # 6. Resume solver in parallel for Packing Phase
    print("--- [STEP 6] Running injectionFoam parallel (Packing Phase) ---")
    log_file.close() # Close and re-open log to append packing log
    log_file = open("log.injectionFoam", "a", encoding="utf-8")
    
    temp_bat = VAL_DIR / "temp_run.bat"
    bat_content = f"""@echo off
call "{SETVARS}"
set "PATH=C:\\Program Files\\Microsoft MPI\\Bin;%PATH%"
cd /d "{VAL_DIR}"
{sol_cmd}
"""
    temp_bat.write_text(bat_content, encoding="utf-8")
    
    p_sol_packing = subprocess.Popen("temp_run.bat", shell=True, cwd=str(VAL_DIR), stdout=log_file, stderr=subprocess.STDOUT)
    
    print("Solver resumed for Packing Phase. Waiting for completion...")
    p_sol_packing.wait()
    
    if temp_bat.exists():
        try: os.remove(temp_bat)
        except OSError: pass
        
    log_file.close()
    print("Packing Phase completed.")

# reconstructPar
print("--- [STEP 7] Reconstructing final parallel results ---")
run_cmd("reconstructPar -latestTime", logfile="log.reconstructPar")
print("reconstructPar finished.")

# Run foamToVTK to convert the reconstructed data into VTK format for U, p, T, alpha
print("--- [STEP 7-VTK] Running foamToVTK to convert fields (U p T alpha) ---")
run_cmd("foamToVTK -ascii -fields \"(U p T alpha)\"", logfile="log.foamToVTK")
print("foamToVTK post-processing complete.")


# Parse results
print("--- [STEP 8] Parsing results ---")
os.chdir(str(WORKSPACE_ROOT))
subprocess.run(f"python parse_results.py", shell=True)
print("--- ALL STEPS COMPLETE ---")
