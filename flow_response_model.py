import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import ANALYSIS_DIR, DB_NAME, EXPORT_DIR


CLEAN_RUNS = [
    "full_cycle_run_001",
    "full_cycle_run_002",
    "full_cycle_run_003",
    "pump_pwm_sweep_run_001",
    "valve_routing_run_001",
]

FEATURE_COLUMNS = [
    "pump1_pwm",
    "pump2_pwm",
    "valve1",
    "valve2",
    "valve3",
    "valve4",
]

TARGET_COLUMNS = [
    "flow_p1",
    "flow_p2",
    "flow_valve1",
    "flow_outlet",
]
ALL_REQUIRED_COLUMNS = ["run_name"] + FEATURE_COLUMNS + TARGET_COLUMNS
Clean_CSV_PATH = Path(EXPORT_DIR) / "clean_esp32_model_data.csv"

MODELS = {
    "Mean Predictor": DummyRegressor(strategy="mean"),
    "Linear Regression": LinearRegression(),
    "Ridge Regression": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "Random Forest": RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        min_samples_leaf=5,
    ),
}


def load_data():
    if Clean_CSV_PATH.exists():
        data = pd.read_csv(Clean_CSV_PATH)
        missing_columns = [
            column for column in ALL_REQUIRED_COLUMNS if column not in data.columns
        ]
        if missing_columns:
            raise ValueError(
                "Clean CSV is missing required columns: " + ", ".join(missing_columns)
            )

        data = data[data["run_name"].isin(CLEAN_RUNS)].copy()
        return data, "clean CSV"

    placeholders = ",".join("?" for _ in CLEAN_RUNS)

    conn = sqlite3.connect(DB_NAME)
    data = pd.read_sql_query(
        f"""
        SELECT {", ".join(ALL_REQUIRED_COLUMNS)}
        FROM esp32_matlab_data
        WHERE run_name IN ({placeholders})
        ORDER BY run_name, timestamp
        """,
        conn,
        params=CLEAN_RUNS,
    )
    conn.close()

    return data, "raw SQLite database"


def validate_data(data):
    present_runs = set(data["run_name"].unique())
    missing_runs = [run_name for run_name in CLEAN_RUNS if run_name not in present_runs]

    if missing_runs:
        raise ValueError(
            "Missing required clean run(s) in esp32_matlab_data: "
            + ", ".join(missing_runs)
        )

    required_columns = ALL_REQUIRED_COLUMNS
    rows_before = len(data)
    data = data.dropna(subset=required_columns).copy()
    rows_dropped = rows_before - len(data)

    if data.empty:
        raise ValueError("No complete ESP32 rows remain after dropping missing values.")

    run_counts = data["run_name"].value_counts()
    empty_after_cleaning = [
        run_name for run_name in CLEAN_RUNS if run_counts.get(run_name, 0) == 0
    ]

    if empty_after_cleaning:
        raise ValueError(
            "Run(s) have no complete rows after cleaning: "
            + ", ".join(empty_after_cleaning)
        )

    return data, rows_dropped


def evaluate_models(data):
    results = []

    for test_run in CLEAN_RUNS:
        train_runs = [run_name for run_name in CLEAN_RUNS if run_name != test_run]
        train_data = data[data["run_name"].isin(train_runs)]
        test_data = data[data["run_name"] == test_run]

        x_train = train_data[FEATURE_COLUMNS]
        y_train = train_data[TARGET_COLUMNS]
        x_test = test_data[FEATURE_COLUMNS]
        y_test = test_data[TARGET_COLUMNS]

        for model_name, model in MODELS.items():
            model.fit(x_train, y_train)
            predictions = model.predict(x_test)

            mae_values = mean_absolute_error(
                y_test,
                predictions,
                multioutput="raw_values",
            )
            rmse_values = np.sqrt(
                mean_squared_error(
                    y_test,
                    predictions,
                    multioutput="raw_values",
                )
            )

            results.append({
                "train_runs": " + ".join(train_runs),
                "test_run": test_run,
                "model": model_name,
                "train_rows": len(train_data),
                "test_rows": len(test_data),
                "mae_flow_p1": mae_values[0],
                "mae_flow_p2": mae_values[1],
                "mae_flow_valve1": mae_values[2],
                "mae_flow_outlet": mae_values[3],
                "avg_mae": mae_values.mean(),
                "avg_rmse": rmse_values.mean(),
                "overall_r2": r2_score(
                    y_test,
                    predictions,
                    multioutput="variance_weighted",
                ),
            })

    return pd.DataFrame(results)


