"""
Standalone script to create dummy_mold_case for injectionFoam testing.
Does not import app.py (avoids streamlit dependency).
"""
from pathlib import Path

case_path = Path(r"D:\Open_code_project\injection_mold_flow\dummy_mold_case")

(case_path / "system").mkdir(parents=True, exist_ok=True)
(case_path / "constant").mkdir(parents=True, exist_ok=True)
(case_path / "0").mkdir(parents=True, exist_ok=True)

files = {}

files["system/controlDict"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application     injectionFoam;
startFrom       startTime;
startTime       0;
stopAt          endTime;
endTime         0.05;
deltaT          0.001;
writeControl    adjustableRunTime;
writeInterval   0.01;
purgeWrite      0;
writeFormat     ascii;
writePrecision  6;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;
"""

files["system/blockMeshDict"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object blockMeshDict; }
scale 0.001;
vertices
(
    (0 0 0)  (100 0 0)  (100 50 0)  (0 50 0)
    (0 0 10) (100 0 10) (100 50 10) (0 50 10)
);
blocks
(
    hex (0 1 2 3 4 5 6 7) (20 10 2) simpleGrading (1 1 1)
);
edges ();
boundary
(
    gate_inlet { type patch; faces ((0 4 7 3)); }
    outlet     { type patch; faces ((1 2 6 5)); }
    walls      { type wall;  faces ((0 1 5 4)(3 2 6 7)(0 1 2 3)(4 5 6 7)); }
);
"""

files["system/fvSchemes"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object fvSchemes; }
ddtSchemes      { default Euler; }
gradSchemes     { default Gauss linear; }
divSchemes      { default none; div(phi,U) Gauss linearUpwind grad(U); div(phi,alpha) Gauss vanLeer; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
"""

files["system/fvSolution"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
solvers
{
    p     { solver PCG; preconditioner DIC; tolerance 1e-6; relTol 0.05; }
    U     { solver PBiCGStab; preconditioner DILU; tolerance 1e-5; relTol 0.1; }
    alpha { solver PBiCGStab; preconditioner DILU; tolerance 1e-6; relTol 0; }
}
PIMPLE { nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 1; }
"""

files["constant/transportProperties"] = """\
FoamFile { version 2.0; format ascii; class dictionary; object transportProperties; }
CrossWLFCoeffs
{
    D1      1.2e14;
    D2      263.15;
    D3      0;
    A1      25.5;
    A2      0.16;
}
TaitCoeffs
{
    b1m     0.001;
    b2m     1e-6;
    b3m     1.2e8;
    b4m     0.004;
    b5      263.15;
    C_tait  0.0894;
}
"""

files["0/p"] = """\
FoamFile { version 2.0; format ascii; class volScalarField; object p; }
dimensions [1 -1 -2 0 0 0 0];
internalField uniform 1e5;
boundaryField
{
    gate_inlet { type fixedValue; value uniform 1.5e8; }
    outlet     { type fixedValue; value uniform 1e5; }
    walls      { type zeroGradient; }
}
"""

files["0/U"] = """\
FoamFile { version 2.0; format ascii; class volVectorField; object U; }
dimensions [0 1 -1 0 0 0 0];
internalField uniform (0 0 0);
boundaryField
{
    gate_inlet { type fixedValue; value uniform (0.05 0 0); }
    outlet     { type zeroGradient; }
    walls      { type noSlip; }
}
"""

files["0/T"] = """\
FoamFile { version 2.0; format ascii; class volScalarField; object T; }
dimensions [0 0 0 1 0 0 0];
internalField uniform 503.15;
boundaryField
{
    gate_inlet { type fixedValue; value uniform 503.15; }
    outlet     { type zeroGradient; }
    walls      { type fixedValue; value uniform 323.15; }
}
"""

files["0/alpha"] = """\
FoamFile { version 2.0; format ascii; class volScalarField; object alpha; }
dimensions [0 0 0 0 0 0 0];
internalField uniform 0;
boundaryField
{
    gate_inlet { type fixedValue; value uniform 1; }
    outlet     { type zeroGradient; }
    walls      { type zeroGradient; }
}
"""

for rel_path, content in files.items():
    fpath = case_path / rel_path
    fpath.write_text(content, encoding="utf-8")
    print(f"  Created: {rel_path}")

print(f"\ndummy_mold_case created at: {case_path}")
