#!/usr/bin/env python3
"""
Titan v5.8 - FINAL VALIDATION RUNNER
mu_air=1.0 fix. Creates fields, runs solver, parses results.
"""
import os, sys, glob, shutil, re, subprocess, time

VAL_DIR = r"d:\Open_code_project\injection_mold_flow\validation_test"
BASH = r"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe"
BUILD_SCRIPT = r"d:\Open_code_project\injection_mold_flow\build_titanFoam.sh"

def run_cfd(script_content, timeout=120):
    """Write a temp bash script and run it via blueCFD bash"""
    script_path = os.path.join(VAL_DIR, "_r.sh")
    with open(script_path, 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write("export PATH=/d/Program-Files/blueCFD-Core-2024/msys64/mingw64/bin:/d/Program-Files/blueCFD-Core-2024/msys64/usr/bin:/d/Program-Files/blueCFD-Core-2024/OpenFOAM-12/wmake:/d/Program-Files/blueCFD-Core-2024/OpenFOAM-12/bin:/d/Program-Files/blueCFD-Core-2024/ofuser-of12/platforms/mingw_w64Gcc122DPInt32Opt/bin:/usr/bin:/bin\n")
        f.write(script_content + "\n")
    
    proc = subprocess.Popen(
        f'"{BASH}" "{script_path}"',
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=True
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate()
    
    os.remove(script_path)
    return proc.returncode, stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace')

def write_fields():
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
            '}',
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
            '}',
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
            '}',
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
            '}',
        ],
    }
    
    for name, lines in fields.items():
        fpath = os.path.join(d0, name)
        with open(fpath, 'w', newline='\n') as f:
            f.write("\n".join(lines) + "\n")
        print(f"[WRITE] 0/{name} ({os.path.getsize(fpath)} bytes)")
    return True

def clean():
    os.chdir(VAL_DIR)
    for pattern in ["processor*", "0.*", "[1-9]*"]:
        for item in glob.glob(pattern):
            if os.path.isdir(item):
                shutil.rmtree(item, ignore_errors=True)
    for log in ["log.blockMesh", "log.decomposePar", "log.titanFoam", "log.reconstructPar"]:
        lpath = os.path.join(VAL_DIR, log)
        if os.path.exists(lpath): os.remove(lpath)

def main():
    print("="*60)
    print("  TITAN v5.8 - FINAL VALIDATION (mu_air=1.0 fix)")
    print("="*60)
    
    # Step 0
    print("\n[STEP 0] Fields")
    write_fields()
    clean()
    
    # Step 1: blockMesh
    print("\n[STEP 1] blockMesh...")
    rc, out, err = run_cfd("cd /d/Open_code_project/injection_mold_flow/validation_test && blockMesh > log.blockMesh 2>&1")
    log_path = os.path.join(VAL_DIR, "log.blockMesh")
    if os.path.exists(log_path):
        print(f"  [OK] ({os.path.getsize(log_path)} bytes)")
    else:
        print(f"[FAIL] rc={rc}, err={err[:200]}")
        return 1
    
    # Step 2: decomposePar
    print("\n[STEP 2] decomposePar...")
    rc, out, err = run_cfd("cd /d/Open_code_project/injection_mold_flow/validation_test && decomposePar -force > log.decomposePar 2>&1")
    if os.path.exists(os.path.join(VAL_DIR, "log.decomposePar")):
        print(f"  [OK]")
        proc0 = os.path.join(VAL_DIR, "processor0", "0")
        if os.path.isdir(proc0):
            print(f"  [INFO] processor0/0: {os.listdir(proc0)}")
    else:
        print(f"[FAIL] rc={rc}")
        return 1
    
    # Step 3: titanFoam (SERIAL)
    print("\n[STEP 3] titanFoam SERIAL (mu_air=1.0) ...")
    start = time.time()
    rc, out, err = run_cfd("cd /d/Open_code_project/injection_mold_flow/validation_test && titanFoam.exe > log.titanFoam 2>&1", timeout=180)
    elapsed = time.time() - start
    
    log_path = os.path.join(VAL_DIR, "log.titanFoam")
    if os.path.exists(log_path):
        with open(log_path) as f:
            content = f.read()
        print(f"  [INFO] Log: {os.path.getsize(log_path)} bytes, {elapsed:.0f}s")
        
        lines = content.split('\n')
        
        # Check for FATAL ERROR
        if 'FATAL ERROR' in content:
            print("[FAIL] FATAL ERROR in simulation:")
            for l in lines:
                if 'FATAL' in l or 'cannot find' in l:
                    print(f"  >> {l.strip()}")
            return 1
        
        # Extract monitoring
        time_lines = [l for l in lines if 'Time = ' in l]
        print(f"  Time steps: {len(time_lines)}")
        
        if time_lines:
            print(f"\n  First: {time_lines[0].strip()}")
            if len(time_lines) > 1:
                print(f"  Last:  {time_lines[-1].strip()}")
        
        # Show all monitoring lines
        print("\n--- Monitoring ---")
        for l in lines:
            if any(kw in l for kw in ['FilledRatio', 'AvgViscosity', 'MaxP']):
                print(f"  {l.strip()}")
        
        # Final validation
        print("\n" + "="*60)
        print("[VALIDATION]")
        print("="*60)
        
        times = re.findall(r'Time = ([0-9.eE+-]+)', content)
        rat = re.findall(r'FilledRatio = ([0-9.eE+-]+)', content)
        vis = re.findall(r'AvgViscosity = ([0-9.eE+-]+)', content)
        
        if times:
            print(f"  Final time: {times[-1]} s")
        if rat:
            rv = float(rat[-1])
            print(f"  FilledRatio: {rat[-1]}% [{'PASS' if rv>=85 else 'FAIL'} >= 85%]")
        if vis:
            vv = float(vis[-1])
            print(f"  AvgViscosity: {vis[-1]} Pa·s [{'PASS' if 1<=vv<=10000 else 'FAIL'} range 1~10000]")
        
        if rat and vis:
            rv, vv = float(rat[-1]), float(vis[-1])
            if rv >= 85 and 1 <= vv <= 10000:
                print("\n*** TITAN v5.8 VALIDATION PASSED! ***")
                return 0
            else:
                print("\n*** TITAN v5.8 VALIDATION FAILED - needs tuning ***")
                return 1
    else:
        print(f"[FAIL] No log.titanFoam! rc={rc}, err={err[:300]}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
