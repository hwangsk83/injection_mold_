# -*- coding: utf-8 -*-
"""
generate_thin_plate.py - Utility to generate a 100x50x2 mm thin plate binary STL file
"""
import struct
import numpy as np
from pathlib import Path

def create_thin_plate_stl(filepath: Path, dx=100.0, dy=50.0, dz=2.0):
    # Vertices of the 8 corners of the box
    # 0: (0,0,0), 1: (dx,0,0), 2: (dx,dy,0), 3: (0,dy,0)
    # 4: (0,0,dz), 5: (dx,0,dz), 6: (dx,dy,dz), 7: (0,dy,dz)
    v = [
        [0.0, 0.0, 0.0],
        [dx, 0.0, 0.0],
        [dx, dy, 0.0],
        [0.0, dy, 0.0],
        [0.0, 0.0, dz],
        [dx, 0.0, dz],
        [dx, dy, dz],
        [0.0, dy, dz]
    ]

    # 12 triangles (2 per face, 6 faces)
    # Each item has: [normal, v1_idx, v2_idx, v3_idx]
    triangles = [
        # Bottom Face (-Z) - Normal: (0, 0, -1)
        [[0.0, 0.0, -1.0], 0, 2, 1],
        [[0.0, 0.0, -1.0], 0, 3, 2],
        # Top Face (+Z) - Normal: (0, 0, 1)
        [[0.0, 0.0, 1.0], 4, 5, 6],
        [[0.0, 0.0, 1.0], 4, 6, 7],
        # Front Face (-Y) - Normal: (0, -1, 0)
        [[0.0, -1.0, 0.0], 0, 1, 5],
        [[0.0, -1.0, 0.0], 0, 5, 4],
        # Back Face (+Y) - Normal: (0, 1, 0)
        [[0.0, 1.0, 0.0], 2, 3, 7],
        [[0.0, 1.0, 0.0], 2, 7, 6],
        # Left Face (-X) - Normal: (-1, 0, 0)
        [[-1.0, 0.0, 0.0], 0, 4, 7],
        [[-1.0, 0.0, 0.0], 0, 7, 3],
        # Right Face (+X) - Normal: (1, 0, 0)
        [[1.0, 0.0, 0.0], 1, 6, 5],
        [[1.0, 0.0, 0.0], 1, 2, 6]
    ]

    header = f"Thin Plate {dx}x{dy}x{dz}mm Binary STL".encode('utf-8').ljust(80, b'\x00')
    n_triangles = len(triangles)
    
    with open(filepath, 'wb') as f:
        f.write(header)
        f.write(struct.pack('<I', n_triangles))
        
        for normal, v1_idx, v2_idx, v3_idx in triangles:
            # Write Normal
            f.write(struct.pack('<fff', *normal))
            # Write 3 Vertices
            f.write(struct.pack('<fff', *v[v1_idx]))
            f.write(struct.pack('<fff', *v[v2_idx]))
            f.write(struct.pack('<fff', *v[v3_idx]))
            # Attribute byte count (2 bytes)
            f.write(struct.pack('<H', 0))

    print(f"Created: {filepath} ({n_triangles} triangles)")

if __name__ == "__main__":
    out_path = Path(r"D:\Open_code_project\injection_mold_flow\thin_plate_100x50x2.stl")
    create_thin_plate_stl(out_path)
