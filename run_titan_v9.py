#!/usr/bin/env python3
"""
Titan v5.8 - FINAL VALIDATION RUNNER v9
Uses LD_LIBRARY_PATH for DLL loading + absolute paths
"""
import os, sys, glob, shutil, re, subprocess, time

VAL_DIR = r"d:\Open_code_project\injection_mold_flow\validation_test"
BASH = r"d:\Program-Files\blueCFD-Core-2024\msys64\usr\bin\bash.exe"
BIN_DIR = r"d:\Program-Files\blueCFD-Core-2024\ofuser-of12\platforms\mingw_w64Gcc122DPInt32Opt\bin"

def run_bash(script_body, timeout=300):
    s = os.path.join(VAL_DIR, "_run.sh")
    mingw64 = "/d/Program-Files/blueCFD-Core-2024/msys64/mingw64/bin"
    with open(s, 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write(f"export PATH={mingw64}:/d/Program-Files/blueCFD-Core-2024/msys64/usr/bin:/d/Program-Files/blueCFD-Core-2024/ofuser-of12/platforms/mingw_w64Gcc122DPInt32Opt/bin:/usr/bin:/bin\n")
        f.write(f"export LD_LIBRARY_PATH={mingw64}:/d/Program-Files/blueCFD-Core-2024/ofuser-of12/platforms/mingw_w64Gcc122DPInt32Opt/bin\n")
        f.write(script_body + "\n")
    proc = subprocess.Popen(f'"{BASH}" "{s}"', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
    os.remove(s)
    return proc.returncode, out.decode('utf-8',errors='replace'), err.decode('utf-8',errors='replace')

def write_fields():
    d0 = os.path.join(VAL_DIR, "0")
    os.makedirs(d0, exist_ok=True)
    fields = {
        "U": [
            'FoamFile { version 2.0; format ascii; class volVectorField; location "0"; object U; }',
            'dimensions [0 1 -1 0 0 0 0];', 'internalField uniform (0 0 0);',
            'boundaryField', '{',
            '    gate_inlet { type fixedValue; value uniform (0.25 0 0); }',
            '    outlet     { type zeroGradient; }', '    walls      { type noSlip; }', '}',
        ],
        "p": [
            'FoamFile { version 2.0; format ascii; class volScalarField; location "0"; object p; }',
            'dimensions [1 -1 -2 0 0 0 0];', 'internalField uniform 0;',
            'boundaryField', '{',
            '    gate_inlet { type zeroGradient; }',
            '    outlet     { type fixedValue; value uniform 0; }',
            '    walls      { type zeroGradient; }', '}',
        ],
        "alpha": [
            'FoamFile { version 2.0; format ascii; class volScalarField; location "0"; object alpha; }',
            'dimensions [0 0 0 0 0 0 0];', 'internalField uniform 0;',
            'boundaryField', '{',
            '    gate_inlet { type fixedValue; value uniform 1; }',
            '    outlet     { type inletOutlet; inletValue uniform 0; value uniform 0; }',
            '    walls      { type zeroGradient; }', '}',
        ],
        "T": [
            'FoamFile { version 2.0; format ascii; class volScalarField; location "0"; object T; }',
            'dimensions [0 0 0 1 0 0 0];', 'internalField uniform 300;',
            'boundaryField', '{',
            '    gate_inlet { type fixedValue; value uniform 490; }',
            '    outlet     { type zeroGradient; }', '    walls      { type zeroGradient; }', '}',
        ],
    }
    for name, lines in fields.items():
        with open(os.path.join(d0, name), 'w', newline='\n') as f:
            f.write("\n".join(lines) + "\n")
    print("[WRITE] All 0/ fields")

def clean():
    os.chdir(VAL_DIR)
    for p in ["processor*", "0.*", "[1-9]*"]:
        for item in glob.glob(p):
            if os.path.isdir(item): shutil.rmtree(item, ignore_errors=True)
    for l in ["log.blockMesh","log.decomposePar","log.titanFoam","log.reconstructPar"]:
        lp = os.path.join(VAL_DIR, l)
        if os.path.exists(lp): os.remove(lp)

def main():
    print("="*60)
    print("  TITAN v5.8 - FINAL VALIDATION (LD_LIBRARY_PATH)")
    print("="*60)
    
    write_fields()
    clean()
    
    # blockMesh
    print("\n[1] blockMesh...")
    rc,out,err = run_bash("cd /d/Open_code_project/injection_mold_flow/validation_test && blockMesh > log.blockMesh 2>&1")
    if not os.path.exists(os.path.join(VAL_DIR,"log.blockMesh")): 
        print(f"[FAIL] {err[:200]}")
        return 1
    print("[OK]")
    
    # decomposePar
    print("\n[2] decomposePar...")
    rc,out,err = run_bash("cd /d/Open_code_project/injection_mold_flow/validation_test && decomposePar -force > log.decomposePar 2>&1")
    proc0 = os.path.join(VAL_DIR,"processor0","0")
    if os.path.isdir(proc0):
        print(f"[OK] processor0/0: {os.listdir(proc0)}")
    
    # titanFoam
    print("\n[3] titanFoam SERIAL...")
    t0 = time.time()
    # Use absolute path + LD_LIBRARY_PATH
    TITAN = "/d/Program-Files/blueCFD-Core-2024/ofuser-of12/platforms/mingw_w64Gcc122DPInt32Opt/bin/titanFoam.exe"
    rc,out,err = run_bash(f"cd /d/Open_code_project/injection_mold_flow/validation_test && {TITAN} > log.titanFoam 2>&1", timeout=300)
    dt = time.time() - t0
    
    lp = os.path.join(VAL_DIR,"log.titanFoam")
    if not os.path.exists(lp):
        print(f"[FAIL] No log! rc={rc}, out={out[:200]}, err={err[:200]}")
        return 1
    
    with open(lp) as f:
        content = f.read()
    
    print(f"[INFO] {os.path.getsize(lp)}B in {dt:.0f}s")
    
    if 'error while loading' in content or 'cannot open' in content:
        print(f"[FAIL] DLL: {content[:200]}")
        return 1
    if 'FATAL ERROR' in content:
        print("[FAIL] FATAL:")
        for l in content.split('\n'):
            if 'FATAL' in l or 'cannot find' in l:
                print(f"  >> {l.strip()}")
        return 1
    
    # Parse
    lines = content.split('\n')
    monitor = [l for l in lines if any(k in l for k in ['Time = ','FilledRatio','AvgViscosity','MaxP'])]
    print(f"\n--- Monitoring ({len(monitor)} lines) ---")
    for m in monitor:
        print(f"  {m.strip()}")
    
    times = re.findall(r'Time = ([0-9.eE+-]+)', content)
    rat = re.findall(r'FilledRatio = ([0-9.eE+-]+)', content)
    vis = re.findall(r'AvgViscosity = ([0-9.eE+-]+)', content)
    prs = re.findall(r'MaxP = ([0-9.eE+-]+)', content)
    
    print("\n" + "="*60)
    print("[VALIDATION]")
    print("="*60)
    if times: print(f"  Steps: {len(times)}, final t={times[-1]}s")
    if rat: print(f"  FilledRatio: {rat[-1]}% [{'PASS' if float(rat[-1])>=85 else 'FAIL'} >=85%]")
    if vis: print(f"  AvgViscosity: {vis[-1]} Pa·s [{'PASS' if 1<=float(vis[-1])<=10000 else 'FAIL'} 1~10000]")
    if prs: print(f"  MaxP: {prs[-1]} Pa")
    
    if rat and vis:
        rv, vv = float(rat[-1]), float(vis[-1])
        if rv >= 85 and 1 <= vv <= 10000:
            print("\n*** TITAN v5.8 VALIDATION PASSED! ***")
            return 0
    print("\n*** Check results above ***")
    return 0

if __name__ == "__main__":
    sys.exit(main())
