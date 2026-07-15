#!/usr/bin/env python3
"""run_full_test.py - Project Titan v5.9 Full Orchestrator
Ensures 0/ directory persists, runs decomposePar + mpirun, reports results."""

import os, sys, subprocess, time, shutil

WORKSPACE = r"D:\Open_code_project\injection_mold_flow"
CASE_DIR = os.path.join(WORKSPACE, "validation_test")
SRC_0_DIR = os.path.join(WORKSPACE, "dummy_mold_case", "0")
DST_0_DIR = os.path.join(CASE_DIR, "0")

BLUECFD_VARS = r"d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"

def ensure_0_dir():
    """Fresh copy of 0/ from dummy_mold_case with modifications."""
    if os.path.isdir(DST_0_DIR):
        shutil.rmtree(DST_0_DIR)
    shutil.copytree(SRC_0_DIR, DST_0_DIR)
    print(f"[SETUP] Copied {len(os.listdir(DST_0_DIR))} files to 0/")

    # Modify U: 0.05 -> 0.25 m/s
    u_path = os.path.join(DST_0_DIR, "U")
    with open(u_path, 'r') as f:
        u_data = f.read()
    u_data = u_data.replace("(0.05 0 0)", "(0.25 0 0)")
    with open(u_path, 'w') as f:
        f.write(u_data)
    print("[SETUP] U inlet velocity: 0.05 -> 0.25 m/s")

    # Modify alpha: outlet -> inletOutlet
    a_path = os.path.join(DST_0_DIR, "alpha")
    with open(a_path, 'r') as f:
        a_data = f.read()
    a_data = a_data.replace(
        "outlet     { type zeroGradient; }",
        "outlet     { type inletOutlet; inletValue uniform 0; value uniform 0; }"
    )
    with open(a_path, 'w') as f:
        f.write(a_data)
    print("[SETUP] alpha outlet: zeroGradient -> inletOutlet")

    # Verify
    for fn in ['U','p','alpha','T']:
        fp = os.path.join(DST_0_DIR, fn)
        with open(fp, 'rb') as fh:
            raw = fh.read()
        print(f"  {fn}: {len(raw)} bytes OK")

def run_bluecfd_cmd(cmd_str):
    """Run command through setvars_OF12.bat environment."""
    full_cmd = f'call "{BLUECFD_VARS}" && set "PATH=d:\\Program-Files\\blueCFD-Core-2024\\ThirdParty-12\\platforms\\mingw_w64Gcc122\\MS-MPI-10.1.2\\bin;%PATH%" && {cmd_str}'
    proc = subprocess.run(
        full_cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=CASE_DIR
    )
    return proc

def main():
    os.chdir(CASE_DIR)
    print(f"[RUN] Case dir: {CASE_DIR}")

    # Step 1: Ensure 0/ directory
    ensure_0_dir()

    # Step 2: Clean old processor dirs + time dirs
    print("[RUN] Cleaning old results...")
    for d in ['processor0','processor1','processor2','processor3']:
        dp = os.path.join(CASE_DIR, d)
        if os.path.isdir(dp):
            shutil.rmtree(dp)
    # Remove time dirs but keep 0/
    for item in os.listdir(CASE_DIR):
        if item == '0':
            continue
        fp = os.path.join(CASE_DIR, item)
        if os.path.isdir(fp) and (item[0].isdigit() or '.' in item):
            shutil.rmtree(fp)

    # Step 3: decomposePar
    print("[RUN] Running decomposePar...")
    r = run_bluecfd_cmd("decomposePar -force 2>&1")
    with open(os.path.join(CASE_DIR, "log.decomposePar"), 'w') as f:
        f.write(r.stdout + r.stderr)
    if r.returncode != 0:
        print(f"[FAIL] decomposePar rc={r.returncode}")
        print(r.stdout[-500:])
        return r.returncode
    print("[RUN] decomposePar OK")

    # Verify processor dirs have 0/ fields
    for pi in range(4):
        pd = os.path.join(CASE_DIR, f"processor{pi}", "0")
        if os.path.isdir(pd):
            files = os.listdir(pd)
            print(f"  processor{pi}/0/: {files}")
        else:
            print(f"  WARNING: processor{pi}/0/ NOT FOUND!")

    # Step 4: mpirun titanFoam to t=1.0
    print("[RUN] Launching mpirun -np 4 titanFoam -parallel...")
    t0 = time.time()
    r = run_bluecfd_cmd("mpirun -np 4 titanFoam -parallel 2>&1")
    elapsed = time.time() - t0
    with open(os.path.join(CASE_DIR, "log.titanFoam"), 'w') as f:
        f.write(r.stdout + r.stderr)
    
    if r.returncode != 0:
        print(f"[FAIL] titanFoam rc={r.returncode} after {elapsed:.0f}s")
        lines = (r.stdout + r.stderr).split('\n')
        print("Last 30 lines of output:")
        for line in lines[-30:]:
            print(f"  {line}")
        return r.returncode
    
    print(f"[OK] titanFoam completed in {elapsed:.0f}s")
    
    # Step 5: Report results
    output = r.stdout + r.stderr
    for keyword in ["FilledRatio", "filledRatio", "Time =", "Courant", "ExecutionTime"]:
        for line in output.split('\n'):
            if keyword.lower() in line.lower():
                print(f"  {line.strip()}")
    
    # Check for solver_monitor.csv if generated
    csv_path = os.path.join(WORKSPACE, "solver_monitor.csv")
    if os.path.isfile(csv_path):
        with open(csv_path, 'r') as f:
            lines = f.readlines()
        print(f"\n[MONITOR] solver_monitor.csv: {len(lines)} lines")
        print("  Header:", lines[0].strip())
        if len(lines) > 2:
            print("  Last 3 rows:")
            for line in lines[-3:]:
                print(f"    {line.strip()}")
    else:
        print("[MONITOR] solver_monitor.csv not found (may not be generated)")

    print("[DONE] Project Titan v5.9 parallel test complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
