"""
Generate poster / presentation figures from existing pipeline outputs.

Produces PNGs in plots/:
  1. synchronized_timeline_<run>.png       - pump/valve/flow/tank on one wall-clock axis
  2. flow_response_model_results.png        - LORO MAE and R2 by model
  3. flow_prediction_overlay_<run>.png      - held-out predicted vs measured flow
  4. tank_forecasting_model_results.png     - LORO MAE and R2 by model (with persistence)
  5. architecture_diagram.png               - data-flow / system architecture

Run after:
  python -m scripts.models.flow_response_model
  python -m scripts.models.tank_forecasting_model
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score

from config import ANALYSIS_DIR, EXPORT_DIR, PLOT_DIR

PLOT_PATH = Path(PLOT_DIR)
PLOT_PATH.mkdir(exist_ok=True)

SYNC_RUN = "full_cycle_run_004"  # longest clean full-cycle run
FLOW_OVERLAY_RUN = "full_cycle_run_002"
FLOW_FEATURE_COLUMNS = [
    "pump1_pwm",
    "pump2_pwm",
    "valve1",
    "valve2",
    "valve3",
    "valve4",
]
FLOW_TARGET_COLUMNS = ["flow_p1", "flow_p2", "flow_valve1", "flow_outlet"]
TANK_COLUMNS = ["tower", "treated", "raw"]

BAR_BLUE = "#2b7bba"
BAR_GREY = "#b0b0b0"


def despike_for_plot(series, threshold=250, window=5):
    values = pd.to_numeric(series, errors="coerce")
    rolling_median = values.rolling(window=window, center=True, min_periods=3).median()
    spike_mask = (values - rolling_median).abs() > threshold
    return values.mask(spike_mask).interpolate(limit_direction="both")


def synchronized_timeline(run_name=SYNC_RUN):
    csv_path = Path(EXPORT_DIR) / f"{run_name}_merged_timeseries.csv"
    if not csv_path.exists():
        print(f"Skipping synchronized timeline: {csv_path} not found")
        return

    data = pd.read_csv(csv_path)
    t = data["t_seconds"]

    fig, axes = plt.subplots(nrows=4, ncols=1, figsize=(12, 11), sharex=True)
    fig.suptitle(
        f"Wall-Clock Synchronized System Timeline - {run_name}\n"
        "Arduino tanks + ESP32/MATLAB controls & flow on one 1-second axis",
        fontsize=15,
    )

    axes[0].plot(t, data["pump1_pwm"], label="Pump 1 command")
    axes[0].plot(t, data["pump2_pwm"], label="Pump 2 command")
    axes[0].set_ylabel("Pump PWM")
    axes[0].set_title("Pump Commands")

    for valve in ["valve1", "valve2", "valve3", "valve4"]:
        axes[1].plot(t, data[valve], label=valve.replace("valve", "Valve "))
    axes[1].set_ylabel("Valve state")
    axes[1].set_yticks([0, 1])
    axes[1].set_title("Valve States")

    axes[2].plot(t, data["flow_p1"], label="Pump 1 flow")
    axes[2].plot(t, data["flow_p2"], label="Pump 2 flow")
    axes[2].plot(t, data["flow_valve1"], label="Valve 1 flow")
    axes[2].plot(t, data["flow_outlet"], label="Outlet flow")
    axes[2].set_ylabel("Flow reading")
    axes[2].set_title("Flow Response")

    for tank in TANK_COLUMNS:
        axes[3].plot(t, despike_for_plot(data[tank]), label=tank.title())
    axes[3].set_ylabel("Tank reading\n(raw ultrasonic)")
    axes[3].set_xlabel("Time since run start (s, wall-clock synchronized)")
    axes[3].set_title("Tank Levels (isolated ultrasonic spikes interpolated for display)")

    for ax in axes:
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out = PLOT_PATH / f"synchronized_timeline_{run_name}.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Saved {out}")


# ---------------------------------------------------------------------------
# Model result charts
# ---------------------------------------------------------------------------
def _model_summary(results_csv):
    results = pd.read_csv(results_csv)
    summary = results.groupby("model", as_index=False).agg(
        avg_mae=("avg_mae", "mean"),
        std_mae=("avg_mae", "std"),
        avg_r2=("overall_r2", "mean"),
        std_r2=("overall_r2", "std"),
    )
    summary[["std_mae", "std_r2"]] = summary[["std_mae", "std_r2"]].fillna(0)
    return summary


def _fold_values(results, metric_column):
    return {
        model: results.loc[results["model"] == model, metric_column].to_numpy()
        for model in results["model"].unique()
    }


def _bar_colors(models, baseline_names):
    return [BAR_GREY if model in baseline_names else BAR_BLUE for model in models]


def _clean_panel(
    ax,
    models,
    means,
    stds,
    fold_values,
    colors,
    xlabel,
    title,
    fmt="{:.2f}",
    right_pad=0.22,
):
    """One horizontal bar panel: mean bar + std whisker + tight fold dots +
    a right-aligned column of value labels that never overlaps the bars."""
    y = np.arange(len(models))
    ax.barh(y, means, color=colors, height=0.62, zorder=2)
    ax.errorbar(
        means, y, xerr=stds, fmt="none",
        ecolor="#2a2a2a", elinewidth=1.1, capsize=3, zorder=3,
    )

    # Individual held-out folds as a tight, low-noise cluster on each bar.
    for i, model in enumerate(models):
        vals = fold_values.get(model, np.array([]))
        n = len(vals)
        if n:
            jitter = np.linspace(-0.05, 0.05, n) if n > 1 else np.array([0.0])
            ax.scatter(
                vals, i + jitter, s=13, color="#1b1b1b",
                alpha=0.45, linewidth=0, zorder=4,
            )

    ax.set_yticks(y)
    ax.set_yticklabels(models)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel(xlabel)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.18, zorder=0)

    # Add right margin so the value-label column sits off the bars.
    lo, hi = ax.get_xlim()
    ax.set_xlim(lo, hi + right_pad * (hi - lo))
    for i, value in enumerate(means):
        ax.text(
            0.99, i, fmt.format(value),
            transform=ax.get_yaxis_transform(),
            ha="right", va="center", fontsize=9, color="#111111",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.75),
        )


def model_results_bar(results_csv, title, out_name, baseline_names):
    results_csv = Path(results_csv)
    if not results_csv.exists():
        print(f"Skipping {out_name}: {results_csv} not found")
        return

    results = pd.read_csv(results_csv)
    summary = _model_summary(results_csv)

    fig, (ax_mae, ax_r2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(title, fontsize=14)

    s_mae = summary.sort_values("avg_mae")
    _clean_panel(
        ax_mae, s_mae["model"].tolist(), s_mae["avg_mae"].to_numpy(),
        s_mae["std_mae"].to_numpy(), _fold_values(results, "avg_mae"),
        _bar_colors(s_mae["model"], baseline_names),
        "Average MAE (lower is better)", "Error",
    )

    s_r2 = summary.sort_values("avg_r2", ascending=False)
    _clean_panel(
        ax_r2, s_r2["model"].tolist(), s_r2["avg_r2"].to_numpy(),
        s_r2["std_r2"].to_numpy(), _fold_values(results, "overall_r2"),
        _bar_colors(s_r2["model"], baseline_names),
        "Average R2 (higher is better)", "Generalization",
    )
    ax_r2.axvline(0, color="black", linewidth=0.8, zorder=1)

    fig.text(
        0.5, 0.015,
        "Bars = mean across held-out runs; whiskers = std; dots = individual runs.",
        ha="center", fontsize=9, color="#555555",
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.94])
    out = PLOT_PATH / out_name
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Saved {out}")


def tank_model_results_bar(results_csv, out_name):
    results_csv = Path(results_csv)
    if not results_csv.exists():
        print(f"Skipping {out_name}: {results_csv} not found")
        return

    results = pd.read_csv(results_csv)
    baseline_names = {"Mean Predictor", "Persistence (no change)"}
    summary = _model_summary(results_csv)

    fig, (ax_mae, ax_zoom, ax_r2) = plt.subplots(
        1, 3, figsize=(15, 5), gridspec_kw={"width_ratios": [1.1, 0.9, 1.1]}
    )
    fig.suptitle("Tank Forecasting (+10s) - Leave-One-Run-Out Validation", fontsize=14)

    s_mae = summary.sort_values("avg_mae")
    _clean_panel(
        ax_mae, s_mae["model"].tolist(), s_mae["avg_mae"].to_numpy(),
        s_mae["std_mae"].to_numpy(), _fold_values(results, "avg_mae"),
        _bar_colors(s_mae["model"], baseline_names),
        "Average MAE", "All models",
    )

    zoom_models = ["Persistence (no change)", "Linear Regression", "Ridge Regression"]
    zoom = (
        summary[summary["model"].isin(zoom_models)]
        .set_index("model")
        .loc[zoom_models]
        .reset_index()
    )
    zoom_folds = {
        model: values
        for model, values in _fold_values(results, "avg_mae").items()
        if model in zoom_models
    }
    _clean_panel(
        ax_zoom, zoom["model"].tolist(), zoom["avg_mae"].to_numpy(),
        zoom["std_mae"].to_numpy(), zoom_folds,
        _bar_colors(zoom["model"], baseline_names),
        "Average MAE", "Zoom: near-baseline models", right_pad=0.30,
    )
    ax_zoom.set_xlim(left=0)

    s_r2 = summary.sort_values("avg_r2", ascending=False)
    _clean_panel(
        ax_r2, s_r2["model"].tolist(), s_r2["avg_r2"].to_numpy(),
        s_r2["std_r2"].to_numpy(), _fold_values(results, "overall_r2"),
        _bar_colors(s_r2["model"], baseline_names),
        "Average R2", "Generalization",
    )
    ax_r2.axvline(0, color="black", linewidth=0.8, zorder=1)

    fig.text(
        0.5, 0.015,
        "Persistence (grey) = predict no change. Regression matches but does not beat it "
        "-> short-horizon tank state is persistence-dominated.",
        ha="center", fontsize=9, color="#555555",
    )
    plt.tight_layout(rect=[0, 0.04, 1, 0.93])
    out = PLOT_PATH / out_name
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Saved {out}")


def flow_prediction_overlay(run_name=FLOW_OVERLAY_RUN):
    csv_path = Path(EXPORT_DIR) / "clean_esp32_model_data.csv"
    if not csv_path.exists():
        print(f"Skipping flow overlay: {csv_path} not found")
        return

    data = pd.read_csv(csv_path)
    required_columns = ["run_name", "timestamp"] + FLOW_FEATURE_COLUMNS + FLOW_TARGET_COLUMNS
    missing_columns = [column for column in required_columns if column not in data.columns]
    if missing_columns:
        print(f"Skipping flow overlay: missing columns {', '.join(missing_columns)}")
        return

    available_runs = sorted(data["run_name"].dropna().unique().tolist())
    if run_name not in available_runs:
        run_name = available_runs[-1]

    train_data = data[data["run_name"] != run_name].copy()
    test_data = data[data["run_name"] == run_name].copy()
    if train_data.empty or test_data.empty:
        print(f"Skipping flow overlay: not enough data for {run_name}")
        return

    test_data = test_data.sort_values("timestamp").reset_index(drop=True)
    model = RandomForestRegressor(n_estimators=200, random_state=42, min_samples_leaf=5)
    model.fit(train_data[FLOW_FEATURE_COLUMNS], train_data[FLOW_TARGET_COLUMNS])
    predictions = pd.DataFrame(
        model.predict(test_data[FLOW_FEATURE_COLUMNS]),
        columns=FLOW_TARGET_COLUMNS,
    )

    t = test_data["timestamp"] - test_data["timestamp"].min()
    channels = [
        ("flow_p1", "Pump 1 flow"),
        ("flow_p2", "Pump 2 flow"),
        ("flow_outlet", "Outlet flow"),
    ]

    fig, axes = plt.subplots(len(channels), 1, figsize=(12, 7.5), sharex=True)
    fig.suptitle(
        f"Random Forest Flow Prediction on Held-Out Run - {run_name}",
        fontsize=14,
    )

    for ax, (column, label) in zip(axes, channels):
        ax.plot(t, test_data[column], color="#1f1f1f", linewidth=1.2, label="Measured")
        ax.plot(t, predictions[column], color=BAR_BLUE, linewidth=1.2, label="Predicted")
        channel_r2 = r2_score(test_data[column], predictions[column])
        ax.set_ylabel(label)
        ax.set_title(f"{label} (R2={channel_r2:.2f})", fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper right", fontsize=8)

    axes[-1].set_xlabel("Time since held-out run start (s)")
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    out = PLOT_PATH / f"flow_prediction_overlay_{run_name}.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Saved {out}")


def flow_feature_importance(out_name="flow_feature_importance.png"):
    """Which control channels drive the flow response (RF importance)."""
    try:
        from scripts.models.flow_response_model import (
            CLEAN_RUNS,
            FEATURE_COLUMNS,
            TARGET_COLUMNS,
        )
    except Exception as error:  # pragma: no cover - defensive
        print(f"Skipping feature importance: {error}")
        return

    csv_path = Path(EXPORT_DIR) / "clean_esp32_model_data.csv"
    if not csv_path.exists():
        print(f"Skipping feature importance: {csv_path} not found")
        return

    data = pd.read_csv(csv_path)
    data = data[data["run_name"].isin(CLEAN_RUNS)].dropna(subset=FEATURE_COLUMNS + TARGET_COLUMNS)
    if data.empty:
        print("Skipping feature importance: no rows")
        return

    model = RandomForestRegressor(n_estimators=200, random_state=42, min_samples_leaf=5)
    model.fit(data[FEATURE_COLUMNS], data[TARGET_COLUMNS])
    importance = pd.Series(model.feature_importances_, index=FEATURE_COLUMNS).sort_values()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(importance.index, importance.values, color=BAR_BLUE, height=0.62)
    for i, value in enumerate(importance.values):
        ax.text(value, i, f" {value:.2f}", va="center", fontsize=9)
    ax.set_xlim(0, importance.max() * 1.18)
    ax.set_xlabel("Random forest feature importance")
    ax.set_title("What drives the flow response?\n(RF importance, trained on all clean runs)")
    ax.grid(axis="x", alpha=0.18)
    plt.tight_layout()
    out = PLOT_PATH / out_name
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Saved {out}")


def architecture_diagram():
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.set_title("Water-Treatment Testbed Digital Twin - Data & Model Backend", fontsize=14)

    def box(x, y, w, h, text, color):
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0.04,rounding_size=0.12",
                facecolor=color, edgecolor="#333333", linewidth=1.2,
            )
        )
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9.5)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(
            FancyArrowPatch(
                (x1, y1), (x2, y2),
                arrowstyle="-|>", mutation_scale=16,
                color="#555555", linewidth=1.4,
            )
        )

    sensor = "#dcedf5"
    store = "#e8e0f2"
    proc = "#dff0e2"
    ml = "#fbe6cc"

    box(0.3, 4.4, 2.6, 1.4, "Arduino UNO\nultrasonic tank\nsensors", sensor)
    box(0.3, 1.0, 2.6, 1.4, "ESP32 / MATLAB\npump, valve,\nflow logs (.mat)", sensor)
    box(3.6, 2.7, 2.4, 1.6, "SQLite\nwater_testbed.db\nrun-indexed\n29K+ rows", store)
    box(6.6, 4.4, 2.4, 1.4, "Wall-clock sync\n-> merged 1-s\ntime-series", proc)
    box(6.6, 1.0, 2.4, 1.4, "Cleaning +\nanomaly / data-\nquality flags", proc)
    box(9.5, 4.4, 2.2, 1.4, "Flow-response\nmodel (LORO)", ml)
    box(9.5, 1.0, 2.2, 1.4, "Tank forecast\n(LORO, vs\npersistence)", ml)
    box(9.5, 2.75, 2.2, 1.2, "Plots, reports,\nsummary tables", proc)

    arrow(2.9, 5.1, 3.6, 3.9)
    arrow(2.9, 1.7, 3.6, 3.1)
    arrow(6.0, 3.9, 6.6, 5.0)
    arrow(6.0, 3.1, 6.6, 1.8)
    arrow(6.0, 3.5, 9.5, 3.4)
    arrow(9.0, 5.1, 9.5, 5.1)
    arrow(9.0, 4.9, 9.5, 1.9)

    ax.text(
        6.0, 0.3,
        "Future work: live MQTT -> ProtoTwin 3-D visualization",
        ha="center", fontsize=9, style="italic", color="#777777",
    )

    out = PLOT_PATH / "architecture_diagram.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"Saved {out}")


def main():
    synchronized_timeline()
    model_results_bar(
        Path(ANALYSIS_DIR) / "flow_response_model_results.csv",
        "Flow-Response Model - Leave-One-Run-Out Validation",
        "flow_response_model_results.png",
        baseline_names={"Mean Predictor"},
    )
    flow_prediction_overlay()
    flow_feature_importance()
    tank_model_results_bar(
        Path(ANALYSIS_DIR) / "tank_forecasting_model_results.csv",
        "tank_forecasting_model_results.png",
    )
    architecture_diagram()


if __name__ == "__main__":
    main()
