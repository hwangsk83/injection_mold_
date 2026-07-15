#!/usr/bin/env python3
"""
Titan v5.8 - ULTIMATE VALIDATION RUNNER
Uses subprocess to properly call blueCFD setvars + bash
"""
import os, sys, glob, shutil, re, subprocess

VAL_DIR = r"d:\Open_code_project\injection_mold_flow\validation_test"
SETVARS = r"d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"
BASH = r"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe"

def run_cmd(cmd):
    """Run command in CMD, return (returncode, stdout, stderr)"""
    proc = subprocess.Popen(
        f'cmd /c "{cmd}"',
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=True
    )
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout.decode('utf-8', errors='replace'), stderr.decode('utf-8', errors='replace')

def run_cfd(cmd):
    """Run command through blueCFD's bash"""
    # Write cmd to a temp script
    script_path = os.path.join(VAL_DIR, "_run.sh")
    with open(script_path, 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write(f"cd /d/Open_code_project/injection_mold_flow/validation_test\n")
        f.write(cmd + "\n")
    
    # Execute via batch
    rc, out, err = run_cmd(f'"{SETVARS}" "{BASH}" "{script_path}"')
    os.remove(script_path)
    return rc, out, err

def write_fields():
    """Write 0/ field files"""
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
        print(f"[WRITE] 0/{name}")
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
    print("[CLEAN] Done")

def main():
    print("="*60)
    print("  TITAN v5.8 - ULTIMATE VALIDATION RUNNER")
    print("="*60)
    
    # Step 0: Write fields
    print("\n[STEP 0] Fields")
    write_fields()
    clean()
    
    # Step 1: blockMesh
    print("\n[STEP 1] blockMesh...")
    rc, out, err = run_cfd("blockMesh > log.blockMesh 2>&1")
    log_path = os.path.join(VAL_DIR, "log.blockMesh")
    if os.path.exists(log_path):
        print(f"  [OK] log.blockMesh created ({os.path.getsize(log_path)} bytes)")
    else:
        print(f"  [FAIL] Return code={rc}, stderr={err[:200]}")
        print(f"  stdout={out[:200]}")
        return 1
    
    # Step 2: decomposePar
    print("\n[STEP 2] decomposePar...")
    rc, out, err = run_cfd("decomposePar -force > log.decomposePar 2>&1")
    log_path = os.path.join(VAL_DIR, "log.decomposePar")
    if os.path.exists(log_path):
        print(f"  [OK] log.decomposePar created ({os.path.getsize(log_path)} bytes)")
    else:
        print(f"  [FAIL] rc={rc}, err={err[:200]}")
        return 1
    
    proc0_0 = os.path.join(VAL_DIR, "processor0", "0")
    if os.path.isdir(proc0_0):
        print(f"  [INFO] processor0/0: {os.listdir(proc0_0)}")
    
    # Step 3: titanFoam (SERIAL first)
    print("\n[STEP 3] titanFoam SERIAL...")
    rc, out, err = run_cfd("titanFoam.exe > log.titanFoam 2>&1")
    
    log_path = os.path.join(VAL_DIR, "log.titanFoam")
    if os.path.exists(log_path):
        with open(log_path) as f:
            content = f.read()
        print(f"  [INFO] log.titanFoam: {os.path.getsize(log_path)} bytes")
        
        # Show first meaningful lines
        lines = content.split('\n')
        time_lines = [l for l in lines if 'Time = ' in l]
        print(f"  Time steps found: {len(time_lines)}")
        
        if time_lines:
            print(f"  First time: {time_lines[0].strip()}")
            print(f"  Last time: {time_lines[-1].strip()}")
        
        # Show monitoring keywords
        for line in lines:
            if any(kw in line for kw in ['FilledRatio', 'AvgViscosity', 'MaxP', 'MaxT', 'Courant']):
                print(f"  >> {line.strip()}")
        
        if 'FATAL ERROR' in content:
            error_lines = [l.strip() for l in lines if 'FATAL ERROR' in l or 'cannot find' in l]
            for el in error_lines[:5]:
                print(f"  ERROR: {el}")
            return 1
        
        # FINAL VALIDATION
        print("\n" + "="*60)
        print("[VALIDATION]")
        print("="*60)
        
        times = re.findall(r'Time = ([0-9.eE+-]+)', content)
        ratios = re.findall(r'FilledRatio = ([0-9.eE+-]+)%', content)
        viscs = re.findall(r'AvgViscosity = ([0-9.eE+-]+)', content)
        
        if times:
            print(f"  Final time: {times[-1]} s")
        if ratios:
            rv = float(ratios[-1])
            print(f"  FilledRatio: {ratios[-1]}% [{'PASS' if rv>=85 else 'FAIL'} >= 85%]")
        if viscs:
            vv = float(viscs[-1])
            print(f"  AvgViscosity: {viscs[-1]} Pa·s [{'PASS' if 1<=vv<=10000 else 'FAIL'} range 1~10000]")
        
        if ratios and viscs:
            rv = float(ratios[-1])
            vv = float(viscs[-1])
            if rv >= 85 and 1 <= vv <= 10000:
                print("\n*** TITAN v5.8 VALIDATION PASSED! ***")
                return 0
            else:
                print("\n*** VALIDATION FAILED ***")
                return 1
    else:
        print(f"[FAIL] No log.titanFoam! rc={rc}, err={err[:500]}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
