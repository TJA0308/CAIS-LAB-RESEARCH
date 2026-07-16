# Poster Notes

## Recommended Poster Focus

Main claim:

> We built a reproducible backend for a water-treatment testbed that stores raw
> experiment data, synchronizes independent hardware streams, creates clean
> model-ready datasets, and supports visual analytics for future digital-twin work.

This is the safest poster framing because it is directly supported by the code and
data products in this repository.

## What To Emphasize

- Data collection architecture: Arduino tank sensors plus ESP32/MATLAB controller logs.
- SQLite experiment database with run-indexed raw data.
- Wall-clock synchronization into 1-second merged time-series CSVs.
- Auditable cleaning that preserves raw database records.
- Poster-ready plots and summaries generated from the same pipeline.
- Initial ML work as exploratory backend validation and forecasting analysis.

## Suggested Poster Sections

1. Problem and goal
   - A physical water-treatment testbed produces separate tank, pump, valve, and
     flow-channel streams.
   - The goal is to create a reproducible backend for analysis and future digital-twin
     visualization.

2. Backend architecture
   - Show `plots/architecture_diagram.png`.
   - Explain how `.mat` controller logs and Arduino readings enter SQLite.

3. Synchronized system data
   - Show `plots/synchronized_timeline_full_cycle_run_004.png`.
   - Use this as the strongest evidence that the backend integrates the system state.

4. Data quality and cleaning
   - Mention raw data is preserved.
   - Cleaning outputs are separate CSV files.
   - `analysis/cleaning_summary.csv` logs rows removed and why.

5. Exploratory models
   - Flow-channel response modeling predicts recorded response channels from controls.
   - Do not overclaim calibrated physical flow unless the lab confirms the readings.
   - Tank forecasting is the more relevant digital-twin direction, but current
     short-horizon results are persistence-dominated.

6. Future work
   - Local frontend/dashboard that reads SQLite and animates tank levels.
   - ProtoTwin/MQTT visualization layer.
   - Tank forecast horizons, delta targets, and future control-conditioned rollouts.
   - Sensor-to-volume calibration.
   - More independent and replicated runs.

## ML Framing

Flow-response model:

- Useful as an exploratory backend validation task.
- Best current static Random Forest result: about R2 0.77 and MAE 1.75 across 7
  leave-one-run-out folds.
- Separate temporal-feature analysis on merged runs improves Random Forest from
  R2 0.757 to 0.827 and MAE 1.472 to 1.145.
- Phrase carefully: "recorded flow-channel response", not "true physical flow",
  unless the sensor/channel calibration is validated.

Tank forecasting:

- Better aligned with the lab's digital-twin goal because it predicts tank-level
  evolution.
- 10-second forecasting is dominated by persistence because tank levels change slowly.
- Persistence baseline MAE is about 6.10; Linear/Ridge are about 6.88 to 6.90.
- A horizon sweep at 10, 30, 60, and 120 seconds still shows persistence as the
  best MAE baseline on current data. The gap increases at longer horizons, which
  suggests the current runs do not contain enough repeated, in-distribution tank
  dynamics for learned models to generalize.
- This is a useful finding: future work needs longer horizons, delta targets,
  future control schedules, or more replicated protocols.

## Plots To Use

Primary:

- `plots/architecture_diagram.png`
- `plots/synchronized_timeline_full_cycle_run_004.png`

Optional / supporting:

- `plots/flow_response_model_results.png`
- `plots/flow_prediction_overlay_full_cycle_run_002.png`
- `plots/tank_forecasting_model_results.png`
- `plots/flow_feature_importance.png`

## Suggested Captions

Architecture:

> Run-indexed backend architecture: Arduino tank readings and ESP32/MATLAB controller
> logs are stored in SQLite, synchronized to 1-second time series, and exported for
> analysis, cleaning, plotting, and exploratory forecasting.

Synchronized timeline:

> Wall-clock synchronized run showing pump commands, valve states, recorded flow-channel
> response, and raw ultrasonic tank readings on one shared 1-second axis.

Tank forecasting:

> Short-horizon tank forecasting is persistence-dominated: current tank reading is a
> strong 10-second baseline, motivating longer-horizon and control-conditioned models.

Flow exploratory model:

> Exploratory model predicting recorded flow-channel response from pump and valve
> commands; temporal control history improves held-out performance.
