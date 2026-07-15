#!/usr/bin/env python3
# cooling_mesher.py - Conjugate Heat Transfer (CHT) Multi-Region Mesher & Boundary Condition Generator
import os
import json
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
VAL_DIR = WORKSPACE / "validation_test"

def setup_cht_regions(case_path: Path):
    """
    Creates OpenFOAM 12 CHT Multi-Region Setup with regions:
    [fluid_polymer, solid_mold, fluid_water]
    """
    print(f"[CHT SETUP] Configuring CHT regions under case: {case_path}")
    
    # 1. Create constant/regionProperties
    constant_dir = case_path / "constant"
    constant_dir.mkdir(parents=True, exist_ok=True)
    
    region_props = """/*--------------------------------*- C++ -*----------------------------------*\\
  Version:     12
  Format:      ascii
  Class:       dictionary
  Object:      regionProperties
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      regionProperties;
}

regions
(
    fluid       (fluid_polymer fluid_water)
    solid       (solid_mold)
);
"""
    with open(constant_dir / "regionProperties", "w", encoding="utf-8") as f:
        f.write(region_props)
    
    # Create sub-region folders inside 0, constant, and system
    for r in ["fluid_polymer", "solid_mold", "fluid_water"]:
        (case_path / "0" / r).mkdir(parents=True, exist_ok=True)
        (case_path / "constant" / r).mkdir(parents=True, exist_ok=True)
        (case_path / "system" / r).mkdir(parents=True, exist_ok=True)
        
    # Write fvSchemes & fvSolution & controlDict for regions
    setup_region_dictionaries(case_path)
    
    print("[CHT SETUP] Multi-region folder hierarchy and regionProperties generated.")
    return True

def setup_region_dictionaries(case_path: Path):
    # Standard numerical settings to defend against SIGFPE
    fv_schemes_content = """FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }
ddtSchemes { default Euler; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) Gauss upwind; div(phi,h) Gauss upwind; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
"""
    
    fv_solution_content = """FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
solvers
{
    "h.*"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-08;
        relTol          0.0;
    }
    "U.*"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-06;
        relTol          0.1;
    }
    "p.*"
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-06;
        relTol          0.05;
    }
}
PIMPLE { nOuterCorrectors 2; nCorrectors 2; nNonOrthogonalCorrectors 1; }
"""
    
    # Write system configs for each region
    for r in ["fluid_polymer", "solid_mold", "fluid_water"]:
        sys_dir = case_path / "system" / r
        with open(sys_dir / "fvSchemes", "w", encoding="utf-8") as f:
            f.write(fv_schemes_content)
        with open(sys_dir / "fvSolution", "w", encoding="utf-8") as f:
            f.write(fv_solution_content)

    # 2. Write Boundary conditions for interfaces (turbulent coupled temperature)
    setup_boundary_conditions(case_path)

def setup_boundary_conditions(case_path: Path):
    # T boundary conditions for fluid_polymer interface with solid_mold
    polymer_t = """FoamFile { version 2.0; format ascii; class volScalarField; object T; }
dimensions      [0 0 0 1 0 0 0];
internalField   uniform 503.15;
boundaryField
{
    polymer_to_mold
    {
        type            compressible::turbulentTemperatureCoupledBaffleFx;
        value           uniform 503.15;
        neighborRegion  solid_mold;
        KName           K;
        K               uniform 0.19; // Polymer conductivity
    }
    gate_inlet
    {
        type            fixedValue;
        value           uniform 503.15;
    }
    outlet
    {
        type            zeroGradient;
    }
}
"""
    with open(case_path / "0" / "fluid_polymer" / "T", "w", encoding="utf-8") as f:
        f.write(polymer_t)
        
    # Mold Solid T boundary conditions
    mold_t = """FoamFile { version 2.0; format ascii; class volScalarField; object T; }
dimensions      [0 0 0 1 0 0 0];
internalField   uniform 323.15;
boundaryField
{
    mold_to_polymer
    {
        type            compressible::turbulentTemperatureCoupledBaffleFx;
        value           uniform 323.15;
        neighborRegion  fluid_polymer;
        KName           K;
        K               uniform 45.0; // Steel conductivity
    }
    mold_to_water
    {
        type            compressible::turbulentTemperatureCoupledBaffleFx;
        value           uniform 323.15;
        neighborRegion  fluid_water;
        KName           K;
        K               uniform 45.0;
    }
    outer_walls
    {
        type            zeroGradient;
    }
}
"""
    with open(case_path / "0" / "solid_mold" / "T", "w", encoding="utf-8") as f:
        f.write(mold_t)

    # Water Fluid T boundary conditions (Turbulent Inlet flow setup, Re > 10,000)
    # Re = U * D / nu. With high Re, turbulent inlet properties are setup
    water_t = """FoamFile { version 2.0; format ascii; class volScalarField; object T; }
dimensions      [0 0 0 1 0 0 0];
internalField   uniform 298.15;
boundaryField
{
    water_to_mold
    {
        type            compressible::turbulentTemperatureCoupledBaffleFx;
        value           uniform 298.15;
        neighborRegion  solid_mold;
        KName           K;
        K               uniform 0.6; // Water conductivity
    }
    water_inlet
    {
        type            fixedValue;
        value           uniform 298.15; // 25C standard cooling water
    }
    water_outlet
    {
        type            zeroGradient;
    }
}
"""
    with open(case_path / "0" / "fluid_water" / "T", "w", encoding="utf-8") as f:
        f.write(water_t)

    # Velocity boundary for water fluid to ensure high Reynolds flow (turbulent standard)
    water_u = """FoamFile { version 2.0; format ascii; class volVectorField; object U; }
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform (1.5 0 0); // ~1.5 m/s velocity for turbulent flow (Re > 10000)
boundaryField
{
    water_to_mold
    {
        type            noSlip;
    }
    water_inlet
    {
        type            fixedValue;
        value           uniform (1.5 0 0);
    }
    water_outlet
    {
        type            zeroGradient;
    }
}
"""
    with open(case_path / "0" / "fluid_water" / "U", "w", encoding="utf-8") as f:
        f.write(water_u)

def main():
    setup_cht_regions(VAL_DIR)

if __name__ == "__main__":
    main()
