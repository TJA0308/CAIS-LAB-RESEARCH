# Project Status

## Working

- SQLite schema and run-indexed experiment tracking.
- ESP32/MATLAB `.mat` import for pump commands, valve states, timestamps, and
  recorded controller-side channel readings.
- Arduino ultrasonic tank-sensor logging with raw serial lines preserved.
- Synchronization of controller and tank streams into one-second merged CSVs for
  runs with available data.
- Separate clean analysis CSVs that preserve the raw database.
- Rule-based anomaly/data-quality reports.
- Run reports, stage summaries, merged dataset summaries, and cross-run
  comparisons.
- Generated plots and poster figures from existing pipeline outputs.
- Read-only FastAPI service for run metadata and synchronized timeseries access.
- Browser replay visualizer with FastAPI-first loading and local CSV fallback.

## Current Demo Run

- `full_cycle_run_004` is the strongest recorded-run demo:
  - merged CSV: `exports/full_cycle_run_004_merged_timeseries.csv`
  - row count: 971 one-second rows
  - time column: `t_seconds`
  - visualizer loads the run through FastAPI and local CSV fallback.

## Runs With Merged CSVs

- `full_cycle_run_002`
- `full_cycle_run_003`
- `full_cycle_run_004`
- `pump_pwm_sweep_run_001`
- `pump_pwm_sweep_run_002`
- `valve_routing_run_001`

## Database Runs Without Merged CSVs

These runs exist in `runs` but do not currently have matching
`exports/{run_name}_merged_timeseries.csv` files:

- `combined_run_001`
- `config_test_001`
- `full_cycle_run_001`
- `live_water_test_1`
- `pump1_onoff_run_002`

## Exploratory Analysis

- Existing scripts in `scripts/models/` contain preliminary input-output
  characterization and tank-forecasting experiments.
- These outputs should not be presented as a validated predictive digital twin,
  autonomous controller, or calibrated physical model.
- `flow_*` fields should be described as recorded controller-side channels, not
  calibrated physical flow measurements.
- Tank readings are raw ultrasonic distances, not calibrated volumes.

## Future Work

- Calibrate ultrasonic tank readings against measured water height or volume.
- Validate a first-principles tank model using inflow, outflow, elapsed time,
  and tank geometry.
- Collect replicated controlled runs for validation.
- Add live visualization only after the recorded-run workflow is stable.
- Compare exploratory learned models against first-principles baselines only
  after sensor and flow calibration are available.
