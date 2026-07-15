import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import loadmat

from config import DB_NAME, RUN_NAME, MAT_FILE, EXPORT_DIR, TANK_MAPPING

OUTPUT_DIR = Path(EXPORT_DIR)
OUTPUT_DIR.mkdir(exist_ok=True)

ESP32_COLUMNS = [
    "pump1_pwm",
    "pump2_pwm",
    "valve1",
    "valve2",
    "valve3",
    "valve4",
    "flow_p1",
    "flow_p2",
    "flow_valve1",
    "flow_outlet",
]

CONTROL_COLUMNS = [
    "pump1_pwm",
    "pump2_pwm",
    "valve1",
    "valve2",
    "valve3",
    "valve4",
]

FLOW_COLUMNS = [
    "flow_p1",
    "flow_p2",
    "flow_valve1",
    "flow_outlet",
]

TANK_COLUMNS_RAW = ["tank1", "tank2", "tank3"]


def get_matlab_start_wall_clock(mat_file):
    """
    Reads startWallClock from the MATLAB .mat file if it exists.
    Returns pandas Timestamp or None.
    """
    mat_path = Path(mat_file)

    if not mat_path.exists():
        print(f"Warning: MAT file not found: {mat_file}")
        return None

    mat = loadmat(mat_file, squeeze_me=True, struct_as_record=False)

    if "s" in mat:
        s = mat["s"]
    elif "serialDataStruct" in mat:
        s = mat["serialDataStruct"]
    else:
        return None

    if hasattr(s, "startWallClock"):
        start_value = getattr(s, "startWallClock")

        if isinstance(start_value, str):
            return pd.to_datetime(start_value, errors="coerce", format="mixed")

        try:
            return pd.to_datetime(str(start_value), errors="coerce", format="mixed")
        except Exception:
            return None

    return None


def safe_percent_missing(df, column):
    if column not in df.columns or len(df) == 0:
        return 100.0

    return round(df[column].isna().mean() * 100, 2)


def nearest_merge(grid, data, tolerance_seconds):
    """
    Merge data onto a 1-second grid using nearest t_seconds.
    """
    if data.empty:
        return grid.copy()

    data = data.sort_values("t_seconds").copy()
    grid = grid.sort_values("t_seconds").copy()

    return pd.merge_asof(
        grid,
        data,
        on="t_seconds",
        direction="nearest",
        tolerance=tolerance_seconds
    )


# -------------------------------------------------
# Load data from SQLite
# -------------------------------------------------
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

if arduino.empty:
    print(f"Warning: no Arduino data found for run_name={RUN_NAME}")


# -------------------------------------------------
# Determine alignment mode
# -------------------------------------------------
start_wall_clock = get_matlab_start_wall_clock(MAT_FILE)

if start_wall_clock is not None and not pd.isna(start_wall_clock):
    alignment_mode = "wall_clock"

    esp32["timestamp_abs"] = (
        start_wall_clock + pd.to_timedelta(esp32["timestamp"], unit="s")
    )

    esp32["t_seconds"] = (
        esp32["timestamp_abs"] - start_wall_clock
    ).dt.total_seconds()

    if not arduino.empty:
        arduino["timestamp_dt"] = pd.to_datetime(
            arduino["timestamp"],
            errors="coerce",
            format="mixed"
        )

        arduino = arduino.dropna(subset=["timestamp_dt"]).copy()

        arduino["t_seconds"] = (
            arduino["timestamp_dt"] - start_wall_clock
        ).dt.total_seconds()

else:
    alignment_mode = "relative_time_approximate"

    print("\nWARNING:")
    print("No startWallClock found in MAT file.")
    print("Falling back to seconds-from-own-start alignment.")
    print("This is approximate and should not be treated as exact synchronization.\n")

    esp32["t_seconds"] = esp32["timestamp"] - esp32["timestamp"].min()

    if not arduino.empty:
        arduino["timestamp_dt"] = pd.to_datetime(
            arduino["timestamp"],
            errors="coerce",
            format="mixed"
        )

        arduino = arduino.dropna(subset=["timestamp_dt"]).copy()

        arduino["t_seconds"] = (
            arduino["timestamp_dt"] - arduino["timestamp_dt"].min()
        ).dt.total_seconds()


# -------------------------------------------------
# Prepare ESP32 data
# -------------------------------------------------
esp32_model = esp32[["t_seconds"] + ESP32_COLUMNS].copy()
esp32_model = esp32_model.dropna(subset=["t_seconds"]).sort_values("t_seconds")

