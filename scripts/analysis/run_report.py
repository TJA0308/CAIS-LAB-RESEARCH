import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_NAME, RUN_NAME, ANALYSIS_DIR, TANK_MAPPING

OUTPUT_DIR = Path(ANALYSIS_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_NAME)

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
WHERE run_name = ?
GROUP BY run_name
""", conn, params=(RUN_NAME,))

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
WHERE run_name = ?
GROUP BY run_name
""", conn, params=(RUN_NAME,))

conn.close()

anomaly_file = OUTPUT_DIR / f"{RUN_NAME}_anomaly_summary.csv"

if anomaly_file.exists():
    anomaly_summary = pd.read_csv(anomaly_file)
else:
    anomaly_summary = pd.DataFrame(columns=["rule", "source", "count"])

report_path = OUTPUT_DIR / f"{RUN_NAME}_run_report.txt"

with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"Run Report: {RUN_NAME}\n")
    f.write("=" * 40 + "\n\n")

    f.write("ESP32/MATLAB Summary\n")
    f.write("-" * 25 + "\n")
    if esp32_summary.empty:
        f.write("No ESP32/MATLAB data found.\n\n")
    else:
        row = esp32_summary.iloc[0]
        f.write(f"Rows: {int(row['rows'])}\n")
        f.write(f"Max Pump 1 PWM: {row['max_pump1_pwm']}\n")
        f.write(f"Max Pump 2 PWM: {row['max_pump2_pwm']}\n")
        f.write(f"Max Flow Pump 1: {row['max_flow_p1']}\n")
        f.write(f"Max Flow Pump 2: {row['max_flow_p2']}\n")
        f.write(f"Max Flow Valve 1: {row['max_flow_valve1']}\n")
        f.write(f"Max Flow Outlet: {row['max_flow_outlet']}\n\n")

    f.write("Arduino Tank Sensor Summary\n")
    f.write("-" * 30 + "\n")
    if arduino_summary.empty:
        f.write("No Arduino data found.\n\n")
    else:
        row = arduino_summary.iloc[0]
        f.write(f"Rows: {int(row['rows'])}\n")
        f.write(
            f"{TANK_MAPPING['tank1'].title()} tank sensor min/max/avg: "
            f"{row['min_tank1']} / {row['max_tank1']} / {row['avg_tank1']:.2f}\n"
        )
        f.write(
            f"{TANK_MAPPING['tank2'].title()} tank sensor min/max/avg: "
            f"{row['min_tank2']} / {row['max_tank2']} / {row['avg_tank2']:.2f}\n"
        )
        f.write(
            f"{TANK_MAPPING['tank3'].title()} tank sensor min/max/avg: "
            f"{row['min_tank3']} / {row['max_tank3']} / {row['avg_tank3']:.2f}\n\n"
        )

    f.write("Anomaly/Data-Quality Summary\n")
    f.write("-" * 32 + "\n")
    if anomaly_summary.empty:
        f.write("No anomalies found or anomaly summary not generated.\n")
    else:
        for _, row in anomaly_summary.iterrows():
            percent_text = ""
            if "percent_of_source_rows" in anomaly_summary.columns:
                percent_text = f" ({row['percent_of_source_rows']}% of {row['source']} rows)"
            f.write(f"{row['rule']} ({row['source']}): {int(row['count'])}{percent_text}\n")

print(f"Saved run report to {report_path}")
