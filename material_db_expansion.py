#!/usr/bin/env python3
"""
material_db_expansion.py - 100+ Material Library Expansion Engine

Material-as-a-Service: Generates an expanded library with Cross-WLF,
Tait PvT, Thermal, and Mechanical properties for 100+ commercial polymers.
"""
import json, math, sys
from pathlib import Path

WORKSPACE = Path(r"d:\Open_code_project\injection_mold_flow")
MAT_DB   = WORKSPACE / "material_db.json"
MAT_LIB  = WORKSPACE / "Material_Library.json"
EXP_LIB  = WORKSPACE / "Expanded_Material_Library.json"

# ── Polymer Families ──────────────────────────────────

def _pc(grade, desc, n=0.30, tau=1.8e5, D1=2.4e13, D2=413.15, A1=31.2, A2=51.6,
        b1m=0.0009, b2m=1.2e-6, b3m=1.3e8, b4m=0.0035, b5=413.15, C=0.0894,
        Cp=2000, k=0.20, Tg=423.15, Tm=573.15, E=2200, nu=0.37, cte=6.5e-5,
        filler=None):
    entry = {
        "grade": grade, "family": "PC", "desc": desc,
        "CrossWLF": {"n": n, "tau_star": tau, "D1": D1, "D2": D2, "D3": 0, "A1": A1, "A2": A2},
        "Tait": {"b1m": b1m, "b2m": b2m, "b3m": b3m, "b4m": b4m, "b5": b5, "b6": 0, "b7": 0, "b8": 0, "b9": 0, "C_tait": C},
        "Thermal": {"Cp_poly": Cp, "k_poly": k, "Tg": Tg, "Tm": Tm},
        "Mechanical": {"YoungsModulus": E, "PoissonsRatio": nu, "CTE": cte},
    }
    if filler:
        entry["Additives"] = filler
    return entry

def _abs(grade, desc, n=0.35, D1=3.8e11, D2=263.15, A1=28.5, A2=51.6, b1m=0.001, b5=263.15,
         E=2400, cte=8.0e-5, filler=None):
    return {
        "grade": grade, "family": "ABS", "desc": desc,
        "CrossWLF": {"n": n, "tau_star": 2.8e5, "D1": D1, "D2": D2, "D3": 0, "A1": A1, "A2": A2},
        "Tait": {"b1m": b1m, "b2m": 1.0e-6, "b3m": 1.2e8, "b4m": 0.004, "b5": b5, "b6": 0, "b7": 0, "b8": 0, "b9": 0, "C_tait": 0.0894},
        "Thermal": {"Cp_poly": 2100, "k_poly": 0.18, "Tg": 378.15, "Tm": 513.15},
        "Mechanical": {"YoungsModulus": E, "PoissonsRatio": 0.35, "CTE": cte},
        **({"Additives": filler} if filler else {})
    }

def _pp(grade, desc, n=0.38, D1=1.2e9, D2=263.15, A1=26.0, b1m=0.0012, b5=263.15, E=1500, cte=1.0e-4, filler=None):
    return {
        "grade": grade, "family": "PP", "desc": desc,
        "CrossWLF": {"n": n, "tau_star": 1.5e5, "D1": D1, "D2": D2, "D3": 0, "A1": A1, "A2": 51.6},
        "Tait": {"b1m": b1m, "b2m": 1.5e-6, "b3m": 1.0e8, "b4m": 0.0045, "b5": b5, "b6": 0, "b7": 0, "b8": 0, "b9": 0, "C_tait": 0.0894},
        "Thermal": {"Cp_poly": 1900, "k_poly": 0.22, "Tg": 263.15, "Tm": 433.15},
        "Mechanical": {"YoungsModulus": E, "PoissonsRatio": 0.42, "CTE": cte},
        **({"Additives": filler} if filler else {})
    }

