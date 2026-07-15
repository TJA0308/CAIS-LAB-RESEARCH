import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_NAME, RUN_NAME, ANALYSIS_DIR, TANK_MAPPING

OUTPUT_DIR = Path(ANALYSIS_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

# -------------------------------------------------
# IMPORTANT:
# Edit these time windows after looking at your plots.
# Times are MATLAB timestamp seconds from esp32_matlab_data.
#
# For full_cycle_run_001, your run lasted to about 1060 sec.
# The windows below are a safe starting template.
# Adjust them to match when you actually changed pumps/valves.
# -------------------------------------------------

STAGE_WINDOWS = {
    "full_cycle_run_001": [
        ("baseline", 0, 30),
        ("groundwater_to_raw", 30, 180),
        ("raw_to_treated", 180, 360),
        ("treated_to_tower", 360, 540),
        ("tower_to_groundwater", 540, 660),
        ("full_pathway", 660, 900),
        ("shutdown", 900, 1100),
    ],

    "full_cycle_run_002": [
        ("baseline", 0, 30),
        ("groundwater_to_raw", 30, 90),
        ("raw_to_treated", 90, 150),
        ("treated_to_tower", 150, 210),
        ("full_pathway", 210, 270),
        ("shutdown", 270, 330),
    ],

    "full_cycle_run_003": [
    ("baseline", 0, 30),
    ("groundwater_to_raw", 30, 90),
    ("raw_to_treated", 90, 150),
    ("treated_to_tower", 150, 210),
    ("full_pathway", 210, 270),
    ("shutdown", 270, 330),
    
    ],

    "valve_routing_run_001": [
        ("baseline", 0, 30),
        ("valve2_route", 30, 75),
        ("reset_1", 75, 95),
        ("valve3_route", 95, 140),
        ("reset_2", 140, 160),
        ("valve4_route", 160, 205),
        ("shutdown", 205, 240),
    ],
    
        "pump_pwm_sweep_run_001": [
        ("baseline", 0, 30),
        ("pump1_pwm_50", 30, 75),
        ("pump1_pwm_100", 75, 120),
        ("pump1_pwm_150", 120, 165),
        ("pump1_pwm_200", 165, 210),
        ("reset", 210, 240),
        ("pump2_pwm_50", 240, 285),
        ("pump2_pwm_100", 285, 330),
        ("pump2_pwm_150", 330, 375),
        ("pump2_pwm_200", 375, 420),
        ("shutdown", 420, 480),
    ],
}


def safe_change(series):
    clean = series.dropna()
    if clean.empty:
        return None
    return round(clean.iloc[-1] - clean.iloc[0], 3)


def safe_mean(series):
    clean = series.dropna()
    if clean.empty:
        return None
    return round(clean.mean(), 3)


def safe_max(series):
    clean = series.dropna()
    if clean.empty:
        return None
    return round(clean.max(), 3)


def safe_percent(condition_count, total):
    if total == 0:
        return 0.0
    return round((condition_count / total) * 100, 2)


if RUN_NAME not in STAGE_WINDOWS:
    print(f"No stage windows defined for RUN_NAME={RUN_NAME}")
    print("Available runs in STAGE_WINDOWS:")
    for name in STAGE_WINDOWS:
        print("-", name)
    raise SystemExit(
        "Add stage windows for this run inside STAGE_WINDOWS and run again."
    )

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
    raise ValueError(f"No ESP32/MATLAB data found for run_name={RUN_NAME}")

# -------------------------------------------------
# Align Arduino time to seconds from its own start.
# This is not perfect synchronization with MATLAB,
# but it gives useful stage-level tank behavior.
#
# format="mixed" handles old/new timestamp formats.
# -------------------------------------------------
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
            arduino["timestamp_dt"] - arduino["timestamp_dt"].min()
        ).dt.total_seconds()
    else:
        arduino["t_seconds"] = pd.Series(dtype=float)
        print(f"Warning: all Arduino timestamps failed to parse for run_name={RUN_NAME}")
else:
    arduino["t_seconds"] = pd.Series(dtype=float)

stage_rows = []

