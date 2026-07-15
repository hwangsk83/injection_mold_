import os
import sys
from pathlib import Path

def generate_gate_dictionaries(case_dir: Path, gates: list, u_inlet_vector: list = None):
    """
    사용자가 입력한 게이트 리스트(dict: Shape, X, Y, Z, R, W, H)를 해석하여
    topoSetDict 및 createPatchDict를 생성하고, 0/U 초기 유량 경계조건을 빌드합니다.
    (모든 수치는 mm단위에서 m단위로 변환하여 반영합니다.)
    """
    case_dir = Path(case_dir)
    system_dir = case_dir / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. topoSetDict 생성
    toposet_actions = []
    
    # 게이트별로 cylinderToCell 또는 boxToCell 추가
    for idx, gate in enumerate(gates):
        shape = gate.get("Shape", "Circular")
        x = gate.get("X", 0.0) / 1000.0
        y = gate.get("Y", 0.0) / 1000.0
        z = gate.get("Z", 0.0) / 1000.0
        
        # 첫 번째 게이트는 new, 그 다음은 add action 적용
        action_type = "new" if idx == 0 else "add"
        
        if shape == "Circular":
            radius = gate.get("R", 2.0) / 1000.0
            # Get direction vector, default to Z-axis alignment if not specified
            nx = gate.get("nx", 0.0)
            ny = gate.get("ny", 0.0)
            nz = gate.get("nz", 1.0)
            
            # Normalize vector
            norm = (nx**2 + ny**2 + nz**2)**0.5
            if norm > 1e-6:
                nx, ny, nz = nx/norm, ny/norm, nz/norm
            else:
                nx, ny, nz = 0.0, 0.0, 1.0
                
            # Align cylinder endpoints along direction vector (length 10mm)
            p1_x = x - 0.005 * nx
            p1_y = y - 0.005 * ny
            p1_z = z - 0.005 * nz
            p2_x = x + 0.005 * nx
            p2_y = y + 0.005 * ny
            p2_z = z + 0.005 * nz
            
            toposet_actions.append(f"""    {{
        name    inletCells;
        type    cellSet;
        action  {action_type};
        source  cylinderToCell;
        p1      ({p1_x:.6f} {p1_y:.6f} {p1_z:.6f});
        p2      ({p2_x:.6f} {p2_y:.6f} {p2_z:.6f});
        radius  {radius};
    }}""")
        elif shape == "Rectangular":
            w_m = gate.get("W", 4.0) / 1000.0
            h_m = gate.get("H", 4.0) / 1000.0
            minx = x - w_m / 2.0
            maxx = x + w_m / 2.0
            miny = y - h_m / 2.0
            maxy = y + h_m / 2.0
            # Narrow thickness Z mapping to partition across thin-wall Z-planes
            minz = z - 0.001
            maxz = z + 0.001
            # boxToCell을 통해 사각형 게이트 영역 지정
            toposet_actions.append(f"""    {{
        name    inletCells;
        type    cellSet;
        action  {action_type};
        source  boxToCell;
        box     ({minx:.6f} {miny:.6f} {minz:.6f}) ({maxx:.6f} {maxy:.6f} {maxz:.6f});
    }}""")
        
    # cellSet을 faceSet으로 변환
    toposet_actions.append("""    {
        name    inletFaces;
        type    faceSet;
        action  new;
        source  cellToFace;
        set     inletCells;
        option  all;
    }""")
    
    toposet_actions_str = "\n\n".join(toposet_actions)
    
    toposet_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  Version:     12
  Format:      ascii
  Class:       dictionary
  Object:      topoSetDict
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      topoSetDict;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

actions
(
{toposet_actions_str}
);
"""
    
    with open(system_dir / "topoSetDict", "w", encoding="utf-8") as f:
        f.write(toposet_content)
        
    # 2. createPatchDict 생성
    createpatch_content = """/*--------------------------------*- C++ -*----------------------------------*\\
  Version:     12
  Format:      ascii
  Class:       dictionary
  Object:      createPatchDict
\\*---------------------------------------------------------------------------*/
FoamFile
{
    version     2.0;
    format      ascii;
    class       dictionary;
    object      createPatchDict;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

pointSync false;

patches
(
    {
        name            gate_inlet;
        patchInfo
        {
            type            patch;
        }
        constructFrom   set;
        set             inletFaces;
    }
);
"""
    with open(system_dir / "createPatchDict", "w", encoding="utf-8") as f:
        f.write(createpatch_content)
        
    # 3. 0/U 초기 균등 분배 속도 파일 자동 셋업
    zero_dir = case_dir / "0"
    zero_dir.mkdir(parents=True, exist_ok=True)
    
    # 기본 유속 벡터 설정
    if u_inlet_vector is None:
        u_inlet_vector = [0.1, 0.0, 0.0]
        
    u_x, u_y, u_z = u_inlet_vector
    
    u_content = f"""/*--------------------------------*- C++ -*----------------------------------*\\
  Version:     12
  Format:      ascii
  Class:       volVectorField
  Location:    "0"
  Object:      U
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       volVectorField;
    object      U;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

dimensions      [0 1 -1 0 0 0 0];

internalField   uniform (0 0 0);

boundaryField
{{
    gate_inlet
    {{
        type            uniformFixedValue;
        uniformValue    table
        (
            (0 (0 0 0))
            (0.1 ({u_x} {u_y} {u_z}))
        );
    }}
    outlet
    {{
        type            zeroGradient;
    }}
    walls
    {{
        type            noSlip;
    }}
    defaultFaces
    {{
        type            noSlip;
    }}
}}
"""
    with open(zero_dir / "U", "w", encoding="utf-8") as f:
        f.write(u_content)

    return True