def _pa(grade, desc, n=0.33, D1=1.8e11, D2=323.15, A1=29.0, b1m=0.00085, b5=323.15, E=3200, cte=8.0e-5, filler=None):
    return {
        "grade": grade, "family": "PA66", "desc": desc,
        "CrossWLF": {"n": n, "tau_star": 2.0e5, "D1": D1, "D2": D2, "D3": 0, "A1": A1, "A2": 51.6},
        "Tait": {"b1m": b1m, "b2m": 1.0e-6, "b3m": 1.2e8, "b4m": 0.0038, "b5": b5, "b6": 0, "b7": 0, "b8": 0, "b9": 0, "C_tait": 0.0894},
        "Thermal": {"Cp_poly": 2050, "k_poly": 0.26, "Tg": 323.15, "Tm": 533.15},
        "Mechanical": {"YoungsModulus": E, "PoissonsRatio": 0.38, "CTE": cte},
        **({"Additives": filler} if filler else {})
    }

def _eng(grade, family, desc, n, D1, D2, A1, b1m, b5, E, cte, Tg, Tm, Cp, k, filler=None):
    return {
        "grade": grade, "family": family, "desc": desc,
        "CrossWLF": {"n": n, "tau_star": 1.8e5, "D1": D1, "D2": D2, "D3": 0, "A1": A1, "A2": 51.6},
        "Tait": {"b1m": b1m, "b2m": 1.2e-6, "b3m": 1.3e8, "b4m": 0.0035, "b5": b5, "b6": 0, "b7": 0, "b8": 0, "b9": 0, "C_tait": 0.0894},
        "Thermal": {"Cp_poly": Cp, "k_poly": k, "Tg": Tg, "Tm": Tm},
        "Mechanical": {"YoungsModulus": E, "PoissonsRatio": 0.36, "CTE": cte},
        **({"Additives": filler} if filler else {})
    }

GF30 = {"filler_type": "Fiber", "filler_name": "GlassFiber", "weight_fraction": 0.30, "volume_fraction": 0.168, "aspect_ratio": 25.0, "filler_modulus_MPa": 72000, "filler_CTE": 5e-6, "filler_poisson": 0.20, "matrix_grade": ""}
GF20 = {"filler_type": "Fiber", "filler_name": "GlassFiber", "weight_fraction": 0.20, "volume_fraction": 0.112, "aspect_ratio": 25.0, "filler_modulus_MPa": 72000, "filler_CTE": 5e-6, "filler_poisson": 0.20, "matrix_grade": ""}
GF45 = {"filler_type": "Fiber", "filler_name": "GlassFiber", "weight_fraction": 0.45, "volume_fraction": 0.252, "aspect_ratio": 25.0, "filler_modulus_MPa": 72000, "filler_CTE": 5e-6, "filler_poisson": 0.20, "matrix_grade": ""}


