#!/usr/bin/env pvpython
# defect_analyzer.py - Manufacturing-grade automated defect analyzer using pvpython
import os
import sys
import csv
from pathlib import Path

# Paths & configuration
WORKSPACE_ROOT = Path(r"d:\Open_code_project\injection_mold_flow")
VAL_DIR = WORKSPACE_ROOT / "validation_test"
VTK_DIR = VAL_DIR / "VTK"
OUTPUT_CSV = WORKSPACE_ROOT / "weld_line_risk_zones.csv"
LOG_FILE = WORKSPACE_ROOT / "defect_analysis.log"

# Append ParaView libraries if not loaded
try:
    from paraview.simple import *
except ImportError:
    print("[ERROR] paraview.simple cannot be imported. Ensure this is run via pvpython.")
    sys.exit(1)

# Import material database for Tg
sys.path.append(str(WORKSPACE_ROOT))
from material_db import MATERIAL_DB
selected_material = "ABS"
Tg = MATERIAL_DB[selected_material]["Thermal"]["Tg"]
print(f"Loaded {selected_material} Glass Transition Temperature Tg = {Tg:.2f} K")

# Find latest reconstructed VTK file (internal mesh)
vtk_files = list(VTK_DIR.glob("validation_test_*.vtk"))
if not vtk_files:
    print("[ERROR] No validation_test_*.vtk internal mesh files found.")
    sys.exit(1)

# Sort files by index (e.g. validation_test_3000.vtk -> 3000)
def get_vtk_index(f):
    name = f.stem
    try:
        return int(name.split("_")[-1])
    except ValueError:
        return -1

vtk_files.sort(key=get_vtk_index)
latest_vtk = vtk_files[-1]
print(f"Latest target VTK file found: {latest_vtk.name}")

# Log file setup
log_stream = open(LOG_FILE, "w", encoding="utf-8")
def log_and_print(msg):
    print(msg)
    log_stream.write(msg + "\n")

log_and_print("==================================================")
log_and_print("        simple-injection-mold-sim Defect Analyzer")
log_and_print("==================================================")
log_and_print(f"Analyzing: {latest_vtk.name}")
log_and_print(f"Material: {selected_material} (Tg = {Tg} K)")

# 1. Load VTK dataset in ParaView simple API
reader = LegacyVTKReader(registrationName='VTKReader', FileNames=[str(latest_vtk)])

# Force updates
UpdatePipeline()

# Get dataset information
data_info = reader.GetDataInformation()
num_cells = data_info.GetNumberOfCells()
num_points = data_info.GetNumberOfPoints()
log_and_print(f"Grid structure: Cells = {num_cells}, Points = {num_points}")

# 2. Extract Cell Data Arrays
cell_data = data_info.GetCellDataInformation()
point_data = data_info.GetPointDataInformation()

# Check if fields are point data or cell data
# OpenFOAM foamToVTK writes volume fields (T, alpha, p, U) as cell data by default!
# Let's inspect available arrays
def list_arrays(data_info_type, label):
    arrays = []
    for i in range(data_info_type.GetNumberOfArrays()):
        arrays.append(data_info_type.GetArrayInformation(i).GetName())
    return arrays

cell_arrays = list_arrays(cell_data, "Cell")
point_arrays = list_arrays(point_data, "Point")
log_and_print(f"Available Cell Arrays: {cell_arrays}")
log_and_print(f"Available Point Arrays: {point_arrays}")

# 3. Solidification Fraction Quantification
# We will use ParaView's CellDataToPointData if arrays are cell-based, or process directly.
# For exact quantification, we can use the Python Calculator filter or parse cells.
# Since we are inside pvpython, we can fetch data block using servermanager to fetch arrays!
import paraview.servermanager as sm
from paraview.vtk.numpy_interface import dataset_adapter as dsa

# Convert source reader into numpy-accessible dataset wrapper
wrapped_data = dsa.WrapDataObject(servermanager.Fetch(reader))

# Check where 'T' and 'alpha' arrays are
if 'T' in wrapped_data.CellData.keys():
    t_arr = wrapped_data.CellData['T']
    alpha_arr = wrapped_data.CellData['alpha']
    u_arr = wrapped_data.CellData['U']
    p_arr = wrapped_data.CellData['p']
    data_source = "CellData"
elif 'T' in wrapped_data.PointData.keys():
    t_arr = wrapped_data.PointData['T']
    alpha_arr = wrapped_data.PointData['alpha']
    u_arr = wrapped_data.PointData['U']
    p_arr = wrapped_data.PointData['p']
    data_source = "PointData"
else:
    log_and_print("[ERROR] Temperature field 'T' not found in VTK dataset.")
    sys.exit(1)