for stage_name, start_s, end_s in STAGE_WINDOWS[RUN_NAME]:
    esp_stage = esp32[
        (esp32["timestamp"] >= start_s)
        & (esp32["timestamp"] < end_s)
    ].copy()

    ard_stage = arduino[
        (arduino["t_seconds"] >= start_s)
        & (arduino["t_seconds"] < end_s)
    ].copy()

    esp_rows = len(esp_stage)
    ard_rows = len(ard_stage)

    if esp_rows > 0:
        pump1_on_percent = safe_percent((esp_stage["pump1_pwm"] > 0).sum(), esp_rows)
        pump2_on_percent = safe_percent((esp_stage["pump2_pwm"] > 0).sum(), esp_rows)

        valve1_on_percent = safe_percent((esp_stage["valve1"] == 1).sum(), esp_rows)
        valve2_on_percent = safe_percent((esp_stage["valve2"] == 1).sum(), esp_rows)
        valve3_on_percent = safe_percent((esp_stage["valve3"] == 1).sum(), esp_rows)
        valve4_on_percent = safe_percent((esp_stage["valve4"] == 1).sum(), esp_rows)

        flow_after_pumps_off = esp_stage[
            (esp_stage["pump1_pwm"] == 0)
            & (esp_stage["pump2_pwm"] == 0)
            & (
                (esp_stage["flow_p1"] > 0.5)
                | (esp_stage["flow_p2"] > 0.5)
                | (esp_stage["flow_valve1"] > 0.5)
                | (esp_stage["flow_outlet"] > 0.5)
            )
        ]

        pump1_low_flow = esp_stage[
            (esp_stage["pump1_pwm"] >= 50)
            & (esp_stage["flow_p1"] <= 0.5)
        ]

        pump2_low_flow = esp_stage[
            (esp_stage["pump2_pwm"] >= 50)
            & (esp_stage["flow_p2"] <= 0.5)
        ]

    else:
        pump1_on_percent = 0.0
        pump2_on_percent = 0.0
        valve1_on_percent = 0.0
        valve2_on_percent = 0.0
        valve3_on_percent = 0.0
        valve4_on_percent = 0.0
        flow_after_pumps_off = pd.DataFrame()
        pump1_low_flow = pd.DataFrame()
        pump2_low_flow = pd.DataFrame()

    if ard_rows > 0:
        sensor_error_count = ard_stage[
            ard_stage[["tank1", "tank2", "tank3"]].isna().any(axis=1)
        ].shape[0]
        sensor_error_percent = safe_percent(sensor_error_count, ard_rows)
    else:
        sensor_error_count = 0
        sensor_error_percent = 0.0

    stage_rows.append({
        "run_name": RUN_NAME,
        "stage": stage_name,
        "start_s": start_s,
        "end_s": end_s,
        "duration_s": end_s - start_s,

        "esp32_rows": esp_rows,
        "arduino_rows": ard_rows,

        "pump1_on_percent": pump1_on_percent,
        "pump2_on_percent": pump2_on_percent,

        "avg_pump1_pwm": safe_mean(esp_stage["pump1_pwm"]) if esp_rows else None,
        "avg_pump2_pwm": safe_mean(esp_stage["pump2_pwm"]) if esp_rows else None,
        "max_pump1_pwm": safe_max(esp_stage["pump1_pwm"]) if esp_rows else None,
        "max_pump2_pwm": safe_max(esp_stage["pump2_pwm"]) if esp_rows else None,

        "valve1_on_percent": valve1_on_percent,
        "valve2_on_percent": valve2_on_percent,
        "valve3_on_percent": valve3_on_percent,
        "valve4_on_percent": valve4_on_percent,

        "avg_flow_p1": safe_mean(esp_stage["flow_p1"]) if esp_rows else None,
        "avg_flow_p2": safe_mean(esp_stage["flow_p2"]) if esp_rows else None,
        "avg_flow_valve1": safe_mean(esp_stage["flow_valve1"]) if esp_rows else None,
        "avg_flow_outlet": safe_mean(esp_stage["flow_outlet"]) if esp_rows else None,

        "max_flow_p1": safe_max(esp_stage["flow_p1"]) if esp_rows else None,
        "max_flow_p2": safe_max(esp_stage["flow_p2"]) if esp_rows else None,
        "max_flow_valve1": safe_max(esp_stage["flow_valve1"]) if esp_rows else None,
        "max_flow_outlet": safe_max(esp_stage["flow_outlet"]) if esp_rows else None,

        f"{TANK_MAPPING['tank1']}_change": safe_change(ard_stage["tank1"]) if ard_rows else None,
        f"{TANK_MAPPING['tank2']}_change": safe_change(ard_stage["tank2"]) if ard_rows else None,
        f"{TANK_MAPPING['tank3']}_change": safe_change(ard_stage["tank3"]) if ard_rows else None,

        f"avg_{TANK_MAPPING['tank1']}": safe_mean(ard_stage["tank1"]) if ard_rows else None,
        f"avg_{TANK_MAPPING['tank2']}": safe_mean(ard_stage["tank2"]) if ard_rows else None,
        f"avg_{TANK_MAPPING['tank3']}": safe_mean(ard_stage["tank3"]) if ard_rows else None,

        "sensor_error_count": sensor_error_count,
        "sensor_error_percent": sensor_error_percent,

        "flow_after_pumps_off_count": len(flow_after_pumps_off),
        "pump1_low_flow_count": len(pump1_low_flow),
        "pump2_low_flow_count": len(pump2_low_flow),
    })

stage_summary = pd.DataFrame(stage_rows)

output_file = OUTPUT_DIR / f"{RUN_NAME}_stage_summary.csv"
stage_summary.to_csv(output_file, index=False)

print(f"\nStage summary for {RUN_NAME}:")
print(stage_summary)

print(f"\nSaved to {output_file}")