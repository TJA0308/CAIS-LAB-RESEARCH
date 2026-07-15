import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_NAME, ANALYSIS_DIR, TANK_MAPPING

OUTPUT_DIR = Path(ANALYSIS_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

# -------------------------------------------------
# Choose which runs to include in the poster summary
# Edit this list as you collect more clean runs.
# -------------------------------------------------
POSTER_RUNS = [
    "full_cycle_run_001",
    "full_cycle_run_002",
    "full_cycle_run_003",
    "pump_pwm_sweep_run_001",
    "valve_routing_run_001",
]

# Optional: include validation/debug runs if needed
INCLUDE_ONLY_POSTER_RUNS = True


def read_table(conn, query, params=None):
    return pd.read_sql_query(query, conn, params=params or ())


def safe_divide(num, den):
    if den == 0 or pd.isna(den):
        return 0.0
    return round((num / den) * 100, 2)


conn = sqlite3.connect(DB_NAME)

esp32 = read_table(conn, "SELECT * FROM esp32_matlab_data")
arduino = read_table(conn, "SELECT * FROM arduino_tank_data")
runs = read_table(conn, "SELECT * FROM runs")

conn.close()

if INCLUDE_ONLY_POSTER_RUNS:
    esp32 = esp32[esp32["run_name"].isin(POSTER_RUNS)]
    arduino = arduino[arduino["run_name"].isin(POSTER_RUNS)]
    runs = runs[runs["run_name"].isin(POSTER_RUNS)]

all_run_names = sorted(
    set(esp32["run_name"].dropna().unique()).union(
        set(arduino["run_name"].dropna().unique())
    )
)

summary_rows = []

for run_name in all_run_names:
    esp_run = esp32[esp32["run_name"] == run_name].copy()
    ard_run = arduino[arduino["run_name"] == run_name].copy()

    esp_rows = len(esp_run)
    ard_rows = len(ard_run)

    # -----------------------------
    # ESP32/MATLAB metrics
    # -----------------------------
    if esp_rows > 0:
        max_pump1_pwm = esp_run["pump1_pwm"].max()
        max_pump2_pwm = esp_run["pump2_pwm"].max()

        max_flow_p1 = esp_run["flow_p1"].max()
        max_flow_p2 = esp_run["flow_p2"].max()
        max_flow_valve1 = esp_run["flow_valve1"].max()
        max_flow_outlet = esp_run["flow_outlet"].max()

        avg_flow_p1 = esp_run["flow_p1"].mean()
        avg_flow_p2 = esp_run["flow_p2"].mean()
        avg_flow_valve1 = esp_run["flow_valve1"].mean()
        avg_flow_outlet = esp_run["flow_outlet"].mean()

        valve1_on_percent = safe_divide((esp_run["valve1"] == 1).sum(), esp_rows)
        valve2_on_percent = safe_divide((esp_run["valve2"] == 1).sum(), esp_rows)
        valve3_on_percent = safe_divide((esp_run["valve3"] == 1).sum(), esp_rows)
        valve4_on_percent = safe_divide((esp_run["valve4"] == 1).sum(), esp_rows)

        pump1_on_rows = esp_run[esp_run["pump1_pwm"] > 0]
        pump2_on_rows = esp_run[esp_run["pump2_pwm"] > 0]

        pump1_on_percent = safe_divide(len(pump1_on_rows), esp_rows)
        pump2_on_percent = safe_divide(len(pump2_on_rows), esp_rows)

        # Candidate residual-flow behavior
        flow_after_pumps_off = esp_run[
            (esp_run["pump1_pwm"] == 0)
            & (esp_run["pump2_pwm"] == 0)
            & (
                (esp_run["flow_p1"] > 0.5)
                | (esp_run["flow_p2"] > 0.5)
                | (esp_run["flow_valve1"] > 0.5)
                | (esp_run["flow_outlet"] > 0.5)
            )
        ]
        flow_after_pumps_off_count = len(flow_after_pumps_off)
        flow_after_pumps_off_percent = safe_divide(flow_after_pumps_off_count, esp_rows)

        pump1_low_flow = esp_run[
            (esp_run["pump1_pwm"] >= 50)
            & (esp_run["flow_p1"] <= 0.5)
        ]
        pump2_low_flow = esp_run[
            (esp_run["pump2_pwm"] >= 50)
            & (esp_run["flow_p2"] <= 0.5)
        ]

        pump1_low_flow_count = len(pump1_low_flow)
        pump2_low_flow_count = len(pump2_low_flow)

    else:
        max_pump1_pwm = max_pump2_pwm = None
        max_flow_p1 = max_flow_p2 = max_flow_valve1 = max_flow_outlet = None
        avg_flow_p1 = avg_flow_p2 = avg_flow_valve1 = avg_flow_outlet = None
        valve1_on_percent = valve2_on_percent = valve3_on_percent = valve4_on_percent = None
        pump1_on_percent = pump2_on_percent = None
        flow_after_pumps_off_count = 0
        flow_after_pumps_off_percent = 0.0
        pump1_low_flow_count = 0
        pump2_low_flow_count = 0

    # -----------------------------
    # Arduino tank metrics
    # -----------------------------
    if ard_rows > 0:
        sensor_error_rows = ard_run[
            ard_run[["tank1", "tank2", "tank3"]].isna().any(axis=1)
        ]
        sensor_error_count = len(sensor_error_rows)
        sensor_error_percent = safe_divide(sensor_error_count, ard_rows)

        tower_start = ard_run["tank1"].dropna().iloc[0] if not ard_run["tank1"].dropna().empty else None
        tower_end = ard_run["tank1"].dropna().iloc[-1] if not ard_run["tank1"].dropna().empty else None

        treated_start = ard_run["tank2"].dropna().iloc[0] if not ard_run["tank2"].dropna().empty else None
        treated_end = ard_run["tank2"].dropna().iloc[-1] if not ard_run["tank2"].dropna().empty else None

        raw_start = ard_run["tank3"].dropna().iloc[0] if not ard_run["tank3"].dropna().empty else None
        raw_end = ard_run["tank3"].dropna().iloc[-1] if not ard_run["tank3"].dropna().empty else None

        tower_change = None if tower_start is None or tower_end is None else round(tower_end - tower_start, 2)
        treated_change = None if treated_start is None or treated_end is None else round(treated_end - treated_start, 2)
        raw_change = None if raw_start is None or raw_end is None else round(raw_end - raw_start, 2)

        avg_tower = ard_run["tank1"].mean()
        avg_treated = ard_run["tank2"].mean()
        avg_raw = ard_run["tank3"].mean()

    else:
        sensor_error_count = 0
        sensor_error_percent = 0.0
        tower_change = treated_change = raw_change = None
        avg_tower = avg_treated = avg_raw = None

    summary_rows.append({
        "run_name": run_name,
        "esp32_rows": esp_rows,
        "arduino_rows": ard_rows,

        "max_pump1_pwm": max_pump1_pwm,
        "max_pump2_pwm": max_pump2_pwm,
        "pump1_on_percent": pump1_on_percent,
        "pump2_on_percent": pump2_on_percent,

        "max_flow_p1": max_flow_p1,
        "max_flow_p2": max_flow_p2,
        "max_flow_valve1": max_flow_valve1,
        "max_flow_outlet": max_flow_outlet,

        "avg_flow_p1": round(avg_flow_p1, 3) if avg_flow_p1 is not None else None,
        "avg_flow_p2": round(avg_flow_p2, 3) if avg_flow_p2 is not None else None,
        "avg_flow_valve1": round(avg_flow_valve1, 3) if avg_flow_valve1 is not None else None,
        "avg_flow_outlet": round(avg_flow_outlet, 3) if avg_flow_outlet is not None else None,

        "valve1_on_percent": valve1_on_percent,
        "valve2_on_percent": valve2_on_percent,
        "valve3_on_percent": valve3_on_percent,
        "valve4_on_percent": valve4_on_percent,

        "sensor_error_count": sensor_error_count,
        "sensor_error_percent": sensor_error_percent,
        "flow_after_pumps_off_count": flow_after_pumps_off_count,
        "flow_after_pumps_off_percent": flow_after_pumps_off_percent,
        "pump1_low_flow_count": pump1_low_flow_count,
        "pump2_low_flow_count": pump2_low_flow_count,

        f"{TANK_MAPPING['tank1']}_avg": round(avg_tower, 3) if avg_tower is not None else None,
        f"{TANK_MAPPING['tank2']}_avg": round(avg_treated, 3) if avg_treated is not None else None,
        f"{TANK_MAPPING['tank3']}_avg": round(avg_raw, 3) if avg_raw is not None else None,

        f"{TANK_MAPPING['tank1']}_change": tower_change,
        f"{TANK_MAPPING['tank2']}_change": treated_change,
        f"{TANK_MAPPING['tank3']}_change": raw_change,
    })

summary = pd.DataFrame(summary_rows)

# Put clean poster runs first if they exist
summary["poster_priority"] = summary["run_name"].apply(
    lambda x: POSTER_RUNS.index(x) if x in POSTER_RUNS else 999
)
summary = summary.sort_values(["poster_priority", "run_name"]).drop(columns=["poster_priority"])

output_file = OUTPUT_DIR / "run_comparison_summary.csv"
summary.to_csv(output_file, index=False)

print("\nRun comparison summary:")
print(summary)

print(f"\nSaved to {output_file}")