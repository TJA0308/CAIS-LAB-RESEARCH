import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_NAME, RUN_NAME, ANALYSIS_DIR

OUTPUT_DIR = Path(ANALYSIS_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_NAME)

esp32 = pd.read_sql_query(
    """
    SELECT *
    FROM esp32_matlab_data
    WHERE run_name = ?
    ORDER BY timestamp
    """,
    conn,
    params=(RUN_NAME,)
)

arduino = pd.read_sql_query(
    """
    SELECT *
    FROM arduino_tank_data
    WHERE run_name = ?
    ORDER BY timestamp
    """,
    conn,
    params=(RUN_NAME,)
)

conn.close()

print(f"Running anomaly detection for run_name={RUN_NAME}")
print(f"ESP32 rows: {len(esp32)}")
print(f"Arduino rows: {len(arduino)}")

anomalies = []

# -------------------------------
# ESP32/MATLAB anomaly rules
# -------------------------------

if not esp32.empty:
    # Rule 1: Pump 1 command high but Pump 1 recorded channel is low
    pump1_low_flow = esp32[
        (esp32["pump1_pwm"] >= 50) &
        (esp32["flow_p1"] <= 0.5)
    ]

    for _, row in pump1_low_flow.iterrows():
        anomalies.append({
            "run_name": RUN_NAME,
            "source": "esp32",
            "timestamp": row["timestamp"],
            "rule": "pump1_on_low_flow",
            "details": f"pump1_pwm={row['pump1_pwm']}, flow_p1={row['flow_p1']}"
        })

    # Rule 2: Pump 2 command high but Pump 2 recorded channel is low
    pump2_low_flow = esp32[
        (esp32["pump2_pwm"] >= 50) &
        (esp32["flow_p2"] <= 0.5)
    ]

    for _, row in pump2_low_flow.iterrows():
        anomalies.append({
            "run_name": RUN_NAME,
            "source": "esp32",
            "timestamp": row["timestamp"],
            "rule": "pump2_on_low_flow",
            "details": f"pump2_pwm={row['pump2_pwm']}, flow_p2={row['flow_p2']}"
        })

    # Rule 3: Flow still present when both pump commands are off
    flow_after_pumps_off = esp32[
        (esp32["pump1_pwm"] == 0) &
        (esp32["pump2_pwm"] == 0) &
        (
            (esp32["flow_p1"] > 0.5) |
            (esp32["flow_p2"] > 0.5) |
            (esp32["flow_valve1"] > 0.5) |
            (esp32["flow_outlet"] > 0.5)
        )
    ]

    for _, row in flow_after_pumps_off.iterrows():
        anomalies.append({
            "run_name": RUN_NAME,
            "source": "esp32",
            "timestamp": row["timestamp"],
            "rule": "flow_after_pumps_off",
            "details": (
                f"flow_p1={row['flow_p1']}, flow_p2={row['flow_p2']}, "
                f"flow_valve1={row['flow_valve1']}, flow_outlet={row['flow_outlet']}"
            )
        })

# -------------------------------
# Arduino data-quality rules
# -------------------------------

if not arduino.empty:
    # Rule 4: Sensor error / missing value
    missing_sensor = arduino[
        arduino[["tank1", "tank2", "tank3"]].isna().any(axis=1)
    ]

    for _, row in missing_sensor.iterrows():
        anomalies.append({
            "run_name": RUN_NAME,
            "source": "arduino",
            "timestamp": row["timestamp"],
            "rule": "sensor_error_or_missing",
            "details": f"raw_line={row['raw_line']}"
        })

    # Rule 5: Possible stuck sensor stream
    arduino["same_as_previous"] = arduino["raw_line"] == arduino["raw_line"].shift(1)

    stuck_count = 0
    for _, row in arduino.iterrows():
        if row["same_as_previous"]:
            stuck_count += 1
        else:
            stuck_count = 0

        if stuck_count == 10:
            anomalies.append({
                "run_name": RUN_NAME,
                "source": "arduino",
                "timestamp": row["timestamp"],
                "rule": "possible_sensor_stuck",
                "details": f"same raw_line repeated >=10 times: {row['raw_line']}"
            })

# Always create the report file, even if empty
columns = ["run_name", "source", "timestamp", "rule", "details"]
anomaly_df = pd.DataFrame(anomalies, columns=columns)

output_file = OUTPUT_DIR / f"{RUN_NAME}_anomaly_report.csv"
anomaly_df.to_csv(output_file, index=False)

print(f"\nSaved anomaly report to {output_file}")

print("\nAnomaly counts:")
if anomaly_df.empty:
    print("No anomalies detected.")
else:
    print(anomaly_df["rule"].value_counts())

print("\nFirst 10 anomalies:")
print(anomaly_df.head(10))
