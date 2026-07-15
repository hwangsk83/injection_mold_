# material_db.py - Real Material Property Database for Injection Molding Simulation

MATERIAL_DB = {
    "ABS": {
        "CrossWLF": {
            "n": 0.35,
            "tau_star": 2.8e5,
            "D1": 3.8e11,
            "D2": 263.15,
            "D3": 0.0,
            "A1": 28.5,
            "A2": 51.6
        },
        "Tait": {
            "b1m": 0.001,
            "b2m": 1.0e-6,
            "b3m": 1.2e8,
            "b4m": 0.004,
            "b5": 263.15,
            "C_tait": 0.0894
        },
        "Thermal": {
            "Cp_poly": 2100.0,
            "k_poly": 0.18,
            "Tg": 378.15  # Glass Transition Temperature (K)
        }
    },
    "PC": {
        "CrossWLF": {
            "n": 0.30,
            "tau_star": 1.8e5,
            "D1": 2.4e13,
            "D2": 413.15,
            "D3": 0.0,
            "A1": 31.2,
            "A2": 51.6
        },
        "Tait": {
            "b1m": 0.0009,
            "b2m": 1.2e-6,
            "b3m": 1.3e8,
            "b4m": 0.0035,
            "b5": 413.15,
            "C_tait": 0.0894
        },
        "Thermal": {
            "Cp_poly": 2000.0,
            "k_poly": 0.20,
            "Tg": 423.15  # Glass Transition Temperature (K)
        }
    }
}