esp32_duration = float(esp32_model["t_seconds"].max() - esp32_model["t_seconds"].min())

grid_seconds = np.arange(
    0,
    int(np.floor(esp32_model["t_seconds"].max())) + 1,
    1
)

grid = pd.DataFrame({"t_seconds": grid_seconds.astype(float)})

esp32_merged = nearest_merge(
    grid,
    esp32_model,
    tolerance_seconds=1.0
)

# Forward/backward fill controls because commands stay active until changed.
for col in CONTROL_COLUMNS:
    if col in esp32_merged.columns:
        esp32_merged[col] = esp32_merged[col].ffill().bfill()

# Interpolate flow values.
for col in FLOW_COLUMNS:
    if col in esp32_merged.columns:
        esp32_merged[col] = esp32_merged[col].interpolate(
            method="linear",
            limit_direction="both"
        )


# -------------------------------------------------
# Prepare Arduino data
# -------------------------------------------------
if not arduino.empty:
    tank_rename = {
        "tank1": TANK_MAPPING.get("tank1", "tank1"),
        "tank2": TANK_MAPPING.get("tank2", "tank2"),
        "tank3": TANK_MAPPING.get("tank3", "tank3"),
    }

    arduino_model = arduino[["t_seconds"] + TANK_COLUMNS_RAW].copy()
    arduino_model = arduino_model.rename(columns=tank_rename)
    arduino_model = arduino_model.dropna(subset=["t_seconds"]).sort_values("t_seconds")

    arduino_merged = nearest_merge(
        grid,
        arduino_model,
        tolerance_seconds=2.0
    )

    for col in tank_rename.values():
        if col in arduino_merged.columns:
            arduino_merged[col] = arduino_merged[col].interpolate(
                method="linear",
                limit_direction="both"
            )

    arduino_duration = (
        float(arduino_model["t_seconds"].max() - arduino_model["t_seconds"].min())
        if not arduino_model.empty
        else 0.0
    )

else:
    arduino_merged = grid.copy()
    arduino_merged[TANK_MAPPING.get("tank1", "tower")] = np.nan
    arduino_merged[TANK_MAPPING.get("tank2", "treated")] = np.nan
    arduino_merged[TANK_MAPPING.get("tank3", "raw")] = np.nan
    arduino_duration = 0.0


# -------------------------------------------------
# Combine ESP32 and Arduino
# -------------------------------------------------
tank_names = [
    TANK_MAPPING.get("tank1", "tower"),
    TANK_MAPPING.get("tank2", "treated"),
    TANK_MAPPING.get("tank3", "raw"),
]

merged = esp32_merged.merge(
    arduino_merged[["t_seconds"] + tank_names],
    on="t_seconds",
    how="left"
)

merged.insert(0, "run_name", RUN_NAME)

final_columns = [
    "run_name",
    "t_seconds",
    "pump1_pwm",
    "pump2_pwm",
    "valve1",
    "valve2",
    "valve3",
    "valve4",
    "flow_p1",
    "flow_p2",
    "flow_valve1",
    "flow_outlet",
    "tower",
    "treated",
    "raw",
]

for expected_name in ["tower", "treated", "raw"]:
    if expected_name not in merged.columns:
        merged[expected_name] = np.nan

merged = merged[final_columns]

output_file = OUTPUT_DIR / f"{RUN_NAME}_merged_timeseries.csv"
merged.to_csv(output_file, index=False)


# -------------------------------------------------
# Diagnostics
# -------------------------------------------------
print("\nMerged time-series diagnostics")
print("--------------------------------")
print(f"RUN_NAME: {RUN_NAME}")
print(f"MAT_FILE: {MAT_FILE}")
print(f"alignment_mode: {alignment_mode}")
print(f"ESP32 rows: {len(esp32)}")
print(f"Arduino rows: {len(arduino)}")
print(f"ESP32 duration seconds: {round(esp32_duration, 2)}")
print(f"Arduino duration seconds: {round(arduino_duration, 2)}")
print(f"Merged rows: {len(merged)}")
print(f"Missing tower %: {safe_percent_missing(merged, 'tower')}")
print(f"Missing treated %: {safe_percent_missing(merged, 'treated')}")
print(f"Missing raw %: {safe_percent_missing(merged, 'raw')}")
print(f"Saved merged CSV to: {output_file}")