# Compute solidification fraction
total_cells = len(t_arr)
frozen_count = 0
for val in t_arr:
    if val <= Tg:
        frozen_count += 1

solid_frac = (frozen_count / total_cells) * 100.0
log_and_print(f"\n--- [SOLIDIFICATION REPORT] ---")
log_and_print(f"Total evaluated mesh cells: {total_cells}")
log_and_print(f"Frozen mesh cells (T <= Tg): {frozen_count}")
log_and_print(f"Solidification Fraction:     {solid_frac:.2f}%")

# 4. Weldline Risk Zone Vector Collision Analysis
# Weldlines occur where melt fronts collide ($0.1 <= \alpha <= 0.9$)
# and opposing velocity vectors are present ($U_i \cdot U_j < 0$).
# We will identify coordinates meeting these criteria.
log_and_print(f"\n--- [WELDLINE ANALYSIS REPORT] ---")

# ParaView geometry cell centers
cell_centers_filter = CellCenters(Input=reader)
UpdatePipeline()
centers_wrapped = dsa.WrapDataObject(servermanager.Fetch(cell_centers_filter))
points = centers_wrapped.Points # Coordinates of cell centers

weldline_risk_zones = []
risk_threshold_dot = -0.1 # Opposing flow threshold (negative dot product)

# We want to check adjacent cells. For a high-performance check:
# We filter flow front cells first (0.1 <= alpha <= 0.9)
front_indices = []
for idx, val in enumerate(alpha_arr):
    if 0.1 <= val <= 0.9:
        front_indices.append(idx)

log_and_print(f"Total flow-front boundary cells found: {len(front_indices)}")

# Check coordinate proximity for opposing flows among front cells
import numpy as np

# We'll build a simple KDTree or basic spatial sweep to find adjacent front cells
# Since cell coordinates are organized, we check distance <= 0.015m (grid spacing)
coords = np.array([points[idx] for idx in front_indices])
vels = np.array([u_arr[idx] for idx in front_indices])

risk_count = 0
checked_pairs = set()

# Perform pairwise checks among nearby flow front cells
for i in range(len(front_indices)):
    for j in range(i + 1, len(front_indices)):
        idx_a = front_indices[i]
        idx_b = front_indices[j]
        
        # Physical Euclidean distance check
        dist = np.linalg.norm(coords[i] - coords[j])
        if dist < 0.01: # Check within 10mm proximity
            # Velocity collision dot product
            u_a = vels[i]
            u_b = vels[j]
            mag_a = np.linalg.norm(u_a)
            mag_b = np.linalg.norm(u_b)
            
            if mag_a > 1e-4 and mag_b > 1e-4:
                # Normalize velocities to check dot product direction
                dot_prod = np.dot(u_a / mag_a, u_b / mag_b)
                
                # Dynamic reference melt temperature and temperature drop
                t_ref = float(np.max(t_arr))
                t_avg = (t_arr[idx_a] + t_arr[idx_b]) / 2.0
                t_drop = t_ref - t_avg
                
                # Check if velocities are opposing and temperature drop is significant (T_drop > 5.0 K)
                if dot_prod < -0.1 and t_drop > 5.0:
                    risk_count += 1
                    avg_coords = (coords[i] + coords[j]) / 2.0
                    weldline_risk_zones.append({
                        "Cell_A": idx_a,
                        "Cell_B": idx_b,
                        "X": avg_coords[0],
                        "Y": avg_coords[1],
                        "Z": avg_coords[2],
                        "DotProduct": dot_prod,
                        "Temp_A": t_arr[idx_a],
                        "Temp_B": t_arr[idx_b],
                        "Alpha_A": alpha_arr[idx_a],
                        "Alpha_B": alpha_arr[idx_b]
                    })

log_and_print(f"Identified Opposing Flow Collision Points (Weld-line Risks): {len(weldline_risk_zones)}")

# 5. Export coordinate CSV
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Coordinate_X", "Coordinate_Y", "Coordinate_Z", "Velocity_Dot_Product", "Temp_Average", "Alpha_Average"])
    for zone in weldline_risk_zones:
        writer.writerow([
            f"{zone['X']:.6f}",
            f"{zone['Y']:.6f}",
            f"{zone['Z']:.6f}",
            f"{zone['DotProduct']:.4f}",
            f"{(zone['Temp_A'] + zone['Temp_B'])/2.0:.2f}",
            f"{(zone['Alpha_A'] + zone['Alpha_B'])/2.0:.4f}"
        ])

log_and_print(f"Successfully exported Weldline Risk Zones coordinates to: {OUTPUT_CSV.name}")
log_and_print("==================================================")
log_stream.close()
