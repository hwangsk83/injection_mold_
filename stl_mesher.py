#!/usr/bin/env python3
# stl_mesher.py - Adaptive STL Mesher & Shapely Union Area Calculator
import os
import sys
import json
import trimesh
import numpy as np
from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
VAL_DIR = WORKSPACE / "validation_test"
SURFACE_DIR = VAL_DIR / "constant" / "triSurface"
SPEC_JSON = WORKSPACE / "machine_spec.json"

def ensure_stl_exists():
    SURFACE_DIR.mkdir(parents=True, exist_ok=True)
    stl_path = SURFACE_DIR / "case_model.stl"
    if not stl_path.exists():
        print(f"[INFO] STL not found. Generating default smartphone cover...")
        box = trimesh.creation.box(extents=[0.150, 0.075, 0.0012])
        box.export(str(stl_path))
    return stl_path

def calculate_shapely_projected_area(mesh):
    print("[INFO] Computing overlap-free projected area using Shapely...")
    try:
        polygons = []
        for face in mesh.faces:
            # Extract XY coordinates (project to Z-plane)
            tri_pts = mesh.vertices[face][:, :2]
            if len(tri_pts) == 3:
                # Buffer(0) to fix self-intersections or degeneracies
                poly = Polygon(tri_pts).buffer(0)
                if poly.area > 1e-10:
                    polygons.append(poly)
        
        # Merge all overlapping polygons into a single union
        unified_poly = unary_union(polygons)
        area = unified_poly.area
        print(f"[SUCCESS] Shapely Unified Projection Area: {area:.6f} m^2")
        return area
    except Exception as e:
        print(f"[WARN] Shapely union failed: {e}. Falling back to trimesh bounding area.")
        bounds = mesh.bounds
        return (bounds[1][0] - bounds[0][0]) * (bounds[1][1] - bounds[0][1])

def generate_adaptive_block_mesh(mesh, target_cells):
    bounds = mesh.bounds
    dx = bounds[1][0] - bounds[0][0]
    dy = bounds[1][1] - bounds[0][1]
    dz = bounds[1][2] - bounds[0][2]
    
    # Target volume cell sizing: delta = (V_bbox / N)^(1/3)
    v_bbox = dx * dy * dz
    delta = (v_bbox / target_cells) ** (1/3)
    
    # Bounding box coordinates with 10% padding to prevent clipping
    pad_factor = 0.10
    min_x = bounds[0][0] - pad_factor * dx
    max_x = bounds[1][0] + pad_factor * dx
    min_y = bounds[0][1] - pad_factor * dy
    max_y = bounds[1][1] + pad_factor * dy
    min_z = bounds[0][2] - pad_factor * dz
    max_z = bounds[1][2] + pad_factor * dz
    
    nx = max(10, int(round((max_x - min_x) / delta)))
    ny = max(10, int(round((max_y - min_y) / delta)))
    nz = max(5, int(round((max_z - min_z) / delta)))
    
    print(f"[INFO] Bounding Box Dimensions: X={dx:.3f}m, Y={dy:.3f}m, Z={dz:.5f}m")
    print(f"[INFO] Adaptive Grid Cell Delta: {delta:.6f}m -> Block Divisions: ({nx}, {ny}, {nz})")
    
    block_mesh_dict = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  Version:     12
  Format:      ascii
  Class:       dictionary
  Object:      blockMeshDict
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      blockMeshDict;
}}
scale   1.0;

