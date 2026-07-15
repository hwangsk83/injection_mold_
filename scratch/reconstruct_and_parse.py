import os
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(r"d:\Open_code_project\injection_mold_flow")
VAL_DIR = WORKSPACE_ROOT / "validation_test"
SETVARS = r"d:\Program-Files\blueCFD-Core-2024\setvars_OF12.bat"

# Reconstruct
full_cmd = f'call "{SETVARS}" && cd /d "{VAL_DIR}" && reconstructPar -latestTime'
subprocess.run(f'cmd.exe /c "{full_cmd}"', shell=True)

# Parse
os.chdir(str(WORKSPACE_ROOT))
subprocess.run(f"python parse_results.py", shell=True)
print("--- Done reconstruct and parse! ---")
