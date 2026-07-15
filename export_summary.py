import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_NAME, EXPORT_DIR

OUTPUT_DIR = Path(EXPORT_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_NAME)

esp32 = pd.read_sql_query("SELECT * FROM esp32_matlab_data", conn)
arduino = pd.read_sql_query("SELECT * FROM arduino_tank_data", conn)

esp32_summary = pd.read_sql_query("""
SELECT
    run_name,
    COUNT(*) AS rows,
    MAX(flow_p1) AS max_flow_p1,
    MAX(flow_p2) AS max_flow_p2,
    MAX(flow_valve1) AS max_flow_valve1,
    MAX(flow_outlet) AS max_flow_outlet,
    AVG(flow_p1) AS avg_flow_p1,
    AVG(flow_p2) AS avg_flow_p2,
    AVG(flow_valve1) AS avg_flow_valve1,
    AVG(flow_outlet) AS avg_flow_outlet,
    MAX(pump1_pwm) AS max_pump1_pwm,
    MAX(pump2_pwm) AS max_pump2_pwm
FROM esp32_matlab_data
GROUP BY run_name
""", conn)

arduino_summary = pd.read_sql_query("""
SELECT
run_name,
    COUNT(*) AS rows,
    AVG(tank1) AS avg_tank1,
    AVG(tank2) AS avg_tank2,
    AVG(tank3) AS avg_tank3,
    MIN(tank1) AS min_tank1,
    MIN(tank2) AS min_tank2,
    MIN(tank3) AS min_tank3,
    MAX(tank1) AS max_tank1,
    MAX(tank2) AS max_tank2,
    MAX(tank3) AS max_tank3
FROM arduino_tank_data
GROUP BY run_name
""", conn)

# Same data with readable tank labels for sharing/poster use.
arduino_mapped_summary = arduino_summary.rename(columns={
    "avg_tank1": "avg_tower",
    "avg_tank2": "avg_treated",
    "avg_tank3": "avg_raw",
    "min_tank1": "min_tower",
    "min_tank2": "min_treated",
    "min_tank3": "min_raw",
    "max_tank1": "max_tower",
    "max_tank2": "max_treated",
    "max_tank3": "max_raw",
})

esp32.to_csv(OUTPUT_DIR / "esp32_matlab_data.csv", index=False)
arduino.to_csv(OUTPUT_DIR / "arduino_tank_data.csv", index=False)
esp32_summary.to_csv(OUTPUT_DIR / "esp32_summary_by_run.csv", index=False)
arduino_summary.to_csv(OUTPUT_DIR / "arduino_summary_by_run.csv", index=False)
arduino_mapped_summary.to_csv(OUTPUT_DIR / "arduino_summary_mapped_by_run.csv", index=False)

print("Exported files to exports/")
print("\nESP32 summary:")
print(esp32_summary)

print("\nArduino summary:")
print(arduino_summary)

print("\nArduino mapped summary:")
print(arduino_mapped_summary)

conn.close()
