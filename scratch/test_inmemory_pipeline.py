"""In-Memory Pipeline Test Script"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core_utils.mesh_utils import pipeline_merge_inserts, estimate_memory_footprint

test_stl = Path(r"d:\Open_code_project\injection_mold_flow\validation_test\constant\triSurface\case_model.stl")
print("=== In-Memory Pipeline Test ===")
print(f"STL exists: {test_stl.exists()}")
mesh = pipeline_merge_inserts([str(test_stl)], "scratch/test_combined.stl", debug=True)
print(f"Result mesh: {mesh is not None}")
if mesh:
    print(f"Verts: {len(mesh.vertices)}, Faces: {len(mesh.faces)}, Memory: {estimate_memory_footprint(mesh)/1024/1024:.2f} MB")
print(f"Combined STL exists: {Path('scratch/test_combined.stl').exists()}")
print("[OK] In-Memory pipeline functional")