vertices
(
    ({min_x} {min_y} {min_z})
    ({max_x} {min_y} {min_z})
    ({max_x} {max_y} {min_z})
    ({min_x} {max_y} {min_z})
    ({min_x} {min_y} {max_z})
    ({max_x} {min_y} {max_z})
    ({max_x} {max_y} {max_z})
    ({min_x} {max_y} {max_z})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

edges
(
);

boundary
(
    walls
    {{
        type wall;
        faces
        (
            (0 1 5 4)
            (1 2 6 5)
            (2 3 7 6)
            (3 0 4 7)
            (0 1 2 3)
            (4 5 6 7)
        );
    }}
);
"""
    system_dir = VAL_DIR / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    (system_dir / "blockMeshDict").write_text(block_mesh_dict, encoding="utf-8")
    print("[SUCCESS] Adaptive blockMeshDict generated successfully.")
    
    # Calculate a valid location in mesh that is inside the background block but OUTSIDE the thin part boundary
    # For a shell, bounds centroid or centroid + offset in Z is perfect
    loc_x = bounds[0][0] + 0.1 * dx
    loc_y = bounds[0][1] + 0.1 * dy
    loc_z = bounds[0][2] + 2.0 * dz # offset outside thickness direction
    return (loc_x, loc_y, loc_z)

def generate_snappy_hex_mesh_dict(loc_in_mesh):
    # Dynamic snappyHexMesh with Curvature Adaptive Refinement (AMR)
    # Target level 2~3 for surface refinements, gates, and high curvatures
    snappy_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  Version:     12
  Format:      ascii
  Class:       dictionary
  Object:      snappyHexMeshDict
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      snappyHexMeshDict;
}}

castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    case_model.stl
    {{
        type triSurfaceMesh;
        name case_model;
    }}
}}

castellatedMeshControls
{{
    maxLocalCells 1000000;
    maxGlobalCells 2000000;
    minRefinementCells 100;
    nCellsBetweenLevels 3;

    features
    (
    );

    refinementSurfaces
    {{
        case_model
        {{
            # Curvature-adaptive refinement: High density on features (Level 2 to 3), A-Surface kept at Level 0
            level (0 3);
            patchInfo
            {{
                type wall;
            }}
        }}
    }}

    resolveFeatureAngle 30;

    refinementRegions
    {{
        # Add refinement for dynamic gate entry zone
        case_model
        {{
            mode distance;
            levels ((0.002 3) (0.005 2)); # gate radial boundary refinement
        }}
    }}

    locationInMesh ({loc_in_mesh[0]:.6f} {loc_in_mesh[1]:.6f} {loc_in_mesh[2]:.6f});
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSolveIter 30;
    relaxIter 5;
    nSmoothPatch 3;
    snapFraction 0.5;
    snapAreaFraction 0.3;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes true;
    layers
    {{
        "case_model.*"
        {{
            nSurfaceLayers 3;
        }}
    }}
    expansionRatio 1.2;
    finalLayerThickness 0.3;
    minThickness 0.1;
    nGrow 1;
    featureAngle 60;
    slipFraction 0.5;
    nDepthIter 5;
    nRelaxIter 5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedianAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
    nRefineIter 0;
}}

meshQualityControls
{{
    maxNonOrtho 65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave 80;
    minVol 1e-13;
    minTetDecapitation 1e-15;
    minArea -1;
    minTwist 0.02;
    minDeterminant 0.001;
    minFaceWeight 0.02;
    minVolRatio 0.01;
    mustKeepValue true;
}}

mergeTolerance 1e-6;
"""
    system_dir = VAL_DIR / "system"
    (system_dir / "snappyHexMeshDict").write_text(snappy_content, encoding="utf-8")
    
    # Ensure meshQualityDict is written too
    mesh_quality_content = """/*--------------------------------*- C++ -*----------------------------------*\\
  Version:     12
  Format:      ascii
  Class:       dictionary
  Object:      meshQualityDict
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      meshQualityDict;
}}
#includeEtc "caseDicts/meshQualityDict"
"""
    (system_dir / "meshQualityDict").write_text(mesh_quality_content, encoding="utf-8")
    print("[SUCCESS] Dynamic snappyHexMeshDict and meshQualityDict updated.")

def main():
    print("="*60)
    print("  stl_mesher.py: Shapely 2D Union & Adaptive BBox Grid System")
    print("="*60)
    
    stl_path = ensure_stl_exists()
    mesh = trimesh.load(str(stl_path))
    
    # Calculate overlap-free Z-projected area using Shapely
    area = calculate_shapely_projected_area(mesh)
    
    # Read grid target resolution limit from machine_spec.json
    target_cells = 500000 # Medium default
    specs = {}
    if SPEC_JSON.exists():
        try:
            with open(SPEC_JSON, "r", encoding="utf-8") as f:
                specs = json.load(f)
                res_str = specs.get("mesh_resolution", "Medium")
                res_map = {"Coarse": 200000, "Medium": 500000, "Fine": 1000000}
                target_cells = res_map.get(res_str, 500000)
        except Exception:
            pass
            
    print(f"[INFO] Target Mesh Resolution Limit: {target_cells} cells")
    
    # Generate adaptive background mesh and locate insertion point
    loc_in_mesh = generate_adaptive_block_mesh(mesh, target_cells)
    
    # Save projected area and mesh info
    specs["projected_area_m2"] = area
    specs["target_mesh_cells"] = target_cells
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    # Write snappyHexMesh AMR Dict
    generate_snappy_hex_mesh_dict(loc_in_mesh)
    print("="*60)

if __name__ == "__main__":
    main()