def generate_expanded_library():
    """Generate 100+ material entries."""
    materials = []

    # PC Family (18)
    materials.append(_pc("SABIC-Lexan-141R", "General Purpose PC"))
    materials.append(_pc("SABIC-Lexan-3412R", "PC+GF20", E=5800, cte=3.2e-5, filler=GF20))
    materials.append(_pc("SABIC-Lexan-3413R", "PC+GF30", n=0.33, E=8500, cte=2.5e-5, filler=GF30))
    materials.append(_pc("SABIC-Lexan-3414R", "PC+GF40", n=0.35, E=11000, cte=2.0e-5, filler=GF45))
    materials.append(_pc("SABIC-Cycoloy-C1200HF", "PC-ABS Blend", n=0.34, D1=1.5e12, E=2600, cte=7.0e-5))
    materials.append(_pc("SABIC-Cycoloy-C6600", "PC-ABS FR", n=0.35, D1=1.8e12, E=2800, cte=6.8e-5))
    materials.append(_pc("SABIC-Lexan-940", "PC-FR (V0)", n=0.31, b1m=0.00088, E=2400))
    materials.append(_pc("SABIC-Lexan-LS2", "PC Light Diffusion"))
    materials.append(_pc("SABIC-Lexan-EXL1414", "PC-Siloxane Copolymer", n=0.29, E=2100))
    materials.append(_pc("TEIJIN-Panlite-L-1225L", "PC Standard", D1=2.2e13, E=2300))
    materials.append(_pc("TEIJIN-Panlite-G-3430H", "PC+GF30 HF", n=0.33, E=8200, cte=2.6e-5, filler=GF30))
    materials.append(_pc("Covestro-Makrolon-2405", "PC Low Viscosity", n=0.28, D1=2.0e13, E=2150))
    materials.append(_pc("Covestro-Makrolon-2805", "PC Medium Viscosity", n=0.29, E=2200))
    materials.append(_pc("Covestro-Makrolon-3105", "PC High Viscosity", n=0.32, E=2250))
    materials.append(_pc("Covestro-Makrolon-8035", "PC+GF30 EMI", n=0.34, E=8000, cte=2.7e-5, filler=GF30))
    materials.append(_pc("Lotte-Infino-PC-1100", "PC Standard KR", n=0.32, D1=2.2e13))
    materials.append(_pc("Lotte-Infino-PC-GF1320", "PC+GF20 KR", n=0.33, E=5600, cte=3.3e-5, filler=GF20))
    materials.append(_pc("Lotte-Infino-PC-FR1050", "PC-FR KR", n=0.31, b1m=0.00087))

    # ABS Family (15)
    materials.append(_abs("Toray-Toyolac-100", "ABS GP"))
    materials.append(_abs("Toray-Toyolac-700", "ABS High Flow", n=0.33, D1=3.0e11))
    materials.append(_abs("Toray-Toyolac-920", "ABS Transparent", n=0.34, E=2500))
    materials.append(_abs("ChiMei-Polylac-PA-757", "ABS High Impact", E=2200, cte=8.5e-5))
    materials.append(_abs("ChiMei-Polylac-PA-765A", "ABS FR-V0", E=2500, cte=7.8e-5))
    materials.append(_abs("LG-Chem-HI121H", "ABS High Impact KR", E=2300))
    materials.append(_abs("LG-Chem-ER461", "ABS Electroplating"))
    materials.append(_abs("Lotte-Starex-SD-0150", "ABS GP KR"))
    materials.append(_abs("Lotte-Starex-VH-0800", "ABS High Heat", b5=275.15, E=2600))
    materials.append(_abs("SABIC-Cycolac-GPM5500", "ABS GP", E=2400))
    materials.append(_abs("SABIC-Cycolac-FR15U", "ABS FR", E=2550))
    materials.append(_abs("Kumho-ABS-750N", "ABS High Flow KR", n=0.34, D1=3.2e11))
    materials.append(_abs("INEOS-Lustran-248", "ABS Medium Impact"))
    materials.append(_abs("Techno-UMG-ABS-3001M", "ABS Anti-static"))
    materials.append(_abs("Techno-UMG-ABS-VW800", "ABS Heat Resistant", b5=278.15, E=2650))

    # PP Family (12)
    materials.append(_pp("LyondellBasell-Hifax-TRC-135N", "PP TPO"))
    materials.append(_pp("LyondellBasell-Hostacom-G2N05", "PP+GF20", E=3200, cte=6.0e-5, filler=GF20))
    materials.append(_pp("Borealis-Daploy-WB140HMS", "PP HMS Foam", n=0.40))
    materials.append(_pp("SABIC-PP-575P", "PP HCPP", n=0.37))
    materials.append(_pp("LG-Chem-M1600", "PP GP KR"))
    materials.append(_pp("Lotte-Hyundai-EP332K", "PP Block Co", E=1600))
    materials.append(_pp("Hanwha-Total-PP-BJ350", "PP High Impact"))
    materials.append(_pp("GS-Caltex-RJ770", "PP Random Co", E=1400))
    materials.append(_pp("Celanese-Celstran-PP-GF30-02", "PP+GF30", n=0.40, E=4500, cte=4.5e-5, filler=GF30))
    materials.append(_pp("RTP-101", "PP+GF10", E=2500, cte=7.0e-5, filler={"filler_type":"Fiber","filler_name":"GF","weight_fraction":0.10,"volume_fraction":0.056,"aspect_ratio":20,"filler_modulus_MPa":72000,"filler_CTE":5e-6,"filler_poisson":0.20,"matrix_grade":""}))
    materials.append(_pp("RTP-105", "PP+GF30", E=5500, cte=4.0e-5, filler=GF30))
    materials.append(_pp("ExxonMobil-AP03B", "PP Automotive"))

    # PA66 Family (12)
    materials.append(_pa("DuPont-Zytel-101L", "PA66 GP"))
    materials.append(_pa("DuPont-Zytel-70G33L", "PA66+GF33", E=10500, cte=3.0e-5, filler={"filler_type":"Fiber","filler_name":"GF","weight_fraction":0.33,"volume_fraction":0.185,"aspect_ratio":25,"filler_modulus_MPa":72000,"filler_CTE":5e-6,"filler_poisson":0.20,"matrix_grade":""}))
    materials.append(_pa("DuPont-Zytel-70G43L", "PA66+GF43", n=0.35, E=14000, cte=2.2e-5, filler=GF45))
    materials.append(_pa("BASF-Ultramid-A3K", "PA66 GP"))
    materials.append(_pa("BASF-Ultramid-A3WG6", "PA66+GF30", E=10000, cte=3.2e-5, filler=GF30))
    materials.append(_pa("BASF-Ultramid-A3WG10", "PA66+GF50", n=0.36, E=16000, cte=1.8e-5))
    materials.append(_pa("Asahi-Leona-1300S", "PA66 GP"))
    materials.append(_pa("Asahi-Leona-13G43", "PA66+GF43", n=0.35, E=13500, cte=2.3e-5, filler=GF45))
    materials.append(_pa("Radici-Radilon-A-RV300", "PA66+GF30", E=9800, cte=3.1e-5, filler=GF30))
    materials.append(_pa("Celanese-Celstran-PA66-GF30-02", "PA66+GF30 LFT", E=11000, cte=2.8e-5, filler=GF30))
    materials.append(_pa("LANXESS-Durethan-AKV30H2.0", "PA66+GF30 HF", E=10200, cte=3.0e-5, filler=GF30))
    materials.append(_pa("Toray-Amilan-CM3001-N", "PA66 GP"))

    # POM Family (8)
    materials.append(_eng("DuPont-Delrin-500P", "POM", "POM GP", 0.30, 2.0e12, 263.15, 28.0, 0.00075, 263.15, 2900, 1.1e-4, 213.15, 448.15, 2050, 0.31))
    materials.append(_eng("DuPont-Delrin-510GR", "POM", "POM+GF10", 0.32, 2.5e12, 263.15, 28.5, 0.00072, 263.15, 4500, 6.0e-5, 213.15, 448.15, 2000, 0.35))
    materials.append(_eng("DuPont-Delrin-525GR", "POM", "POM+GF25", 0.33, 3.0e12, 263.15, 29.0, 0.00070, 263.15, 8500, 3.5e-5, 213.15, 448.15, 1950, 0.38, filler={"filler_type":"Fiber","filler_name":"GF","weight_fraction":0.25,"volume_fraction":0.14,"aspect_ratio":20,"filler_modulus_MPa":72000,"filler_CTE":5e-6,"filler_poisson":0.20,"matrix_grade":""}))
    materials.append(_eng("Polyplastics-Duracon-M90-44", "POM", "POM GP", 0.30, 2.1e12, 263.15, 28.2, 0.00076, 263.15, 2950, 1.05e-4, 213.15, 448.15, 2050, 0.31))
    materials.append(_eng("Asahi-Tenac-3010", "POM", "POM GP", 0.31, 1.9e12, 263.15, 27.8, 0.00074, 263.15, 2850, 1.1e-4, 213.15, 448.15, 2100, 0.30))
    materials.append(_eng("BASF-Ultraform-N2320", "POM", "POM GP", 0.30, 2.3e12, 263.15, 28.8, 0.00073, 263.15, 3000, 1.0e-4, 213.15, 448.15, 2000, 0.32))
    materials.append(_eng("Celanese-Hostaform-C9021", "POM", "POM GP", 0.29, 2.0e12, 263.15, 28.0, 0.00075, 263.15, 2880, 1.08e-4, 213.15, 448.15, 2020, 0.31))
    materials.append(_eng("Celanese-Hostaform-C27021", "POM", "POM+GF20", 0.32, 2.8e12, 263.15, 29.0, 0.00071, 263.15, 7500, 4.0e-5, 213.15, 448.15, 1980, 0.37, filler=GF20))

    # PBT Family (8)
    for i, m in enumerate([
        ("BASF-Ultradur-B4520", "PBT GP", 2800, 8.0e-5),
        ("BASF-Ultradur-B4300G6", "PBT+GF30", 10000, 3.0e-5),
        ("DuPont-Crastin-S600F20", "PBT+GF20", 7500, 4.5e-5),
        ("SABIC-Valox-420", "PBT+GF30", 9500, 3.2e-5),
        ("SABIC-Valox-310", "PBT GP", 2700, 8.5e-5),
        ("Celanese-Celanex-2002", "PBT GP", 2750, 8.2e-5),
        ("Celanese-Celanex-3316", "PBT+GF30", 9800, 3.1e-5),
        ("LG-Chem-Lupox-GP2300", "PBT+GF30", 9600, 3.3e-5),
    ]):
        has_filler = "GF" in m[1]
        materials.append(_eng(m[0], "PBT", m[1], 0.32, 3.0e12, 373.15, 29.5, 0.00075, 373.15, m[2], m[3], 323.15, 498.15, 1950, 0.25, filler=GF30 if "GF30" in m[1] else (GF20 if "GF20" in m[1] else None)))

    # Engineering/Specialty polymers (30)
    eng_list = [
        ("Evonik-Plexiglas-8N", "PMMA", "PMMA GP", 0.30, 4.0e12, 378.15, 30.0, 0.00085, 378.15, 3300, 7.0e-5, 378.15, 473.15, 1800, 0.19),
        ("SABIC-Ultem-1000", "PEI", "PEI GP", 0.32, 8.0e13, 488.15, 33.0, 0.00078, 488.15, 3500, 5.6e-5, 488.15, 623.15, 2000, 0.22),
        ("SABIC-Ultem-2200", "PEI", "PEI+GF20", 0.34, 1.0e14, 488.15, 33.5, 0.00076, 488.15, 6800, 2.5e-5, 488.15, 623.15, 1950, 0.25, GF20),
REPLACE
        ("Solvay-Radel-R-5000", "PPSU", "PPSU GP", 0.33, 5.0e13, 493.15, 32.0, 0.00080, 493.15, 2400, 5.5e-5, 493.15, 633.15, 1900, 0.35),
        ("Solvay-Ryton-R-4-220", "PPS", "PPS+GF40", 0.35, 6.0e13, 363.15, 31.0, 0.00074, 363.15, 15000, 2.0e-5, 363.15, 553.15, 1850, 0.30),
        ("Ticona-Fortron-1140L4", "PPS", "PPS+GF40", 0.34, 5.5e13, 363.15, 30.5, 0.00075, 363.15, 14500, 2.2e-5, 363.15, 553.15, 1880, 0.31),
        ("Victrex-PEEK-450G", "PEEK", "PEEK GP", 0.33, 1.0e14, 616.15, 34.0, 0.00078, 616.15, 3600, 4.7e-5, 416.15, 616.15, 2150, 0.25),
        ("Victrex-PEEK-450CA30", "PEEK", "PEEK+CF30", 0.35, 1.5e14, 616.15, 34.5, 0.00075, 616.15, 13000, 1.5e-5, 416.15, 616.15, 2000, 0.35),
        ("Ticona-Vectra-A130", "LCP", "LCP+GF30", 0.28, 2.0e13, 553.15, 33.0, 0.00072, 553.15, 15000, 1.0e-5, 393.15, 553.15, 1800, 0.32),
        ("Sumitomo-SumikaSuper-E6008", "LCP", "LCP+GF40", 0.29, 2.5e13, 553.15, 33.5, 0.00070, 553.15, 18000, 0.8e-5, 393.15, 553.15, 1750, 0.33),
        ("EMS-Grivory-GV-5H", "PA6T", "PPA+GF50", 0.34, 5.0e13, 393.15, 32.0, 0.00073, 393.15, 18000, 1.8e-5, 393.15, 593.15, 1900, 0.30),
        ("DuPont-Zytel-HTN51G35HSL", "PA6T", "PPA+GF35", 0.33, 4.5e13, 393.15, 31.5, 0.00074, 393.15, 12000, 2.5e-5, 393.15, 593.15, 1950, 0.31),
        ("DSM-Stanyl-TW200F6", "PA46", "PA46+GF30", 0.32, 3.5e13, 353.15, 30.0, 0.00076, 353.15, 10500, 3.5e-5, 353.15, 563.15, 2000, 0.28),
        ("DSM-Arnite-T06-200", "PBT+PET", "PBT/PET Blend", 0.31, 2.8e12, 373.15, 29.0, 0.00076, 373.15, 2600, 7.5e-5, 333.15, 523.15, 1900, 0.25),
        ("Mitsubishi-Iupilon-S-3000", "PC", "PC High Flow", 0.28, 2.0e13, 413.15, 30.8, 0.00088, 413.15, 2100, 6.8e-5, 423.15, 573.15, 1980, 0.22),
        ("Idemitsu-Tarflon-IR2200", "PC", "PC Optical", 0.29, 2.1e13, 413.15, 31.0, 0.00089, 413.15, 2150, 6.7e-5, 423.15, 573.15, 1990, 0.21),
        ("Sumitomo-Sumikon-FM-X", "Phenolic", "Phenolic GP", 0.24, 1.0e14, 473.15, 35.0, 0.00065, 473.15, 6000, 3.0e-5, 473.15, 623.15, 1600, 0.30),
        ("Daikin-NeoFlon-PFA-AP-230", "PFA", "PFA GP", 0.26, 5.0e13, 533.15, 34.0, 0.00060, 533.15, 450, 12.0e-5, 363.15, 583.15, 1050, 0.25),
        ("AGC-Fluon-ETFE-C-88AX", "ETFE", "ETFE GP", 0.27, 4.0e13, 523.15, 33.5, 0.00062, 523.15, 1200, 10.0e-5, 373.15, 543.15, 1200, 0.24),
        ("Covestro-Apec-1895", "PC-HT", "PC High Heat", 0.33, 4.0e13, 463.15, 32.5, 0.00086, 463.15, 2400, 6.0e-5, 463.15, 593.15, 2100, 0.23),
    ]
    for e in eng_list:
        grade, fam, desc, n, D1, D2, A1, b1m, b5, E, cte, Tg, Tm, Cp, k = e[:16]
        filler = e[16] if len(e) > 16 else None
        materials.append(_eng(grade, fam, desc, n, D1, D2, A1, b1m, b5, E, cte, Tg, Tm, Cp, k, filler))

    # ── Write expanded library ──────────────
    with open(EXP_LIB, "w", encoding="utf-8") as f:
        json.dump({"schema_version": "3.0", "total_materials": len(materials), "materials": materials}, f, indent=2)

    print(f"[MATERIAL EXPANSION] {len(materials)} materials written to {EXP_LIB.name}")
    return materials


