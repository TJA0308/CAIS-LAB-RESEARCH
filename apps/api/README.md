# Water Testbed Read-Only API

This FastAPI service exposes run metadata and synchronized one-second CSV outputs
from the existing water-testbed pipeline. It is read-only: it does not collect
data, clean data, modify SQLite, or change existing ingestion/processing scripts.

## Install

```powershell
pip install -r requirements-api.txt
```

## Run

From the repository root:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

Interactive API docs:

```text
http://127.0.0.1:8000/docs
```

## Test

```powershell
python -m pytest tests/test_api.py
```

## Examples

```powershell
curl.exe http://127.0.0.1:8000/health
curl.exe http://127.0.0.1:8000/runs
curl.exe http://127.0.0.1:8000/runs/full_cycle_run_004
curl.exe "http://127.0.0.1:8000/runs/full_cycle_run_004/timeseries?start_s=60&end_s=65&limit=3"
```

## Endpoints

- `GET /health`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/timeseries?start_s=0&end_s=120&limit=1000`

`run_id` is validated against the SQLite `runs.run_name` column before any
merged CSV path is constructed.

## Data Sources

- Run metadata and raw row counts come from `data/db/water_testbed.db`.
- Synchronized replay rows come from `exports/{run_id}_merged_timeseries.csv`.
- The API opens SQLite in read-only mode and does not modify database contents.

Some database runs do not currently have merged CSVs. Those runs will appear in
`GET /runs` with `has_timeseries=false`, and `/runs/{run_id}/timeseries` will
return a clear `404`.

## Response Notes

Timeseries rows use the same column names as the merged CSV files:

- `pump1_pwm`, `pump2_pwm`: recorded pump command values.
- `valve1` through `valve4`: recorded valve command states.
- `tower`, `treated`, `raw`: raw ultrasonic tank readings.
- `flow_p1`, `flow_p2`, `flow_valve1`, `flow_outlet`: controller-side channels
  from recorded ESP32/MATLAB logs.

The `flow_*` fields are not calibrated physical flow measurements and should
not be described as flow-sensor data.
