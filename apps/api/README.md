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
