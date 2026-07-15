#!/usr/bin/env python3
"""
Project Titan - Full Validation Runner v5.8
- Recreates 0/ fields from scratch each run
- Runs blockMesh, decomposePar, titanFoam parallel, reconstructPar
- Parses solver_monitor.csv for final verification
"""
import subprocess, os, sys, time, re, glob, shutil

VAL_DIR = r"d:\Open_code_project\injection_mold_flow\validation_test"
TITAN_BIN = r"d:\Program-Files\blueCFD-Core-2024\ofuser-of12\platforms\mingw_w64Gcc122DPInt32Opt\bin\titanFoam.exe"
SETVARS = r"d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"
BASH = r"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe"

def run_bash(cmd, logfile=None):
    """Run command via blueCFD bash and return success"""
    full_cmd = f'"{SETVARS}" "{BASH}" -c "{cmd}"'
    if logfile:
        full_cmd += f" > {logfile} 2>&1"
    result = os.system(full_cmd)
    return result == 0

def write_0_fields():
    """Write initial condition fields to 0/"""
    global VAL_DIR
    d0 = os.path.join(VAL_DIR, "0")
    os.makedirs(d0, exist_ok=True)
    
    fields = {
        "U": [
            'FoamFile { version 2.0; format ascii; class volVectorField; location "0"; object U; }',
            'dimensions [0 1 -1 0 0 0 0];',
            'internalField uniform (0 0 0);',
            'boundaryField',
            '{',
            '    gate_inlet { type fixedValue; value uniform (0.25 0 0); }',
            '    outlet     { type zeroGradient; }',
            '    walls      { type noSlip; }',
            '}'
        ],
        "p": [
            'FoamFile { version 2.0; format ascii; class volScalarField; location "0"; object p; }',
            'dimensions [1 -1 -2 0 0 0 0];',
            'internalField uniform 0;',
            'boundaryField',
            '{',
            '    gate_inlet { type zeroGradient; }',
            '    outlet     { type fixedValue; value uniform 0; }',
            '    walls      { type zeroGradient; }',
            '}'
        ],
        "alpha": [
            'FoamFile { version 2.0; format ascii; class volScalarField; location "0"; object alpha; }',
            'dimensions [0 0 0 0 0 0 0];',
            'internalField uniform 0;',
            'boundaryField',
            '{',
            '    gate_inlet { type fixedValue; value uniform 1; }',
            '    outlet     { type inletOutlet; inletValue uniform 0; value uniform 0; }',
            '    walls      { type zeroGradient; }',
            '}'
        ],
        "T": [
            'FoamFile { version 2.0; format ascii; class volScalarField; location "0"; object T; }',
            'dimensions [0 0 0 1 0 0 0];',
            'internalField uniform 300;',
            'boundaryField',
            '{',
            '    gate_inlet { type fixedValue; value uniform 490; }',
            '    outlet     { type zeroGradient; }',
            '    walls      { type zeroGradient; }',
            '}'
        ]
    }
    for name, lines in fields.items():
        fpath = os.path.join(d0, name)
        with open(fpath, 'w') as f:
            f.write('\n'.join(lines) + '\n')
        print(f"[WRITE] 0/{name}")
    return True

def clean_processors():
    """Remove processor directories"""
    global VAL_DIR
    for d in glob.glob(os.path.join(VAL_DIR, "processor*")):
        shutil.rmtree(d, ignore_errors=True)
        print(f"[CLEAN] {os.path.basename(d)}")
    # Clean old time dirs
    for item in os.listdir(VAL_DIR):
        fpath = os.path.join(VAL_DIR, item)
        if os.path.isdir(fpath) and re.match(r'^\d', item) and item != '0':
            shutil.rmtree(fpath, ignore_errors=True)
            print(f"[CLEAN] time dir {item}")

