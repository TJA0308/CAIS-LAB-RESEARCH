from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import ANALYSIS_DIR, EXPORT_DIR


HORIZON_SECONDS = 10
MAX_TANK_MISSING_PERCENT = 25.0
MERGED_CANDIDATE_RUNS = [
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
    "flow_p1",
    "flow_p2",
    "flow_valve1",
    "flow_outlet",
    "tower",
    "treated",
    "raw",
]
TARGET_COLUMNS = ["tower", "treated", "raw"]
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


def load_candidate_runs():
    candidate_runs = []

    for run_name in MERGED_CANDIDATE_RUNS:
        csv_path = Path(EXPORT_DIR) / f"{run_name}_merged_timeseries.csv"
        if not csv_path.exists():
            continue

        data = pd.read_csv(csv_path)
        required_columns = ["run_name", "t_seconds"] + FEATURE_COLUMNS
        missing_columns = [column for column in required_columns if column not in data.columns]
        if missing_columns:
            continue

        tank_missing_ok = True
        for tank in TARGET_COLUMNS:
            missing_percent = (
                pd.to_numeric(data[tank], errors="coerce").isna().mean() * 100
            )
            if missing_percent > MAX_TANK_MISSING_PERCENT:
                tank_missing_ok = False
                break

        if tank_missing_ok:
            candidate_runs.append(run_name)

    if not candidate_runs:
        raise ValueError(
            "No candidate merged CSV files exist with acceptable tank missingness."
        )

    return candidate_runs


def load_merged_run(run_name):
    csv_path = Path(EXPORT_DIR) / f"{run_name}_merged_timeseries.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing merged dataset for run: {csv_path}")

    data = pd.read_csv(csv_path)
    required_columns = ["run_name", "t_seconds"] + FEATURE_COLUMNS
    missing_columns = [column for column in required_columns if column not in data.columns]
    if missing_columns:
        raise ValueError(
            f"{csv_path.name} is missing required columns: {', '.join(missing_columns)}"
        )

    return data


def build_forecasting_rows(data):
    data = data.copy()
    data["t_seconds"] = pd.to_numeric(data["t_seconds"], errors="coerce")
    data = data.dropna(subset=["t_seconds"]).copy()
    data["t_seconds"] = data["t_seconds"].round().astype(int)

    for column in FEATURE_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.sort_values("t_seconds").drop_duplicates(subset=["t_seconds"], keep="first")

    future_targets = data[["t_seconds"] + TARGET_COLUMNS].copy()
    future_targets["t_seconds"] = future_targets["t_seconds"] - HORIZON_SECONDS
    future_targets = future_targets.rename(
        columns={column: f"{column}_future" for column in TARGET_COLUMNS}
    )

    merged = data.merge(future_targets, on="t_seconds", how="left")
    merged = merged.dropna(
        subset=FEATURE_COLUMNS + [f"{column}_future" for column in TARGET_COLUMNS]
    ).copy()

    return merged


def prepare_dataset(run_names):
    per_run = []

    for run_name in run_names:
        run_data = load_merged_run(run_name)
        modeling_rows = build_forecasting_rows(run_data)

        if modeling_rows.empty:
            raise ValueError(
                f"No usable forecasting rows remain for run {run_name} after shifting by "
                f"{HORIZON_SECONDS} seconds."
            )

        modeling_rows["run_name"] = run_name
        per_run.append(modeling_rows)

    dataset = pd.concat(per_run, ignore_index=True)
    return dataset


def evaluate_models(dataset, run_names):
    results = []

    for test_run in run_names:
        train_runs = [run_name for run_name in run_names if run_name != test_run]
        train_data = dataset[dataset["run_name"].isin(train_runs)]
        test_data = dataset[dataset["run_name"] == test_run]

        x_train = train_data[FEATURE_COLUMNS]
        y_train = train_data[[f"{column}_future" for column in TARGET_COLUMNS]]
        x_test = test_data[FEATURE_COLUMNS]
        y_test = test_data[
            [f"{column}_future" for column in TARGET_COLUMNS]
        ]

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
                "test_rows": len(x_test),
                "mae_tower": mae_values[0],
                "mae_treated": mae_values[1],
                "mae_raw": mae_values[2],
                "avg_mae": mae_values.mean(),
                "avg_rmse": rmse_values.mean(),
                "overall_r2": r2_score(
                    y_test,
                    predictions,
                    multioutput="variance_weighted",
                ),
            })

    return pd.DataFrame(results)


def write_outputs(results, run_row_counts):
    output_dir = Path(ANALYSIS_DIR)
    output_dir.mkdir(exist_ok=True)

    csv_path = output_dir / "tank_forecasting_model_results.csv"
    summary_path = output_dir / "tank_forecasting_model_summary.txt"

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
        summary_file.write("Tank Forecasting Model Summary\n")
        summary_file.write("=============================\n\n")
        summary_file.write(
            "Proof-of-concept regression models predict Arduino tank readings "
            f"{HORIZON_SECONDS} seconds into the future from merged control, flow, "
            "and tank state data.\n\n"
        )
        summary_file.write("Runs used\n")
        for run_name, row_count in run_row_counts.items():
            summary_file.write(f"- {run_name}: {row_count} modeling rows\n")
        summary_file.write("\n")
        summary_file.write("Features\n")
        summary_file.write(", ".join(FEATURE_COLUMNS) + "\n\n")
        summary_file.write("Targets\n")
        summary_file.write(
            ", ".join(f"{column}_future (+{HORIZON_SECONDS}s)" for column in TARGET_COLUMNS)
            + "\n\n"
        )
        summary_file.write("Evaluation\n")
        summary_file.write(
            "Leave-one-run-out validation across available merged runs only. "
            "No random row split is used. These results are exploratory and should "
            "not be treated as production accuracy.\n\n"
        )
        summary_file.write("Best model per held-out run by average MAE\n")
        summary_file.write(best_by_split.round(4).to_string(index=False))
        summary_file.write("\n\n")
        summary_file.write("Average summary by model\n")
        summary_file.write(model_average_summary.round(4).to_string(index=False))
        summary_file.write("\n")

    return csv_path, summary_path, model_average_summary


def main():
    run_names = load_candidate_runs()
    if len(run_names) < 2:
        raise ValueError(
            "Need at least two usable merged runs for held-out run validation."
        )

    dataset = prepare_dataset(run_names)
    run_row_counts = dataset.groupby("run_name").size().to_dict()
    results = evaluate_models(dataset, run_names)

    print("\nRuns used for tank forecasting")
    print("=" * 80)
    for run_name in run_names:
        print(f"- {run_name}: {run_row_counts[run_name]} modeling rows")

    display_columns = [
        "train_runs",
        "test_run",
        "model",
        "train_rows",
        "test_rows",
        "mae_tower",
        "mae_treated",
        "mae_raw",
        "avg_mae",
        "avg_rmse",
        "overall_r2",
    ]

    print("\nTank forecasting model results")
    print("=" * 80)
    print(results[display_columns].round(4).to_string(index=False))

    csv_path, summary_path, model_average_summary = write_outputs(results, run_row_counts)

    print("\nAverage summary by model")
    print("=" * 80)
    print(model_average_summary.round(4).to_string(index=False))

    print("\nSaved outputs:")
    print(f"- {csv_path}")
    print(f"- {summary_path}")


if __name__ == "__main__":
    main()
