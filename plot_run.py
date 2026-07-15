import sqlite3
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from config import DB_NAME, RUN_NAME, PLOT_DIR, TANK_MAPPING, ESP32_MAPPING

OUTPUT_DIR = Path(PLOT_DIR)
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

if esp32.empty:
    raise ValueError(f"No ESP32 data found for run_name={RUN_NAME}")

if arduino.empty:
    print(f"Warning: no Arduino data found for run_name={RUN_NAME}")

# -------------------------------
# Convert Arduino timestamps safely.
# Some older rows may use slightly different timestamp formats.
# format="mixed" makes parsing robust across old and new runs.
# -------------------------------
if not arduino.empty:
    arduino["timestamp_dt"] = pd.to_datetime(
        arduino["timestamp"],
        errors="coerce",
        format="mixed"
    )

    bad_timestamps = arduino["timestamp_dt"].isna().sum()

    if bad_timestamps > 0:
        print(f"Warning: {bad_timestamps} Arduino rows had invalid timestamps and were dropped.")

    arduino = arduino.dropna(subset=["timestamp_dt"]).copy()

    if not arduino.empty:
        arduino["t_seconds"] = (
            arduino["timestamp_dt"] - arduino["timestamp_dt"].iloc[0]
        ).dt.total_seconds()
    else:
        print(f"Warning: all Arduino timestamps failed to parse for run_name={RUN_NAME}")

# -------------------------------
# Plot 1: ESP32 flow timeline
# -------------------------------
plt.figure(figsize=(10, 5))
plt.plot(esp32["timestamp"], esp32["flow_p1"], label=ESP32_MAPPING["flow_p1"])
plt.plot(esp32["timestamp"], esp32["flow_p2"], label=ESP32_MAPPING["flow_p2"])
plt.plot(esp32["timestamp"], esp32["flow_valve1"], label=ESP32_MAPPING["flow_valve1"])
plt.plot(esp32["timestamp"], esp32["flow_outlet"], label=ESP32_MAPPING["flow_outlet"])
plt.xlabel("Time during MATLAB run (s)")
plt.ylabel("Flow reading")
plt.title(f"Flow Timeline - {RUN_NAME}")
plt.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIR / f"{RUN_NAME}_flow_timeline.png", dpi=200)
plt.close()

# -------------------------------
# Plot 2: Pump command timeline
# -------------------------------
plt.figure(figsize=(10, 5))
plt.plot(esp32["timestamp"], esp32["pump1_pwm"], label=ESP32_MAPPING["pump1_pwm"])
plt.plot(esp32["timestamp"], esp32["pump2_pwm"], label=ESP32_MAPPING["pump2_pwm"])
plt.xlabel("Time during MATLAB run (s)")
plt.ylabel("Pump command / PWM")
plt.title(f"Pump Command Timeline - {RUN_NAME}")
plt.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIR / f"{RUN_NAME}_pump_timeline.png", dpi=200)
plt.close()

# -------------------------------
# Plot 3: Valve state timeline
# -------------------------------
plt.figure(figsize=(10, 5))
plt.plot(esp32["timestamp"], esp32["valve1"], label=ESP32_MAPPING["valve1"])
plt.plot(esp32["timestamp"], esp32["valve2"], label=ESP32_MAPPING["valve2"])
plt.plot(esp32["timestamp"], esp32["valve3"], label=ESP32_MAPPING["valve3"])
plt.plot(esp32["timestamp"], esp32["valve4"], label=ESP32_MAPPING["valve4"])
plt.xlabel("Time during MATLAB run (s)")
plt.ylabel("Valve state")
plt.title(f"Valve State Timeline - {RUN_NAME}")
plt.legend()
plt.tight_layout()
plt.savefig(OUTPUT_DIR / f"{RUN_NAME}_valve_timeline.png", dpi=200)
plt.close()

# -------------------------------
# Plot 4: Arduino tank sensor timeline
# -------------------------------
if not arduino.empty and "t_seconds" in arduino.columns:
    plt.figure(figsize=(10, 5))
    plt.plot(arduino["t_seconds"], arduino["tank1"], label=TANK_MAPPING["tank1"])
    plt.plot(arduino["t_seconds"], arduino["tank2"], label=TANK_MAPPING["tank2"])
    plt.plot(arduino["t_seconds"], arduino["tank3"], label=TANK_MAPPING["tank3"])
    plt.xlabel("Time during Arduino logging (s)")
    plt.ylabel("Ultrasonic sensor reading")
    plt.title(f"Arduino Tank Sensor Timeline - {RUN_NAME}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"{RUN_NAME}_tank_timeline.png", dpi=200)
    plt.close()

print("Saved plots to plots/ folder:")
print(f"- plots/{RUN_NAME}_flow_timeline.png")
print(f"- plots/{RUN_NAME}_pump_timeline.png")
print(f"- plots/{RUN_NAME}_valve_timeline.png")

if not arduino.empty and "t_seconds" in arduino.columns:
    print(f"- plots/{RUN_NAME}_tank_timeline.png")