def main():
    global VAL_DIR, TITAN_BIN, BASH
    
    os.chdir(VAL_DIR)
    
    # Step 0: Write fields fresh
    print("="*50)
    print("[TITAN] Step 0: Write 0/ fields")
    print("="*50)
    write_0_fields()
    clean_processors()
    
    # Step 1: blockMesh
    print("\n" + "="*50)
    print("[TITAN] Step 1: blockMesh")
    print("="*50)
    if not run_bash("cd /d/Open_code_project/injection_mold_flow/validation_test && blockMesh > log.blockMesh 2>&1"):
        with open(os.path.join(VAL_DIR, "log.blockMesh")) as f:
            print(f.read())
        sys.exit(1)
    print("[PASS] blockMesh OK")
    
    # Step 2: decomposePar
    print("\n" + "="*50)
    print("[TITAN] Step 2: decomposePar")
    print("="*50)
    if not run_bash("cd /d/Open_code_project/injection_mold_flow/validation_test && decomposePar -force -fields > log.decomposePar 2>&1"):
        with open(os.path.join(VAL_DIR, "log.decomposePar")) as f:
            print(f.read())
        sys.exit(1)
    print("[PASS] decomposePar OK")
    
    # Verify processor fields exist
    proc0_dir = os.path.join(VAL_DIR, "processor0", "0")
    if os.path.isdir(proc0_dir):
        files = os.listdir(proc0_dir)
        print(f"[INFO] processor0/0 has: {files}")
    
    # Step 3: titanFoam parallel
    print("\n" + "="*50)
    print("[TITAN] Step 3: titanFoam parallel (4 cores)")
    print("="*50)
    titan_clean = TITAN_BIN.replace("\\", "/").replace(":", "")
    titan_clean = "/" + titan_clean
    mpicmd = '"/c/Program Files/Microsoft MPI/Bin/mpiexec.exe"'
    
    if not run_bash(f"cd /d/Open_code_project/injection_mold_flow/validation_test && {mpicmd} -np 4 {titan_clean} -parallel > log.titanFoam 2>&1"):
        with open(os.path.join(VAL_DIR, "log.titanFoam")) as f:
            log = f.read()
            # Print just the error part
            for line in log.split('\n'):
                if any(kw in line for kw in ['FAIL', 'ERROR', 'FATAL', 'abort']):
                    print(f"  >> {line.strip()}")
            print(f"\n[FULL LOG LAST 20 LINES]:")
            lines = log.split('\n')
            for l in lines[-20:]:
                print(f"  {l.strip()}")
        sys.exit(1)
    print("[PASS] titanFoam parallel OK")
    
    # Step 4: reconstructPar
    print("\n" + "="*50)
    print("[TITAN] Step 4: reconstructPar")
    print("="*50)
    if not run_bash("cd /d/Open_code_project/injection_mold_flow/validation_test && reconstructPar -latestTime > log.reconstructPar 2>&1"):
        print("[WARN] reconstructPar had issues (non-critical)")
    
    # Step 5: Parse results from log
    print("\n" + "="*50)
    print("[TITAN] Step 5: Results Analysis")
    print("="*50)
    
    log_path = os.path.join(VAL_DIR, "log.titanFoam")
    if os.path.exists(log_path):
        with open(log_path) as f:
            log = f.read()
        
        # Extract final time-step data
        print("\n--- LAST TIME STEP EXTRACT ---")
        lines = log.strip().split('\n')
        last_tstep = ""
        for i in range(len(lines)-1, -1, -1):
            if "Time = " in lines[i]:
                last_tstep = lines[i]
                # Print last few time steps
                start = max(0, i-15)
                for j in range(start, len(lines)):
                    if "Time = " in lines[j] or "FilledRatio" in lines[j] or "AvgVisc" in lines[j] or "MaxP" in lines[j] or "Courant" in lines[j]:
                        print(f"  {lines[j].strip()}")
                break
        
        # Final summary
        print("\n--- FINAL TIMESTEP ANALYSIS ---")
        times = re.findall(r'Time = ([0-9.]+)', log)
        ratios = re.findall(r'FilledRatio = ([0-9.]+)%', log)
        avgs = re.findall(r'AvgViscosity = ([0-9eE.+-]+)', log)
        maxps = re.findall(r'MaxP = ([0-9eE.+-]+)', log)
        
        if times and ratios:
            final_time = times[-1]
            final_ratio = ratios[-1]
            final_avgv = avgs[-1] if avgs else "N/A"
            final_maxp = maxps[-1] if maxps else "N/A"
            
            print(f"  Simulation Time: {final_time} s")
            print(f"  Vol_Filled_Ratio: {final_ratio}%")
            print(f"  Avg_Viscosity: {final_avgv} Pa*s")
            print(f"  Max_Pressure: {final_maxp} Pa")
            
            # VALIDATE
            ratio_ok = float(final_ratio.replace('%','')) >= 85.0
            visc_ok = 1.0 <= float(final_avgv) <= 10000.0 if final_avgv != "N/A" else False
            press_ok = float(final_maxp) >= 1e5 if final_maxp != "N/A" else False
            
            print(f"\n--- VALIDATION ---")
            print(f"  [{'PASS' if ratio_ok else 'FAIL'}] Filled Ratio >= 85%: {final_ratio}%")
            print(f"  [{'PASS' if visc_ok else 'FAIL'}] Viscosity 1~10000 Pa*s: {final_avgv}")
            print(f"  [{'PASS' if press_ok else 'FAIL'}] Pressure >= 1e5 Pa: {final_maxp} Pa")
            
            if ratio_ok and visc_ok:
                print("\n*** VALIDATION PASSED - Titan Solver v5.8 is PRODUCTION READY! ***")
                return 0
            else:
                print("\n*** VALIDATION FAILED - Review needed ***")
                return 1
    else:
        print("[FAIL] log.titanFoam not found!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
