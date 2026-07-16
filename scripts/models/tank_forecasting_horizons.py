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


HORIZONS_SECONDS = [10, 30, 60, 120]
EXTREME_JUMP_THRESHOLD = 300
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


def infer_run_name(csv_path):
    suffix = "_merged_timeseries"
    if csv_path.stem.endswith(suffix):
        return csv_path.stem[: -len(suffix)]
    return csv_path.stem


def load_merged_runs():
    runs = {}
    for csv_path in sorted(Path(EXPORT_DIR).glob("*_merged_timeseries.csv")):
        data = pd.read_csv(csv_path)
        required_columns = ["run_name", "t_seconds"] + FEATURE_COLUMNS
        if not set(required_columns).issubset(data.columns):
            continue

        for column in ["t_seconds"] + FEATURE_COLUMNS:
            data[column] = pd.to_numeric(data[column], errors="coerce")

        run_name = infer_run_name(csv_path)
        data["run_name"] = data["run_name"].fillna(run_name)
        runs[run_name] = (
            data.dropna(subset=["t_seconds"])
            .sort_values("t_seconds")
            .drop_duplicates(subset=["t_seconds"], keep="first")
            .reset_index(drop=True)
        )
    return runs


def build_horizon_rows(run_name, data, horizon_seconds):
    data = data.copy()

    for column in TARGET_COLUMNS:
        data[f"{column}_future"] = data[column].shift(-horizon_seconds)

    drop_columns = FEATURE_COLUMNS + [f"{column}_future" for column in TARGET_COLUMNS]
    data = data.dropna(subset=drop_columns).copy()

    jump_mask = pd.Series(False, index=data.index)
    for column in TARGET_COLUMNS:
        jump_mask = jump_mask | (data[column].diff().abs() > EXTREME_JUMP_THRESHOLD)
    data = data.loc[~jump_mask].copy()

    data["run_name"] = run_name
    data["horizon_seconds"] = horizon_seconds
    return data


def prepare_horizon_dataset(runs, horizon_seconds):
    frames = []
    for run_name, data in runs.items():
        rows = build_horizon_rows(run_name, data, horizon_seconds)
        if not rows.empty:
            frames.append(rows)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def metrics_row(horizon, train_runs, test_run, model_name, train_rows, test_rows, y_test, predictions):
    mae_values = mean_absolute_error(y_test, predictions, multioutput="raw_values")
    rmse_values = np.sqrt(mean_squared_error(y_test, predictions, multioutput="raw_values"))
    return {
        "horizon_seconds": horizon,
        "train_runs": " + ".join(train_runs),
        "test_run": test_run,
        "model": model_name,
        "train_rows": train_rows,
        "test_rows": test_rows,
        "mae_tower": mae_values[0],
        "mae_treated": mae_values[1],
        "mae_raw": mae_values[2],
        "avg_mae": mae_values.mean(),
        "avg_rmse": rmse_values.mean(),
        "overall_r2": r2_score(y_test, predictions, multioutput="variance_weighted"),
    }


def evaluate_horizon(dataset, horizon_seconds):
    results = []
    run_names = sorted(dataset["run_name"].unique())
    target_columns = [f"{column}_future" for column in TARGET_COLUMNS]

    for test_run in run_names:
        train_runs = [run_name for run_name in run_names if run_name != test_run]
        train_data = dataset[dataset["run_name"].isin(train_runs)]
        test_data = dataset[dataset["run_name"] == test_run]

        x_train = train_data[FEATURE_COLUMNS]
        y_train = train_data[target_columns]
        x_test = test_data[FEATURE_COLUMNS]
        y_test = test_data[target_columns]

        persistence_predictions = test_data[TARGET_COLUMNS].to_numpy()
        results.append(
            metrics_row(
                horizon_seconds,
                train_runs,
                test_run,
                "Persistence (no change)",
                len(train_data),
                len(test_data),
                y_test,
                persistence_predictions,
            )
        )

        for model_name, model in MODELS.items():
            model.fit(x_train, y_train)
            predictions = model.predict(x_test)
            results.append(
                metrics_row(
                    horizon_seconds,
                    train_runs,
                    test_run,
                    model_name,
                    len(train_data),
                    len(test_data),
                    y_test,
                    predictions,
                )
            )

    return results


def main():
    runs = load_merged_runs()
    if len(runs) < 2:
        raise SystemExit("Need at least two merged runs for horizon evaluation.")

    all_results = []
    run_counts = []
    for horizon_seconds in HORIZONS_SECONDS:
        dataset = prepare_horizon_dataset(runs, horizon_seconds)
        if dataset.empty or dataset["run_name"].nunique() < 2:
            continue

        run_counts.extend(
            {
                "horizon_seconds": horizon_seconds,
                "run_name": run_name,
                "rows": row_count,
            }
            for run_name, row_count in dataset.groupby("run_name").size().items()
        )
        all_results.extend(evaluate_horizon(dataset, horizon_seconds))

    results = pd.DataFrame(all_results)
    if results.empty:
        raise SystemExit("No usable horizon results were produced.")

    output_dir = Path(ANALYSIS_DIR)
    output_dir.mkdir(exist_ok=True)
    results_path = output_dir / "tank_forecasting_horizon_results.csv"
    summary_path = output_dir / "tank_forecasting_horizon_summary.txt"
    counts_path = output_dir / "tank_forecasting_horizon_run_counts.csv"

    results.to_csv(results_path, index=False)
    pd.DataFrame(run_counts).to_csv(counts_path, index=False)

    average_summary = (
        results.groupby(["horizon_seconds", "model"], as_index=False)
        .agg(
            mean_avg_mae=("avg_mae", "mean"),
            mean_avg_rmse=("avg_rmse", "mean"),
            mean_overall_r2=("overall_r2", "mean"),
        )
        .sort_values(["horizon_seconds", "mean_avg_mae"])
        .reset_index(drop=True)
    )

    best_by_horizon = (
        average_summary.sort_values(["horizon_seconds", "mean_avg_mae"])
        .groupby("horizon_seconds")
        .head(1)
        .reset_index(drop=True)
    )

    with open(summary_path, "w", encoding="utf-8") as summary_file:
        summary_file.write("Tank Forecasting Horizon Sweep\n")
        summary_file.write("==============================\n\n")
        summary_file.write(
            "Task: compare short and longer tank-level forecast horizons using "
            "leave-one-run-out validation on merged 1-second runs.\n\n"
        )
        summary_file.write("Horizons evaluated: ")
        summary_file.write(", ".join(f"{h}s" for h in sorted(results["horizon_seconds"].unique())))
        summary_file.write("\n\n")
        summary_file.write("Average summary by horizon and model\n")
        summary_file.write(average_summary.round(4).to_string(index=False))
        summary_file.write("\n\n")
        summary_file.write("Best model by average MAE per horizon\n")
        summary_file.write(best_by_horizon.round(4).to_string(index=False))
        summary_file.write("\n")

    print("\nTank forecasting horizon summary")
    print("=" * 80)
    print(average_summary.round(4).to_string(index=False))
    print("\nBest by horizon")
    print("=" * 80)
    print(best_by_horizon.round(4).to_string(index=False))
    print("\nSaved outputs:")
    print(f"- {results_path}")
    print(f"- {summary_path}")
    print(f"- {counts_path}")


if __name__ == "__main__":
    main()
