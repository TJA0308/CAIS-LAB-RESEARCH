# Water-Treatment Testbed Backend

This repository contains the backend pipeline for a physical water-treatment testbed.
It stores experiment data in SQLite, imports ESP32/MATLAB controller logs, supports
Arduino tank logging, synchronizes the streams into 1-second time-series files, and
generates analysis outputs for reports and posters.

The raw database is preserved. Cleaning and model-ready datasets are written as
separate CSV files in `exports/`.

## What It Does

- Creates and manages a run-indexed SQLite database.
- Imports ESP32/MATLAB `.mat` files containing pump commands, valve states, and
  recorded flow-channel readings.
- Logs Arduino ultrasonic tank readings.
- Aligns ESP32/MATLAB and Arduino data onto a shared 1-second timeline.
- Exports merged CSVs for each run.
- Exposes run metadata and synchronized run data through a read-only FastAPI
  service for local tools.
- Generates plots, anomaly/data-quality reports, run summaries, and stage summaries.
- Builds cleaned CSV datasets for exploratory characterization work.
- Produces poster-ready figures from existing pipeline outputs.

## Architecture

```text
Arduino tank readings  --->  arduino_tank_data
                              |
                              v
                         SQLite database
                              ^
                              |
ESP32/MATLAB .mat logs ---> esp32_matlab_data

SQLite + wall-clock metadata
        |
        v
exports/*_merged_timeseries.csv
        |
        +--> analysis/*.csv / analysis/*.txt
        +--> plots/*.png
        +--> exports/clean_*_model_data.csv
        +--> FastAPI read-only API
                  |
                  v
             browser replay UI
```

Important files:

- `config.py`: current run settings, paths, serial settings, and display mappings.
- `scripts/ingest/`: database setup, `.mat` import, and Arduino logging.
- `scripts/processing/`: stream synchronization and clean model dataset creation.
- `scripts/analysis/`: run summaries, anomaly reports, and cross-run summaries.
- `scripts/models/`: exploratory flow and tank forecasting models.
- `scripts/visualization/`: run plots, poster figures, and local stream helpers.
- `apps/api/`: read-only FastAPI service for run metadata and synchronized CSVs.
- `apps/local_visualizer/`: browser replay UI for recorded runs.
- `scripts/utils/`: one-off inspection and metadata cleanup helpers.

## Database

Default database:

```text
data/db/water_testbed.db
```

Main tables:

- `runs`: run metadata keyed by `run_name`.
- `esp32_matlab_data`: controller-side time series with pump commands, valve states,
  and flow-channel readings.
- `arduino_tank_data`: Arduino ultrasonic tank readings and raw serial lines.

Tank mapping:

```text
tank1 = tower
tank2 = treated
tank3 = raw
```

The database stores raw readings. Rows are not deleted by the cleaning scripts.

## Operating The Pipeline

Set the current run in `config.py`:

```python
RUN_NAME = "full_cycle_run_004"
MAT_FILE = str(RAW_DATA_DIR / "full_cycle_run_004.mat")
```

Typical workflow for a run:

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
python -m scripts.models.flow_response_model
python -m scripts.models.tank_forecasting_model
python -m scripts.models.tank_forecasting_horizons
python -m scripts.visualization.make_poster_figures
```

## Read-Only API And Replay UI

Install the minimal API dependencies:

```powershell
pip install -r requirements-api.txt
```

Run the FastAPI service:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

The API docs are available at:

```text
http://127.0.0.1:8000/docs
```

Run the replay interface in a second terminal:

```powershell
python apps/local_visualizer/server.py
```

Then open:

```text
http://127.0.0.1:8765
```

The replay UI tries the FastAPI service first and falls back to the local CSV
server if FastAPI is unavailable. Both paths are read-only.

## Outputs

Database outputs:

- `data/db/water_testbed.db`

Merged run datasets:

- `exports/*_merged_timeseries.csv`

Clean model datasets:

- `exports/clean_esp32_model_data.csv`
- `exports/clean_tank_forecasting_data.csv`

Analysis outputs:

- `analysis/*_anomaly_report.csv`
- `analysis/*_anomaly_summary.csv`
- `analysis/*_run_report.txt`
- `analysis/*_stage_summary.csv`
- `analysis/cleaning_summary.csv`
- `analysis/flow_response_model_summary.txt`
- `analysis/tank_forecasting_model_summary.txt`
- `analysis/tank_forecasting_horizon_summary.txt`

Plot outputs:

- `plots/*_flow_timeline.png`
- `plots/*_pump_timeline.png`
- `plots/*_valve_timeline.png`
- `plots/*_tank_timeline.png`
- `plots/*_combined_timeline.png`
- `plots/architecture_diagram.png`
- `plots/synchronized_timeline_full_cycle_run_004.png`

## Notes

- Arduino `"Error"` readings are preserved in the database and handled downstream.
- Ultrasonic tank readings are raw sensor distances, not calibrated volumes.
- Flow-channel readings are treated as recorded controller-side response channels;
  they should not be overclaimed as calibrated physical flow unless validated.
- Poster/research framing is kept in `docs/POSTER_NOTES.md`.
