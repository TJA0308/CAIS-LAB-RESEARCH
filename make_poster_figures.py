"""
Generate poster / presentation figures from existing pipeline outputs.

Produces four PNGs in plots/:
  1. synchronized_timeline_<run>.png  - pump/valve/flow/tank on one wall-clock axis
  2. flow_response_model_results.png  - LORO MAE and R2 by model
  3. tank_forecasting_model_results.png - LORO MAE and R2 by model (with persistence)
  4. architecture_diagram.png         - data-flow / system architecture

Run after flow_response_model.py and tank_forecasting_model.py.
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

    axes[3].plot(t, data["tower"], label="Tower")
    axes[3].plot(t, data["treated"], label="Treated")
    axes[3].plot(t, data["raw"], label="Raw")
    axes[3].set_ylabel("Tank reading\n(raw ultrasonic)")
    axes[3].set_xlabel("Time since run start (s, wall-clock synchronized)")
    axes[3].set_title("Tank Levels")

    for ax in axes:
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out = PLOT_PATH / f"synchronized_timeline_{run_name}.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"Saved {out}")


def _model_summary(results_csv):
    results = pd.read_csv(results_csv)
    summary = (
        results.groupby("model", as_index=False)
        .agg(
            avg_mae=("avg_mae", "mean"),
            std_mae=("avg_mae", "std"),
            avg_r2=("overall_r2", "mean"),
            std_r2=("overall_r2", "std"),
        )
    )
    summary[["std_mae", "std_r2"]] = summary[["std_mae", "std_r2"]].fillna(0)
    return summary


def _dot_offsets(count):
    if count <= 1:
        return np.array([0.0])
    return np.linspace(-0.18, 0.18, count)


def _bar_colors(models, baseline_names):
    return ["#b0b0b0" if model in baseline_names else "#2b7bba" for model in models]


def _add_fold_dots(ax, results, metric_column, ordered_models):
    for y, model in enumerate(ordered_models):
        values = results.loc[results["model"] == model, metric_column].to_numpy()
        if values.size == 0:
            continue
        offsets = _dot_offsets(values.size)
        ax.scatter(
            values,
            y + offsets,
            s=22,
            color="#1f1f1f",
            alpha=0.72,
            zorder=3,
            linewidth=0,
        )


def _format_r2_axis(ax, values):
    r2_min = min(0, float(values.min()))
    r2_max = max(0, float(values.max()))
    r2_range = r2_max - r2_min or 1
    ax.set_xlim(r2_min - 0.12 * r2_range, r2_max + 0.16 * r2_range)
    return r2_range


def model_results_bar(results_csv, title, out_name, baseline_names):
    results_csv = Path(results_csv)
    if not results_csv.exists():
        print(f"Skipping {out_name}: {results_csv} not found")
        return

    results = pd.read_csv(results_csv)
    summary = _model_summary(results_csv).sort_values("avg_mae")
    models = summary["model"].tolist()
    colors = _bar_colors(models, baseline_names)

    fig, (ax_mae, ax_r2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle(title, fontsize=14)

    y_positions = np.arange(len(summary))
    ax_mae.barh(y_positions, summary["avg_mae"], color=colors)
    ax_mae.errorbar(
        summary["avg_mae"],
        y_positions,
        xerr=summary["std_mae"],
        fmt="none",
        ecolor="#303030",
        elinewidth=1,
        capsize=3,
        zorder=4,
    )
    _add_fold_dots(ax_mae, results, "avg_mae", models)
    ax_mae.set_yticks(y_positions)
    ax_mae.set_yticklabels(models)
    ax_mae.set_xlabel("Average MAE (lower is better)")
    ax_mae.invert_yaxis()
    for y, value in enumerate(summary["avg_mae"]):
        ax_mae.text(value, y, f" {value:.2f}", va="center", fontsize=9)

    r2_sorted = summary.sort_values("avg_r2", ascending=False)
    r2_models = r2_sorted["model"].tolist()
    r2_positions = np.arange(len(r2_sorted))
    r2_colors = _bar_colors(r2_models, baseline_names)
    ax_r2.barh(r2_positions, r2_sorted["avg_r2"], color=r2_colors)
    ax_r2.errorbar(
        r2_sorted["avg_r2"],
        r2_positions,
        xerr=r2_sorted["std_r2"],
        fmt="none",
        ecolor="#303030",
        elinewidth=1,
        capsize=3,
        zorder=4,
    )
    _add_fold_dots(ax_r2, results, "overall_r2", r2_models)
    ax_r2.set_yticks(r2_positions)
    ax_r2.set_yticklabels(r2_models)
    ax_r2.set_xlabel("Average R2 (higher is better)")
    ax_r2.axvline(0, color="black", linewidth=0.8)
    ax_r2.invert_yaxis()
    r2_range = _format_r2_axis(ax_r2, r2_sorted["avg_r2"])
    for y, (model, value) in enumerate(zip(r2_sorted["model"], r2_sorted["avg_r2"])):
        if value >= 0:
            ax_r2.text(value + 0.02 * r2_range, y, f"{value:.2f}", va="center", fontsize=9)
        else:
            ax_r2.text(
                value / 2,
                y,
                f"{value:.2f}",
                va="center",
                ha="center",
                color="black" if model in baseline_names else "white",
                fontsize=9,
            )

    plt.tight_layout(rect=[0, 0, 1, 0.94])
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
    summary = _model_summary(results_csv).sort_values("avg_mae")
    models = summary["model"].tolist()
    y_positions = np.arange(len(summary))

    fig, (ax_mae, ax_zoom, ax_r2) = plt.subplots(
        1,
        3,
        figsize=(15, 5),
        gridspec_kw={"width_ratios": [1.15, 0.8, 1.15]},
    )
    fig.suptitle("Tank Forecasting (+10s) - Leave-One-Run-Out Validation", fontsize=14)

    ax_mae.barh(y_positions, summary["avg_mae"], color=_bar_colors(models, baseline_names))
    ax_mae.errorbar(
        summary["avg_mae"],
        y_positions,
        xerr=summary["std_mae"],
        fmt="none",
        ecolor="#303030",
        elinewidth=1,
        capsize=3,
        zorder=4,
    )
    _add_fold_dots(ax_mae, results, "avg_mae", models)
    ax_mae.set_yticks(y_positions)
    ax_mae.set_yticklabels(models)
    ax_mae.set_xlabel("Average MAE")
    ax_mae.set_title("All models")
    ax_mae.invert_yaxis()
    for y, value in enumerate(summary["avg_mae"]):
        ax_mae.text(value, y, f" {value:.2f}", va="center", fontsize=9)

    zoom_models = ["Persistence (no change)", "Linear Regression", "Ridge Regression"]
    zoom = summary[summary["model"].isin(zoom_models)].copy()
    zoom["order"] = zoom["model"].map({model: index for index, model in enumerate(zoom_models)})
    zoom = zoom.sort_values("order")
    zoom_positions = np.arange(len(zoom))
    ax_zoom.barh(
        zoom_positions,
        zoom["avg_mae"],
        color=_bar_colors(zoom["model"], baseline_names),
    )
    ax_zoom.errorbar(
        zoom["avg_mae"],
        zoom_positions,
        xerr=zoom["std_mae"],
        fmt="none",
        ecolor="#303030",
        elinewidth=1,
        capsize=3,
        zorder=4,
    )
    _add_fold_dots(ax_zoom, results, "avg_mae", zoom["model"].tolist())
    ax_zoom.set_yticks(zoom_positions)
    ax_zoom.set_yticklabels(zoom["model"])
    ax_zoom.set_xlabel("Average MAE")
    ax_zoom.set_title("Zoom: near-baseline models")
    ax_zoom.invert_yaxis()
    zoom_max = max(float(zoom["avg_mae"].max() + zoom["std_mae"].max()), 1)
    ax_zoom.set_xlim(0, zoom_max * 1.35)
    for y, value in enumerate(zoom["avg_mae"]):
        ax_zoom.text(value, y, f" {value:.2f}", va="center", fontsize=9)

    r2_sorted = summary.sort_values("avg_r2", ascending=False)
    r2_models = r2_sorted["model"].tolist()
    r2_positions = np.arange(len(r2_sorted))
    ax_r2.barh(r2_positions, r2_sorted["avg_r2"], color=_bar_colors(r2_models, baseline_names))
    ax_r2.errorbar(
        r2_sorted["avg_r2"],
        r2_positions,
        xerr=r2_sorted["std_r2"],
        fmt="none",
        ecolor="#303030",
        elinewidth=1,
        capsize=3,
        zorder=4,
    )
    _add_fold_dots(ax_r2, results, "overall_r2", r2_models)
    ax_r2.set_yticks(r2_positions)
    ax_r2.set_yticklabels(r2_models)
    ax_r2.set_xlabel("Average R2")
    ax_r2.set_title("Generalization")
    ax_r2.axvline(0, color="black", linewidth=0.8)
    ax_r2.invert_yaxis()
    r2_range = _format_r2_axis(ax_r2, r2_sorted["avg_r2"])
    for y, (model, value) in enumerate(zip(r2_sorted["model"], r2_sorted["avg_r2"])):
        if value >= 0:
            ax_r2.text(value + 0.02 * r2_range, y, f"{value:.2f}", va="center", fontsize=9)
        else:
            ax_r2.text(
                value / 2,
                y,
                f"{value:.2f}",
                va="center",
                ha="center",
                color="black" if model in baseline_names else "white",
                fontsize=9,
            )

    for ax in (ax_mae, ax_zoom, ax_r2):
        ax.grid(axis="x", alpha=0.2)

    plt.tight_layout(rect=[0, 0, 1, 0.93])
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
        ax.plot(t, predictions[column], color="#2b7bba", linewidth=1.2, label="Predicted")
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

    ax.text(6.0, 0.3,
            "Future work: live MQTT -> ProtoTwin 3-D visualization",
            ha="center", fontsize=9, style="italic", color="#777777")

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
    tank_model_results_bar(
        Path(ANALYSIS_DIR) / "tank_forecasting_model_results.csv",
        "tank_forecasting_model_results.png",
    )
    architecture_diagram()


if __name__ == "__main__":
    main()