def write_summary(results, row_counts, rows_dropped):
    output_dir = Path(ANALYSIS_DIR)
    output_dir.mkdir(exist_ok=True)

    csv_path = output_dir / "flow_response_model_results.csv"
    summary_path = output_dir / "flow_response_model_summary.txt"

    results.to_csv(csv_path, index=False)

    best_by_split = (
        results.sort_values(["test_run", "avg_mae"])
        .groupby("test_run")
        .head(1)
        .reset_index(drop=True)
    )
    model_average_summary = (
        results.groupby("model", as_index=False)
        .agg(
            mean_avg_mae=("avg_mae", "mean"),
            mean_avg_rmse=("avg_rmse", "mean"),
            mean_overall_r2=("overall_r2", "mean"),
        )
        .sort_values("mean_avg_mae")
        .reset_index(drop=True)
    )

    with open(summary_path, "w", encoding="utf-8") as summary_file:
        summary_file.write("Flow Response Model Summary\n")
        summary_file.write("===========================\n\n")
        summary_file.write("Task\n")
        summary_file.write(
            "Predict ESP32 flow response from pump PWM and valve control states.\n\n"
        )

        summary_file.write("Runs Used\n")
        for run_name in CLEAN_RUNS:
            summary_file.write(f"- {run_name}: {int(row_counts[run_name])} rows\n")
        summary_file.write(f"\nRows dropped for missing values: {rows_dropped}\n\n")

        summary_file.write("Features\n")
        summary_file.write(", ".join(FEATURE_COLUMNS) + "\n\n")

        summary_file.write("Targets\n")
        summary_file.write(", ".join(TARGET_COLUMNS) + "\n\n")

        summary_file.write("Evaluation\n")
        summary_file.write(
            "Leave-one-run-out cross-validation across five runs. "
            "No random row split is used.\n\n"
        )

        summary_file.write("Best Model Per Held-Out Run by Average MAE\n")
        summary_file.write(best_by_split.round(4).to_string(index=False))
        summary_file.write("\n\n")

        summary_file.write("Average Summary By Model\n")
        summary_file.write(model_average_summary.round(4).to_string(index=False))
        summary_file.write("\n")

    return csv_path, summary_path, model_average_summary


def main():
    data, data_source = load_data()
    data, rows_dropped = validate_data(data)

    row_counts = data.groupby("run_name").size()
    results = evaluate_models(data)

    display_columns = [
        "train_runs",
        "test_run",
        "model",
        "train_rows",
        "test_rows",
        "mae_flow_p1",
        "mae_flow_p2",
        "mae_flow_valve1",
        "mae_flow_outlet",
        "avg_mae",
        "avg_rmse",
        "overall_r2",
    ]

    print("\nFlow response model results")
    print("=" * 80)
    print(f"Data source: {data_source}")
    print("=" * 80)
    print(results[display_columns].round(4).to_string(index=False))

    csv_path, summary_path, model_average_summary = write_summary(
        results,
        row_counts,
        rows_dropped,
    )

    print("\nAverage summary by model")
    print("=" * 80)
    print(model_average_summary.round(4).to_string(index=False))

    print("\nSaved outputs:")
    print(f"- {csv_path}")
    print(f"- {summary_path}")


if __name__ == "__main__":
    main()