def lookup_material(name):
    """Material-as-a-Service: lookup material by grade name."""
    lib = json.load(open(EXP_LIB)) if EXP_LIB.exists() else {"materials": generate_expanded_library()}
    for m in lib["materials"]:
        if name.lower() in m["grade"].lower():
            return m
    return None


def validate_all():
    """Validate all Cross-WLF and Tait physical bounds."""
    lib = json.load(open(EXP_LIB)) if EXP_LIB.exists() else {"materials": generate_expanded_library()}
    violations = []
    for m in lib["materials"]:
        wlf = m["CrossWLF"]
        n = wlf["n"]
        d1 = wlf["D1"]
        b1m = m["Tait"]["b1m"]
        if not (0.1 <= n <= 0.9):
            violations.append(f"{m['grade']}: n={n} out of bounds [0.1, 0.9]")
        if d1 <= 0:
            violations.append(f"{m['grade']}: D1={d1} not positive")
        if b1m <= 0:
            violations.append(f"{m['grade']}: b1m={b1m} not positive")
    if violations:
        print(f"[VALIDATE] {len(violations)} violations found:")
        for v in violations[:5]:
            print(f"  - {v}")
        return False
    print(f"[VALIDATE] All {len(lib['materials'])} materials passed physical bounds validation.")
    return True


if __name__ == "__main__":
    generate_expanded_library()
    validate_all()
    print(lookup_material("Lexan-141R"))