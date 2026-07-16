from pathlib import Path

import pandas as pd

from config import ANALYSIS_DIR, EXPORT_DIR


MERGED_PATTERN = "*_merged_timeseries.csv"
TANK_COLUMNS = ["tower", "treated", "raw"]
VALVE_COLUMNS = ["valve1", "valve2", "valve3", "valve4"]
PUMP_COLUMNS = ["pump1_pwm", "pump2_pwm"]


def infer_run_name(csv_path):
    suffix = "_merged_timeseries"
    stem = csv_path.stem
    if stem.endswith(suffix):
        return stem[: -len(suffix)]
    return stem


def first_existing_column(data, candidates):
    for column in candidates:
        if column in data.columns:
            return column
    return None


def summarize_unique_values(series):
    values = sorted(series.dropna().unique().tolist())
    return "; ".join(str(value) for value in values)


def safe_percent(series):
    if series.empty:
        return None
    return round(series.mean() * 100, 2)


def summarize_file(csv_path):
    data = pd.read_csv(csv_path)
    run_name_column = first_existing_column(data, ["run_name"])
    timestamp_column = first_existing_column(
        data,
        ["timestamp", "t_seconds", "time_s", "time_seconds", "elapsed_seconds"],
    )

    if run_name_column and data[run_name_column].dropna().nunique() == 1:
        run_name = data[run_name_column].dropna().iloc[0]
    else:
        run_name = infer_run_name(csv_path)

    row = {
        "file": csv_path.name,
        "run_name": run_name,
        "rows": len(data),
        "duration_s": None,
    }

    if timestamp_column and not data.empty:
        timestamps = pd.to_numeric(data[timestamp_column], errors="coerce")
        if timestamps.notna().any():
            row["duration_s"] = round(timestamps.max() - timestamps.min(), 3)

    for tank in TANK_COLUMNS:
        if tank in data.columns:
            tank_values = pd.to_numeric(data[tank], errors="coerce")
            row[f"{tank}_missing_percent"] = round(tank_values.isna().mean() * 100, 2)
            row[f"{tank}_min"] = round(tank_values.min(), 3)
            row[f"{tank}_max"] = round(tank_values.max(), 3)
            row[f"{tank}_mean"] = round(tank_values.mean(), 3)
        else:
            row[f"{tank}_missing_percent"] = None
            row[f"{tank}_min"] = None
            row[f"{tank}_max"] = None
            row[f"{tank}_mean"] = None

    for pump in PUMP_COLUMNS:
        if pump in data.columns:
            row[f"unique_{pump}_values"] = summarize_unique_values(
                pd.to_numeric(data[pump], errors="coerce")
            )
        else:
            row[f"unique_{pump}_values"] = None

    for valve in VALVE_COLUMNS:
        if valve in data.columns:
            valve_values = pd.to_numeric(data[valve], errors="coerce")
            row[f"{valve}_on_percent"] = safe_percent(valve_values == 1)
        else:
            row[f"{valve}_on_percent"] = None

    required_for_tank_forecasting = TANK_COLUMNS + PUMP_COLUMNS + VALVE_COLUMNS
    present_required_columns = [
        column for column in required_for_tank_forecasting if column in data.columns
    ]
    has_required_columns = len(present_required_columns) == len(required_for_tank_forecasting)
    has_enough_rows = len(data) >= 100
    has_duration = row["duration_s"] is not None and row["duration_s"] > 0
    tank_missing_ok = all(
        row[f"{tank}_missing_percent"] is not None
        and row[f"{tank}_missing_percent"] <= 25
        for tank in TANK_COLUMNS
    )

    row["usable_for_tank_forecasting"] = (
        has_required_columns and has_enough_rows and has_duration and tank_missing_ok
    )

    if not has_required_columns:
        missing = [
            column
            for column in required_for_tank_forecasting
            if column not in data.columns
        ]
        row["tank_forecasting_note"] = "missing columns: " + ", ".join(missing)
    elif not has_enough_rows:
        row["tank_forecasting_note"] = "too few rows"
    elif not has_duration:
        row["tank_forecasting_note"] = "missing or invalid duration"
    elif not tank_missing_ok:
        row["tank_forecasting_note"] = "tank missingness above 25 percent"
    else:
        row["tank_forecasting_note"] = "candidate"

    return row


def main():
    export_dir = Path(EXPORT_DIR)
    output_dir = Path(ANALYSIS_DIR)
    output_dir.mkdir(exist_ok=True)

    merged_files = sorted(export_dir.glob(MERGED_PATTERN))

    if not merged_files:
        summary = pd.DataFrame(columns=[
            "file",
            "run_name",
            "rows",
            "duration_s",
            "usable_for_tank_forecasting",
            "tank_forecasting_note",
        ])
    else:
        summary = pd.DataFrame(summarize_file(csv_path) for csv_path in merged_files)

    output_file = output_dir / "merged_dataset_summary.csv"
    summary.to_csv(output_file, index=False)

    print("\nMerged dataset summary")
    print("=" * 80)
    if summary.empty:
        print(f"No files found matching exports/{MERGED_PATTERN}")
    else:
        print(summary.to_string(index=False))

    print(f"\nSaved summary to {output_file}")


if __name__ == "__main__":
    main()
