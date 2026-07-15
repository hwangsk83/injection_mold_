#!/usr/bin/env python3
"""
titan_v59_runner.py - Project Titan v5.9 FINAL
Setvars passes args as commands. mpirun needs full path.
"""

import os, sys, subprocess, shutil

CASE = r"D:\Open_code_project\injection_mold_flow\validation_test"
WORKSPACE = r"D:\Open_code_project\injection_mold_flow"
BLUECFD = r"d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"
MPIRUN = r"d:\Program-Files\blueCFD-Core-2024\ThirdParty-12\platforms\mingw_w64Gcc122\MS-MPI-10.1.2\bin\mpirun.exe"

def bluecfd_cmd(cmd):
    """setvars passes its arguments as a command."""
    full = f'call "{BLUECFD}" {cmd}'
    proc = subprocess.run(full, shell=True, capture_output=True, text=True, cwd=CASE)
    return proc

def create_zero_dir():
    d = os.path.join(CASE, "0")
    if os.path.isdir(d): shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)
    files = {
        "U": "FoamFile { version 2.0; format ascii; class volVectorField; object U; }\ndimensions [0 1 -1 0 0 0 0];\ninternalField uniform (0 0 0);\nboundaryField\n{\n    gate_inlet { type fixedValue; value uniform (0.25 0 0); }\n    outlet     { type zeroGradient; }\n    walls      { type noSlip; }\n}\n",
        "p": "FoamFile { version 2.0; format ascii; class volScalarField; object p; }\ndimensions [0 2 -2 0 0 0 0];\ninternalField uniform 1e5;\nboundaryField\n{\n    gate_inlet { type zeroGradient; }\n    outlet     { type fixedValue; value uniform 1e5; }\n    walls      { type zeroGradient; }\n}\n",
        "alpha": "FoamFile { version 2.0; format ascii; class volScalarField; object alpha; }\ndimensions [0 0 0 0 0 0 0];\ninternalField uniform 0;\nboundaryField\n{\n    gate_inlet { type fixedValue; value uniform 1; }\n    outlet     { type inletOutlet; inletValue uniform 0; value uniform 0; }\n    walls      { type zeroGradient; }\n}\n",
        "T": "FoamFile { version 2.0; format ascii; class volScalarField; object T; }\ndimensions [0 0 0 1 0 0 0];\ninternalField uniform 503.15;\nboundaryField\n{\n    gate_inlet { type fixedValue; value uniform 503.15; }\n    outlet     { type zeroGradient; }\n    walls      { type fixedValue; value uniform 323.15; }\n}\n",
    }
    for fname, content in files.items():
        with open(os.path.join(d, fname), 'wb') as f:
            f.write(content.encode('ascii'))

def main():
    print("=" * 60)
    print("  Project Titan v5.9 - FINAL PARALLEL TEST")
    print("=" * 60)

    # Create 0/ dir
    print("\n[STEP 0] 0/ directory...")
    create_zero_dir()
    print("  [OK] 4 field files created")

    # Clean
    print("\n[STEP 1] Clean old data...")
    for d in ['processor0','processor1','processor2','processor3']:
        dp = os.path.join(CASE, d)
        if os.path.isdir(dp): shutil.rmtree(dp)
    print("  [OK] Cleaned")

    # decomposePar
    print("\n[STEP 2] decomposePar...")
    r = bluecfd_cmd(f'decomposePar -case "{CASE}" -force 2>&1')
    with open(os.path.join(CASE, "log.decomposePar"), 'w') as f:
        f.write(r.stdout + r.stderr)
    if r.returncode != 0:
        print(f"[FAIL] rc={r.returncode}")
        print(r.stdout[-500:])
        return r.returncode
    for pi in range(4):
        pd = os.path.join(CASE, f"processor{pi}", "0")
        if os.path.isdir(pd):
            print(f"  processor{pi}/0: {os.listdir(pd)}")
        else:
            print(f"[FATAL] No processor{pi}/0!")
            return 1
    print("  [OK] decomposePar success")

    # mpirun - using FULL PATH to mpirun.exe
    print("\n[STEP 3] mpirun -np 4 titanFoam (t=1.0s)...")
    r = bluecfd_cmd(f'"{MPIRUN}" -np 4 titanFoam -parallel -case "{CASE}" 2>&1')
    with open(os.path.join(CASE, "log.titanFoam"), 'w') as f:
        f.write(r.stdout + r.stderr)

    output = r.stdout + r.stderr
    print(f"  Exit code: {r.returncode}")

    # Extract key results
    for keyword in ["Time =", "FilledRatio", "filled", "Viscosity", "Average_Visc", "ExecutionTime", "Courant", "Vol_Filled_Ratio", "Average_Temp"]:
        for line in output.split('\n'):
            if keyword.lower() in line.lower():
                print(f"  {line.strip()}")

    if r.returncode == 0:
        print("\n" + "=" * 60)
        print("  [SUCCESS] Project Titan v5.9 PARALLEL TEST COMPLETE!")
        print("=" * 60)
    else:
        print(f"\n[FAIL] Last 30 lines:")
        for line in output.split('\n')[-30:]:
            print(f"  {line}")

    return r.returncode

if __name__ == "__main__":
    sys.exit(main())
