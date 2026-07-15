# config.py
# Shared settings for the water treatment testbed database pipeline

from pathlib import Path

DATA_DIR = Path("data")
RAW_DATA_DIR = DATA_DIR / "raw"
DB_DIR = DATA_DIR / "db"

# -------------------------------
# Database
# -------------------------------
DB_NAME = str(DB_DIR / "water_testbed.db")

# -------------------------------
# Current experiment/run
# Change these two lines before every new run
# -------------------------------
RUN_NAME = "pump_pwm_sweep_run_001"
MAT_FILE = str(RAW_DATA_DIR / "pump_pwm_sweep_run_001.mat")  # change if needed

# -------------------------------
# Arduino UNO serial settings
# -------------------------------
SERIAL_PORT = "COM6"
BAUD_RATE = 57600

# -------------------------------
# Confirmed Arduino tank sensor mapping
# Raw database columns stay tank1/tank2/tank3.
# Plots/reports should display these readable names.
# -------------------------------
TANK_MAPPING = {
    "tank1": "tower",
    "tank2": "treated",
    "tank3": "raw",
}

# -------------------------------
# ESP32/MATLAB channel labels
# These are for plots/reports/readability.
# Raw database columns stay the same.
# -------------------------------
ESP32_MAPPING = {
    "flow_p1": "Pump 1 flow",
    "flow_p2": "Pump 2 flow",
    "flow_valve1": "Valve 1 flow",
    "flow_outlet": "Outlet flow",
    "pump1_pwm": "Pump 1 command",
    "pump2_pwm": "Pump 2 command",
    "valve1": "Valve 1 state",
    "valve2": "Valve 2 state",
    "valve3": "Valve 3 state",
    "valve4": "Valve 4 state",
}

# -------------------------------
# Output folders
# -------------------------------
EXPORT_DIR = "exports"
PLOT_DIR = "plots"
ANALYSIS_DIR = "analysis"
