# Water-Treatment Testbed Data Pipeline

This repository contains the backend software pipeline for a laboratory-scale
water-treatment testbed. It stores raw experiment data in SQLite, imports
ESP32/MATLAB controller logs, supports Arduino ultrasonic tank logging,
synchronizes independent hardware streams into one-second datasets, generates
analysis outputs, and provides a read-only browser replay interface.

The project is focused on reproducible data collection, storage,
synchronization, data-quality review, and visualization. It does not modify raw
database records during cleaning or analysis.

## Project Summary

Laboratory water-treatment experiments produce data from separate hardware and
logging systems. This repository connects those records into a run-indexed data
pipeline:

```text
Sensors / Logs
    |
    +--> Arduino ultrasonic tank readings
    |        -> SQLite: arduino_tank_data
    |
    +--> ESP32/MATLAB pump, valve, and controller-side channel logs
             -> SQLite: esp32_matlab_data

SQLite raw database
    -> synchronized one-second CSVs
    -> cleaning summaries
    -> anomaly/data-quality reports
    -> run and stage summaries
    -> plots
    -> read-only FastAPI service
    -> browser replay UI
```

## Quick Start: Replay Existing Runs

Install the API dependencies:

```powershell
pip install -r requirements-api.txt
```

Start the read-only FastAPI service:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, start the replay interface:

```powershell
python apps/local_visualizer/server.py
```

Open the visualizer:

```text
http://127.0.0.1:8765
```

The replay UI loads from FastAPI first and falls back to the local CSV server if
FastAPI is unavailable. Both paths are read-only.

FastAPI docs:

```text
http://127.0.0.1:8000/docs
```

## Repository Structure

```text
apps/
  api/                  Read-only FastAPI service
  local_visualizer/      Browser replay interface
analysis/                Generated summaries and data-quality reports
data/
  db/                    SQLite databases
  raw/                   Raw MATLAB .mat files
docs/                    Project status notes
exports/                 Exported CSV datasets
plots/                   Generated visualizations
scripts/
  ingest/                Database setup, .mat import, Arduino logging
  processing/            Time synchronization and clean dataset creation
  analysis/              Summaries, anomaly reports, run comparisons
  models/                Exploratory characterization scripts
  visualization/         Plotting and report figure generation
  utils/                 Inspection and maintenance helpers
```

## Database

Default database:

```text
data/db/water_testbed.db
```

Main tables:

- `runs`: experiment metadata keyed by `run_name`.
- `esp32_matlab_data`: controller-side time series with pump commands, valve
  states, and recorded controller-side channel readings.
- `arduino_tank_data`: Arduino ultrasonic tank readings and raw serial lines.

Tank mapping:

```text
tank1 = tower
tank2 = treated
tank3 = raw
```

The database stores raw readings. Cleaning and analysis scripts write separate
CSV outputs and do not delete raw rows.

## Main Pipeline Commands

Set the active run in `config.py`:

```python
RUN_NAME = "full_cycle_run_004"
MAT_FILE = str(RAW_DATA_DIR / "full_cycle_run_004.mat")
```

Typical workflow for one run:

```powershell
python -m scripts.ingest.setup_db
python -m scripts.ingest.mat_to_sqlite
python -m scripts.ingest.arduino_logger
python -m scripts.processing.merge_timeseries
python -m scripts.visualization.plot_run
python -m scripts.analysis.detect_anomalies
python -m scripts.analysis.summarize_anomalies
python -m scripts.analysis.run_report
python -m scripts.analysis.stage_summary
```

After multiple runs are available:

```powershell
python -m scripts.analysis.compare_runs
python -m scripts.analysis.merged_dataset_summary
python -m scripts.processing.create_clean_model_datasets
python -m scripts.visualization.make_report_figures
```

Exploratory characterization scripts are available in `scripts/models/`, but
their outputs should be treated as preliminary analysis rather than validated
physical models.

## Read-Only API

The FastAPI service exposes existing data products without changing the database
or generated files.

Run:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

