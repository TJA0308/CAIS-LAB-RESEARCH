"""
Flow-response model WITH temporal (lag/rolling) features.

The main flow model (`scripts.models.flow_response_model`) uses only instantaneous control
states. Pump flow has ramp-up transients, so recent control history should help.
This script quantifies that on the wall-clock-synchronized 1-second merged runs,
comparing a static-feature model against one with added lag/rolling features under
the SAME leave-one-run-out split (a fair, apples-to-apples comparison).

Note: only the 6 runs with merged 1-second series are used here (full_cycle_run_001
has no wall clock and no merged file). Results are therefore not directly comparable
to the 7-run static model in `scripts.models.flow_response_model`; compare the
two rows below.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import ANALYSIS_DIR, EXPORT_DIR

CONTROL_COLUMNS = ["pump1_pwm", "pump2_pwm", "valve1", "valve2", "valve3", "valve4"]
FLOW_COLUMNS = ["flow_p1", "flow_p2", "flow_valve1", "flow_outlet"]
LAG_STEPS = 3          # seconds of delay to expose (1 s grid)
ROLL_WINDOW = 5        # seconds of recent-average smoothing


def load_runs():
    runs = {}
    for path in sorted(Path(EXPORT_DIR).glob("*_merged_timeseries.csv")):
        data = pd.read_csv(path)
        if not set(CONTROL_COLUMNS + FLOW_COLUMNS + ["t_seconds"]).issubset(data.columns):
            continue
        for column in CONTROL_COLUMNS + FLOW_COLUMNS + ["t_seconds"]:
            data[column] = pd.to_numeric(data[column], errors="coerce")
        run_name = path.name.replace("_merged_timeseries.csv", "")
        runs[run_name] = data.sort_values("t_seconds").reset_index(drop=True)
    return runs


def build_dataset(runs, use_temporal):
    frames = []
    temporal_columns = []
    for run_name, data in runs.items():
        data = data.copy()
        extra = []
        if use_temporal:
            for column in CONTROL_COLUMNS:
                data[f"{column}_lag{LAG_STEPS}"] = data[column].shift(LAG_STEPS)
                data[f"{column}_roll{ROLL_WINDOW}"] = (
                    data[column].rolling(ROLL_WINDOW, min_periods=1).mean()
                )
                extra += [f"{column}_lag{LAG_STEPS}", f"{column}_roll{ROLL_WINDOW}"]
        data["run_name"] = run_name
        feature_columns = CONTROL_COLUMNS + extra
        frames.append(data.dropna(subset=feature_columns + FLOW_COLUMNS))
        temporal_columns = extra
    return pd.concat(frames, ignore_index=True), CONTROL_COLUMNS + temporal_columns


def loro(dataset, feature_columns):
    runs = sorted(dataset["run_name"].unique())
    models = {
        "Ridge Regression": lambda: make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
        "Random Forest": lambda: RandomForestRegressor(
            n_estimators=200, random_state=42, min_samples_leaf=5
        ),
    }
    out = {}
    for model_name, make_model in models.items():
        r2s, maes = [], []
        for test_run in runs:
            train = dataset[dataset["run_name"] != test_run]
            test = dataset[dataset["run_name"] == test_run]
            model = make_model()
            model.fit(train[feature_columns], train[FLOW_COLUMNS])
            predictions = model.predict(test[feature_columns])
            r2s.append(r2_score(test[FLOW_COLUMNS], predictions, multioutput="variance_weighted"))
            maes.append(
                mean_absolute_error(test[FLOW_COLUMNS], predictions, multioutput="raw_values").mean()
            )
        out[model_name] = (float(np.mean(r2s)), float(np.mean(maes)))
    return out


def main():
    runs = load_runs()
    if len(runs) < 2:
        raise SystemExit("Need at least two merged runs.")

    results = {}
    for label, use_temporal in [("static", False), ("temporal", True)]:
        dataset, feature_columns = build_dataset(runs, use_temporal)
        results[label] = loro(dataset, feature_columns)

    lines = []
    lines.append("Flow-Response Model: Static vs Temporal Features")
    lines.append("=" * 48)
    lines.append(f"Runs ({len(runs)}, leave-one-run-out): " + ", ".join(sorted(runs)))
    lines.append(f"Static features: {', '.join(CONTROL_COLUMNS)}")
    lines.append(
        f"Temporal adds per control: lag{LAG_STEPS}s and rolling-mean{ROLL_WINDOW}s\n"
    )
    lines.append(f"{'model':20} {'variant':10} {'avg R2':>8} {'avg MAE':>9}")
    for model_name in ["Random Forest", "Ridge Regression"]:
        for variant in ["static", "temporal"]:
            r2, mae = results[variant][model_name]
            lines.append(f"{model_name:20} {variant:10} {r2:8.3f} {mae:9.3f}")
    rf_static = results["static"]["Random Forest"]
    rf_temporal = results["temporal"]["Random Forest"]
    lines.append(
        f"\nRandom Forest gain from temporal features: "
        f"R2 {rf_static[0]:.3f} -> {rf_temporal[0]:.3f}, "
        f"MAE {rf_static[1]:.3f} -> {rf_temporal[1]:.3f}"
    )

    report = "\n".join(lines)
    print("\n" + report)

    output_dir = Path(ANALYSIS_DIR)
    output_dir.mkdir(exist_ok=True)
    (output_dir / "flow_temporal_features_summary.txt").write_text(report, encoding="utf-8")
    print(f"\nSaved {output_dir / 'flow_temporal_features_summary.txt'}")


if __name__ == "__main__":
    main()
