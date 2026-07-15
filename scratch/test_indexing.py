import re
from pathlib import Path

VAL_DIR = Path(r"D:\Open_code_project\injection_mold_flow\validation_test")

time_dirs = []
for p in VAL_DIR.iterdir():
    if p.is_dir() and re.match(r"^\d+(\.\d+)?$", p.name):
        time_dirs.append(float(p.name))
time_dirs.sort()

def get_time_dir_path(t_val):
    p_int = VAL_DIR / f"{int(t_val)}"
    if p_int.exists() and p_int.is_dir():
        return p_int
    return VAL_DIR / f"{t_val}"

def parse_nonuniform_field(file_path):
    if not file_path.exists():
        return None
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    uni_match = re.search(r"internalField\s+uniform\s+([\d\.eE\+\-]+);", content)
    if uni_match:
        return [float(uni_match.group(1))] * 8000
    
    if "nonuniform List" in content:
        start_idx = content.find("(", content.find("nonuniform"))
        end_idx = content.find(")", start_idx)
        if start_idx != -1 and end_idx != -1:
            data_str = content[start_idx+1:end_idx]
            vals = [float(v) for v in data_str.split() if v.strip()]
            return vals
    return None

# Find cell mapping for blockMesh:
# vertices:
# 0:(0 0 0) 1:(200 0 0) 2:(200 50 0) 3:(0 50 0)
# 4:(0 0 2) 5:(200 0 2) 6:(200 50 2) 7:(0 50 2)
# hex (0 1 2 3 4 5 6 7) (40 20 10)
# OpenFOAM hex cell indexing standard:
# i_x is the first direction: 0..1 (X: 0 to 200)
# i_y is the second direction: 1..2 (Y: 0 to 50)
# i_z is the third direction: 0..4 (Z: 0 to 2)
# Index formula: cell_index = i_x + N_x * (i_y + N_y * i_z)
# where N_x = 40, N_y = 20, N_z = 10
# So outlet cells should be cells where i_x = 39.
# Let's verify by printing some of the actual values of cells at i_x = 39 for all time steps.

for t in time_dirs:
    alpha_file = get_time_dir_path(t) / "alpha"
    vals = parse_nonuniform_field(alpha_file)
    if vals:
        outlet_cells_alpha = []
        for iz in range(10):
            for iy in range(20):
                # i_x = 39
                idx = 39 + 40 * (iy + 20 * iz)
                outlet_cells_alpha.append(vals[idx])
        avg_outlet_alpha = sum(outlet_cells_alpha)/len(outlet_cells_alpha)
        
        # Let's also check i_x = 38
        ix38_cells = []
        for iz in range(10):
            for iy in range(20):
                idx = 38 + 40 * (iy + 20 * iz)
                ix38_cells.append(vals[idx])
        avg_38 = sum(ix38_cells)/len(ix38_cells)
        
        print(f"t={t:.1f}: outlet (ix=39) avg={avg_outlet_alpha:.4f}, max={max(outlet_cells_alpha):.4f} | ix=38 avg={avg_38:.4f}")
