#!/usr/bin/env python3
# polarization_ray_tracer.py - Temperature-dependent Photoelastic Ray Tracer
import os
import json
import numpy as np
from PIL import Image
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
SPEC_JSON = WORKSPACE / "machine_spec.json"
OUT_IMG = WORKSPACE / "rainbow_fringes.png"

def render_photoelastic_rainbow():
    print("[POLARIZATION RAY TRACER] Building temperature-dependent crossed polariscope simulation...")
    
    # 1. Load viscoelastic & material specs
    with open(SPEC_JSON, "r", encoding="utf-8") as f:
        specs = json.load(f)
        
    visco = specs.get("viscoelastic_data", {})
    Tg = visco.get("Tg", 423.15) # in Kelvin (150C)
    C1 = visco.get("C1", 17.44)
    C2 = visco.get("C2", 51.60)
    
    # Base stress-optical coefficient in Brewster (10^-12 m^2/N)
    # Generic polycarbonate has ~3500 Brewster
    C0_brewster = 3500.0
    C0 = C0_brewster * 1e-12  # convert to Pa^-1
    
    # WLF Temperature-dependent Stress-Optical Coefficient: C = f(T)
    # C(T) increases rapidly near Tg due to chain mobility
    def get_stress_optical_coeff(T):
        if T < Tg:
            # Below Tg: glass state, constant or slowly increasing
            dt = Tg - T
            return C0 / (1.0 + 0.005 * dt)
        else:
            # Above Tg: rubbery state, WLF-like scaling
            dt = T - Tg
            # WLF term: exp(-C1*dt/(C2+dt))
            # Viscosity drops but optical response might swell
            shift = np.exp(-C1 * dt / (C2 + dt))
            return C0 * (1.0 + 5.0 * (1.0 - shift))
            
    # 2. Set up high-resolution image rendering grid
    width, height = 800, 400
    img_data = np.zeros((height, width, 3), dtype=np.uint8)
    
    # RGB wavelengths in meters
    lambda_R = 650e-9
    lambda_G = 550e-9
    lambda_B = 450e-9
    
    print("  Simulating light propagation through crossed polarizers...")
    
    # 3. Ray tracing loop (vectorized over the grid)
    x = np.linspace(0.0, 0.150, width)
    y = np.linspace(0.0, 0.075, height)
    xx, yy = np.meshgrid(x, y)
    
    # Simulate a spatial temperature field (cooler near mold boundaries, hot at injection gate)
    # Gate is around (0.075, 0.0375)
    gate_x, gate_y = 0.075, 0.0375
    dist_gate = np.sqrt((xx - gate_x)**2 + (yy - gate_y)**2)
    
    # Temperature field: T_melt = 563K, T_mold = 373K
    melt_temp = 563.15
    mold_temp = 373.15
    # Thermal gradient decaying from core gate
    temp_field = mold_temp + (melt_temp - mold_temp) * np.exp(-15.0 * dist_gate)
    
    # Local stresses (highly non-uniform due to flow shear and gate pressure)
    # Principal stress differences delta_sigma (Pa)
    stress_base = 45.2 * 1e6 # 45.2 MPa from residual stress spec
    # Simulate multi-axis shear stress patterns creating standard photoelastic fringes
    sigma_diff = stress_base * (
        0.3 * np.sin(40.0 * xx) * np.cos(40.0 * yy) + 
        0.7 * np.exp(-30.0 * dist_gate) + 
        0.2 * np.sin(10.0 * yy)
    )
    sigma_diff = np.abs(sigma_diff)
    
    # Principal stress orientation angle phi (relative to polarizer axis)
    phi = np.arctan2(yy - gate_y, xx - gate_x) + 0.1 * np.sin(20.0 * xx)
    
    # Vectorized C(T)
    C_T = np.vectorize(get_stress_optical_coeff)(temp_field)
    
    # Retardation R = C(T) * delta_sigma * d (thickness = 1.2mm)
    thickness = 0.0012 # meters
    retardation = C_T * sigma_diff * thickness
    
    # Transmittance for crossed polarizers: I = I0 * sin^2(2*phi) * sin^2(pi * R / lambda)
    sin_2phi_sq = np.sin(2.0 * phi) ** 2
    
    # RGB Transmittance channels
    trans_R = sin_2phi_sq * (np.sin(np.pi * retardation / lambda_R) ** 2)
    trans_G = sin_2phi_sq * (np.sin(np.pi * retardation / lambda_G) ** 2)
    trans_B = sin_2phi_sq * (np.sin(np.pi * retardation / lambda_B) ** 2)
    
    # Apply standard scaling and clip
    r_chan = np.clip(trans_R * 255.0, 0, 255).astype(np.uint8)
    g_chan = np.clip(trans_G * 255.0, 0, 255).astype(np.uint8)
    b_chan = np.clip(trans_B * 255.0, 0, 255).astype(np.uint8)
    
    # Assemble image
    img_data[:, :, 0] = r_chan
    img_data[:, :, 1] = g_chan
    img_data[:, :, 2] = b_chan
    
    # Save Image
    img = Image.fromarray(img_data)
    img.save(str(OUT_IMG))
    print(f"  [Output Render] Polariscope rainbow fringes saved to: {OUT_IMG}")
    
    # Update specs
    specs["polarization_ray_tracer"] = {
        "image_width": width,
        "image_height": height,
        "stress_optical_base_Brewster": C0_brewster,
        "max_simulated_retardation_nm": float(np.max(retardation) * 1e9),
        "mean_simulated_temperature_K": float(np.mean(temp_field)),
        "status": "SUCCESS"
    }
    with open(SPEC_JSON, "w", encoding="utf-8") as f:
        json.dump(specs, f, indent=4)
        
    print("[SUCCESS] Photoelastic rainbow ray tracing complete.")
    return True

if __name__ == "__main__":
    render_photoelastic_rainbow()
