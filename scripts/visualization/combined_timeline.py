import sqlite3
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

from config import DB_NAME, RUN_NAME, PLOT_DIR, ESP32_MAPPING

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

conn.close()

if esp32.empty:
    raise ValueError(f"No ESP32/MATLAB data found for run_name={RUN_NAME}")

output_file = OUTPUT_DIR / f"{RUN_NAME}_combined_timeline.png"

fig, axes = plt.subplots(
    nrows=3,
    ncols=1,
    figsize=(12, 9),
    sharex=True
)

fig.suptitle(
    f"Full-Cycle System Timeline - {RUN_NAME}",
    fontsize=16
)

# -------------------------------------------------
# Panel 1: Pump commands
# -------------------------------------------------
axes[0].plot(
    esp32["timestamp"],
    esp32["pump1_pwm"],
    label=ESP32_MAPPING.get("pump1_pwm", "Pump 1 command")
)
axes[0].plot(
    esp32["timestamp"],
    esp32["pump2_pwm"],
    label=ESP32_MAPPING.get("pump2_pwm", "Pump 2 command")
)

axes[0].set_ylabel("Pump PWM")
axes[0].set_title("Pump Commands")
axes[0].legend(loc="upper right")
axes[0].grid(True, alpha=0.3)

# -------------------------------------------------
# Panel 2: Valve states
# -------------------------------------------------
axes[1].plot(
    esp32["timestamp"],
    esp32["valve1"],
    label=ESP32_MAPPING.get("valve1", "Valve 1")
)
axes[1].plot(
    esp32["timestamp"],
    esp32["valve2"],
    label=ESP32_MAPPING.get("valve2", "Valve 2")
)
axes[1].plot(
    esp32["timestamp"],
    esp32["valve3"],
    label=ESP32_MAPPING.get("valve3", "Valve 3")
)
axes[1].plot(
    esp32["timestamp"],
    esp32["valve4"],
    label=ESP32_MAPPING.get("valve4", "Valve 4")
)

axes[1].set_ylabel("Valve State")
axes[1].set_title("Valve States")
axes[1].set_yticks([0, 1])
axes[1].legend(loc="upper right")
axes[1].grid(True, alpha=0.3)

# -------------------------------------------------
# Panel 3: Flow response
# -------------------------------------------------
axes[2].plot(
    esp32["timestamp"],
    esp32["flow_p1"],
    label=ESP32_MAPPING.get("flow_p1", "Pump 1 channel")
)
axes[2].plot(
    esp32["timestamp"],
    esp32["flow_p2"],
    label=ESP32_MAPPING.get("flow_p2", "Pump 2 channel")
)
axes[2].plot(
    esp32["timestamp"],
    esp32["flow_valve1"],
    label=ESP32_MAPPING.get("flow_valve1", "Valve 1 channel")
)
axes[2].plot(
    esp32["timestamp"],
    esp32["flow_outlet"],
    label=ESP32_MAPPING.get("flow_outlet", "Outlet channel")
)

axes[2].set_xlabel("Time during MATLAB run (s)")
axes[2].set_ylabel("Flow Reading")
axes[2].set_title("Controller-Side Channel Readings")
axes[2].legend(loc="upper right")
axes[2].grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig(output_file, dpi=300)
plt.close()

print(f"Saved combined timeline to {output_file}")