Example requests:

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/runs
curl.exe http://127.0.0.1:8000/runs/full_cycle_run_004
curl.exe "http://127.0.0.1:8000/runs/full_cycle_run_004/timeseries?start_s=60&end_s=65&limit=3"
```

Endpoints:

- `GET /health`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/timeseries`

The API validates `run_id` against `runs.run_name` before constructing a merged
CSV path. Some database runs do not currently have merged CSVs; those runs will
return a clear `404` from the timeseries endpoint.

## Browser Replay Interface

The local replay interface is in:

```text
apps/local_visualizer/
```

Run:

```powershell
python apps/local_visualizer/server.py
```

Open:

```text
http://127.0.0.1:8765
```

The visualizer shows:

- recorded pump command states,
- valve command states,
- raw storage, treated storage, and tower ultrasonic tank readings,
- controller-side channel values,
- active command paths on the testbed schematic,
- tank sensor traces over time,
- sensor-jump warnings for large adjacent tank-reading changes.

The visualizer is replay-only. It does not control hardware, poll live sensors,
or write to SQLite.

## Outputs

Database:

- `data/db/water_testbed.db`

Raw exported tables:

- `exports/esp32_matlab_data.csv`: export of controller-side records from
  `esp32_matlab_data`, including pump commands, valve states, timestamps, and
  recorded controller-side `flow_*` channel values.
- `exports/arduino_tank_data.csv`: export of Arduino tank readings from
  `arduino_tank_data`, including raw serial lines and ultrasonic readings.
- `exports/esp32_summary_by_run.csv`, `exports/arduino_summary_by_run.csv`,
  and `exports/arduino_summary_mapped_by_run.csv`: row-count and run-level
  summaries for exported raw records.

Merged one-second datasets:

- `exports/*_merged_timeseries.csv`

These are synchronized replay datasets keyed by `run_name` and `t_seconds`.
They combine pump commands, valve states, controller-side channel values, and
tank readings onto a shared one-second timeline where both data streams are
available.

Clean analysis datasets:

- `exports/clean_esp32_model_data.csv`
- `exports/clean_tank_forecasting_data.csv`

These files are derived analysis copies. They do not replace or modify raw
database records.

Analysis outputs:

- `analysis/*_anomaly_report.csv`
- `analysis/*_anomaly_summary.csv`
- `analysis/*_run_report.txt`
- `analysis/*_stage_summary.csv`
- `analysis/cleaning_summary.csv`
- `analysis/run_comparison_summary.csv`
- `analysis/merged_dataset_summary.csv`

Plots:

- `plots/*_flow_timeline.png`
- `plots/*_pump_timeline.png`
- `plots/*_valve_timeline.png`
- `plots/*_tank_timeline.png`
- `plots/*_combined_timeline.png`
- `plots/architecture_diagram.png`
- `plots/synchronized_timeline_full_cycle_run_004.png`

The historical `flow` filename prefix is retained for compatibility with
existing scripts, but these plots should be interpreted as controller-side
channel timelines unless independent physical flow sensors are added.

## Verification

Run the current test suite:

```powershell
python -m pytest
```

Check frontend syntax:

```powershell
node --check apps/local_visualizer/static/app.js
```

## Scope And Limitations

- Arduino `"Error"` readings are preserved in the database and handled
  downstream.
- Ultrasonic tank readings are raw sensor distances, not calibrated tank
  volumes.
- `flow_*` fields are recorded controller-side channels from the ESP32/MATLAB
  logs. They are not calibrated physical flow measurements and should not be
  described as flow-sensor data.
- The replay UI is read-only and uses recorded runs only.
- This repository does not implement a validated digital twin or an autonomous
  controller.

## Future Work

- Calibrate ultrasonic tank readings against measured water height or volume.
- Validate a first-principles tank model using inflow, outflow, elapsed time,
  and tank geometry.
- Collect replicated controlled runs for cross-run validation.
- Add live visualization only after the read-only replay workflow is stable.
- Compare exploratory learned models against first-principles baselines only
  after sensor calibration and physical inflow/outflow measurements are
  available.
