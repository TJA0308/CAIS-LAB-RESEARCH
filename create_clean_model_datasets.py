import sqlite3
from pathlib import Path

import pandas as pd

from config import ANALYSIS_DIR, DB_NAME, EXPORT_DIR


ESP32_RUNS = [
    "full_cycle_run_001",
    "full_cycle_run_002",
    "full_cycle_run_003",
    "full_cycle_run_004",
    "pump_pwm_sweep_run_001",
    "pump_pwm_sweep_run_002",
    "valve_routing_run_001",
    "valve_routing_run_002",
]

TANK_RUNS = [
    "full_cycle_run_002",
    "full_cycle_run_003",
    "full_cycle_run_004",
    "pump_pwm_sweep_run_001",
    "pump_pwm_sweep_run_002",
    "valve_routing_run_001",
    "valve_routing_run_002",
]

ESP32_REQUIRED_COLUMNS = [
    "run_name",
    "timestamp",
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

TANK_FEATURE_COLUMNS = [
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

TANK_TARGET_COLUMNS = ["tower", "treated", "raw"]
TIME_COLUMN_CANDIDATES = ["relative_time", "timestamp", "t_seconds"]
FUTURE_SHIFT_ROWS = 10
EXTREME_JUMP_THRESHOLD = 300


def first_existing_column(data, candidates):
    for column in candidates:
        if column in data.columns:
            return column
    return None


def infer_run_name(csv_path):
    suffix = "_merged_timeseries"
    stem = csv_path.stem
    if stem.endswith(suffix):
        return stem[: -len(suffix)]
    return stem


def build_summary_row(dataset_type, run_name, raw_rows, clean_rows, notes):
    dropped_rows = raw_rows - clean_rows
    dropped_percent = round((dropped_rows / raw_rows) * 100, 2) if raw_rows else 0.0
    return {
        "dataset_type": dataset_type,
        "run_name": run_name,
        "raw_rows": raw_rows,
        "clean_rows": clean_rows,
        "dropped_rows": dropped_rows,
        "dropped_percent": dropped_percent,
        "notes": notes,
    }


def clean_esp32_model_data():
    placeholders = ",".join("?" for _ in ESP32_RUNS)
    query = f"""
        SELECT {", ".join(ESP32_REQUIRED_COLUMNS)}
        FROM esp32_matlab_data
        WHERE run_name IN ({placeholders})
        ORDER BY run_name, timestamp
    """

    conn = sqlite3.connect(DB_NAME)
    data = pd.read_sql_query(query, conn, params=ESP32_RUNS)
    conn.close()

    if data.empty:
        empty = pd.DataFrame(columns=ESP32_REQUIRED_COLUMNS + [
            "dropped_pump1_low_flow",
            "dropped_pump2_low_flow",
        ])
        summary_rows = [
            build_summary_row(
                "esp32_flow_response",
                run_name,
                0,
                0,
                "run not present in esp32_matlab_data",
            )
            for run_name in ESP32_RUNS
        ]
        return empty, summary_rows

    for column in ESP32_REQUIRED_COLUMNS:
        if column != "run_name":
            data[column] = pd.to_numeric(data[column], errors="coerce")

    summary_rows = []
    cleaned_runs = []

    for run_name in ESP32_RUNS:
        run_data = data[data["run_name"] == run_name].copy()
        raw_rows = len(run_data)

        if raw_rows == 0:
            summary_rows.append(
                build_summary_row(
                    "esp32_flow_response",
                    run_name,
                    0,
                    0,
                    "run not present in esp32_matlab_data",
                )
            )
            continue

        cleaned = run_data.dropna(subset=ESP32_REQUIRED_COLUMNS).copy()
        missing_drop_count = raw_rows - len(cleaned)

        cleaned["dropped_pump1_low_flow"] = (
            (cleaned["pump1_pwm"] >= 50) & (cleaned["flow_p1"] <= 0.5)
        )
        cleaned["dropped_pump2_low_flow"] = (
            (cleaned["pump2_pwm"] >= 50) & (cleaned["flow_p2"] <= 0.5)
        )

        low_flow_drop_count = int(
            (cleaned["dropped_pump1_low_flow"] | cleaned["dropped_pump2_low_flow"]).sum()
        )
        cleaned = cleaned[
            ~(cleaned["dropped_pump1_low_flow"] | cleaned["dropped_pump2_low_flow"])
        ].copy()

        notes = (
            f"dropped_missing={missing_drop_count}; "
            f"dropped_low_flow={low_flow_drop_count}"
        )
        summary_rows.append(
            build_summary_row(
                "esp32_flow_response",
                run_name,
                raw_rows,
                len(cleaned),
                notes,
            )
        )
        cleaned_runs.append(cleaned)

    if cleaned_runs:
        cleaned_data = pd.concat(cleaned_runs, ignore_index=True)
    else:
        cleaned_data = pd.DataFrame(columns=ESP32_REQUIRED_COLUMNS + [
            "dropped_pump1_low_flow",
            "dropped_pump2_low_flow",
        ])

    return cleaned_data, summary_rows


def clean_tank_forecasting_data():
    export_dir = Path(EXPORT_DIR)
    summary_rows = []
    cleaned_runs = []

    for run_name in TANK_RUNS:
        csv_path = export_dir / f"{run_name}_merged_timeseries.csv"
        if not csv_path.exists():
            summary_rows.append(
                build_summary_row(
                    "tank_forecasting",
                    run_name,
                    0,
                    0,
                    "merged CSV not present",
                )
            )
            continue

        data = pd.read_csv(csv_path)
        raw_rows = len(data)

        required_columns = ["run_name"] + TANK_FEATURE_COLUMNS
        missing_columns = [column for column in required_columns if column not in data.columns]
        if missing_columns:
            summary_rows.append(
                build_summary_row(
                    "tank_forecasting",
                    run_name,
                    raw_rows,
                    0,
                    "missing columns: " + ", ".join(missing_columns),
                )
            )
            continue

        data = data.copy()
        time_column = first_existing_column(data, TIME_COLUMN_CANDIDATES)
        if time_column:
            data[time_column] = pd.to_numeric(data[time_column], errors="coerce")
            data = data.sort_values(time_column, kind="stable")

        for column in TANK_FEATURE_COLUMNS:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        for column in TANK_TARGET_COLUMNS:
            data[f"{column}_future_10s"] = data[column].shift(-FUTURE_SHIFT_ROWS)

        after_future = data.copy()
        dropna_columns = TANK_FEATURE_COLUMNS + [
            "tower_future_10s",
            "treated_future_10s",
            "raw_future_10s",
        ]
        cleaned = after_future.dropna(subset=dropna_columns).copy()
        missing_drop_count = len(after_future) - len(cleaned)

        jump_mask = pd.Series(False, index=cleaned.index)
        for column in TANK_TARGET_COLUMNS:
            jump_mask = jump_mask | (cleaned[column].diff().abs() > EXTREME_JUMP_THRESHOLD)

        extreme_jump_drop_count = int(jump_mask.sum())
        cleaned = cleaned.loc[~jump_mask].copy()
        cleaned["run_name"] = cleaned["run_name"].fillna(run_name)

        notes = (
            f"time_column={time_column or 'none'}; "
            f"dropped_missing={missing_drop_count}; "
            f"dropped_extreme_jumps={extreme_jump_drop_count}"
        )
        summary_rows.append(
            build_summary_row(
                "tank_forecasting",
                run_name,
                raw_rows,
                len(cleaned),
                notes,
            )
        )
        cleaned_runs.append(cleaned)

    output_columns = (
        ["run_name"]
        + ([column for column in TIME_COLUMN_CANDIDATES if column == "relative_time"])
        + ([column for column in TIME_COLUMN_CANDIDATES if column == "timestamp"])
        + ([column for column in TIME_COLUMN_CANDIDATES if column == "t_seconds"])
        + TANK_FEATURE_COLUMNS
        + ["tower_future_10s", "treated_future_10s", "raw_future_10s"]
    )

    if cleaned_runs:
        cleaned_data = pd.concat(cleaned_runs, ignore_index=True)
        output_columns = [column for column in output_columns if column in cleaned_data.columns]
        cleaned_data = cleaned_data[output_columns]
    else:
        cleaned_data = pd.DataFrame(columns=output_columns)

    return cleaned_data, summary_rows


def save_outputs(clean_esp32_data, clean_tank_data, summary_rows):
    export_dir = Path(EXPORT_DIR)
    analysis_dir = Path(ANALYSIS_DIR)
    export_dir.mkdir(exist_ok=True)
    analysis_dir.mkdir(exist_ok=True)

    esp32_output = export_dir / "clean_esp32_model_data.csv"
    tank_output = export_dir / "clean_tank_forecasting_data.csv"
    summary_output = analysis_dir / "cleaning_summary.csv"

    clean_esp32_data.to_csv(esp32_output, index=False)
    clean_tank_data.to_csv(tank_output, index=False)

    summary = pd.DataFrame(summary_rows)
    summary = summary.sort_values(["dataset_type", "run_name"]).reset_index(drop=True)
    summary.to_csv(summary_output, index=False)

    return esp32_output, tank_output, summary_output, summary


def main():
    clean_esp32_data, esp32_summary_rows = clean_esp32_model_data()
    clean_tank_data, tank_summary_rows = clean_tank_forecasting_data()

    esp32_output, tank_output, summary_output, summary = save_outputs(
        clean_esp32_data,
        clean_tank_data,
        esp32_summary_rows + tank_summary_rows,
    )

    print("\nCleaning summary")
    print("=" * 100)
    if summary.empty:
        print("No runs were processed.")
    else:
        print(summary.to_string(index=False))

    print("\nSaved outputs:")
    print(f"- {esp32_output}")
    print(f"- {tank_output}")
    print(f"- {summary_output}")


if __name__ == "__main__":
    main()
