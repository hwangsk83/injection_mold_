import re
from pathlib import Path

VAL_DIR = Path(r"D:\Open_code_project\injection_mold_flow\validation_test")

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

# Find cell index mappings to x coordinates using blockMeshDict logic or simple index geometry:
# hex (0 1 2 3 4 5 6 7) (40 20 10)
# simpleGrading (1 1 1)
# Grid layout: 40 cells along X (i_x = 0..39), 20 cells along Y (i_y = 0..19), 10 cells along Z (i_z = 0..9)
# Let's inspect blockMesh cell layout. Typically in OpenFOAM, blockMesh orders cell index as:
# cell_index = i_x + 40 * (i_y + 20 * i_z)
# Let's write out some coordinates or coordinates of centers. 
# Better yet, let's look at alpha in D:\Open_code_project\injection_mold_flow\validation_test\3\alpha:
vals = parse_nonuniform_field(VAL_DIR / "3" / "alpha")
if vals:
    # Let's group alpha values by their coordinate index
    # We want to see how many alpha values are close to 1.0 vs 0.0, and find which cell indices are actually filled!
    above_05 = [i for i, val in enumerate(vals) if val > 0.05]
    print(f"Total cells > 0.05 alpha: {len(above_05)}")
    # If the flow goes from x=0 (inlet) to x=0.2 (outlet), and total length is 200mm (40 cells)
    # The cell coordinate along X is i_x = cell_index % 40.
    # Let's map how far the front has progressed:
    x_positions_filled = [i % 40 for i in above_05]
    if x_positions_filled:
        print(f"Max filled cell index along X: {max(x_positions_filled)} / 39")
        print(f"Min filled cell index along X: {min(x_positions_filled)}")
        # Count cells filled at each i_x
        counts = {}
        for ix in x_positions_filled:
            counts[ix] = counts.get(ix, 0) + 1
        sorted_counts = sorted(counts.items())
        print(f"Counts per X-slice (ix, filled_count_out_of_200): {sorted_counts[:10]} ... {sorted_counts[-10:]}")
