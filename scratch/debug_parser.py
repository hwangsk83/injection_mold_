import re
from pathlib import Path

VAL_DIR = Path(r"D:\Open_code_project\injection_mold_flow\validation_test")

time_dirs = []
for p in VAL_DIR.iterdir():
    if p.is_dir() and re.match(r"^\d+(\.\d+)?$", p.name):
        time_dirs.append(float(p.name))
time_dirs.sort()

print(f"Time dirs: {time_dirs}")

def get_time_dir_path(t_val):
    p_int = VAL_DIR / f"{int(t_val)}"
    if p_int.exists() and p_int.is_dir():
        return p_int
    return VAL_DIR / f"{t_val}"

def parse_nonuniform_field(file_path):
    if not file_path.exists():
        return None
    content = file_path.read_text(encoding="utf-8", errors="ignore")
    # 1. Try uniform match
    uni_match = re.search(r"internalField\s+uniform\s+([\d\.eE\+\-]+);", content)
    if uni_match:
        return [float(uni_match.group(1))] * 8000
    
    # 2. Try nonuniform parse
    if "nonuniform List" in content:
        start_idx = content.find("(", content.find("nonuniform"))
        end_idx = content.find(")", start_idx)
        if start_idx != -1 and end_idx != -1:
            data_str = content[start_idx+1:end_idx]
            vals = [float(v) for v in data_str.split() if v.strip()]
            return vals
    return None

for t in time_dirs:
    alpha_file = get_time_dir_path(t) / "alpha"
    vals = parse_nonuniform_field(alpha_file)
    if vals:
        outlet_cells_alpha = [vals[i] for i in range(len(vals)) if (i % 40) == 39]
        avg_outlet_alpha = sum(outlet_cells_alpha)/len(outlet_cells_alpha)
        print(f"t={t}: len(vals)={len(vals)}, outlet len={len(outlet_cells_alpha)}, avg alpha={avg_outlet_alpha:.4f}, max={max(vals):.4f}")
    else:
        print(f"t={t}: alpha file not found at {alpha_file}")

last_t = time_dirs[-1]
p_file = get_time_dir_path(last_t) / "p"
p_vals = parse_nonuniform_field(p_file)
if p_vals:
    print(f"Pressure drop at last_t={last_t}: len={len(p_vals)}, max={max(p_vals):.4f}")
else:
    print(f"p file not found at {p_file}")
