# Local Water System Visualizer

This is a local replay prototype. It does not write to SQLite and does not
change the existing database architecture. The browser frontend tries to load
run data from the read-only FastAPI service first:

```text
http://127.0.0.1:8000/runs
http://127.0.0.1:8000/runs/{run_id}/timeseries
```

If FastAPI is unavailable, it falls back to this visualizer server's existing
CSV endpoints, which read:

```text
exports/*_merged_timeseries.csv
```

Recommended local demo workflow:

```powershell
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, run the visualizer server from the repository root:

```powershell
python apps/local_visualizer/server.py
```

Then open:

```text
http://127.0.0.1:8765
```

What it shows:

- A browser-based schematic of the recorded testbed command layout.
- Raw storage, treated storage, and tower tank sensor readings as animated
  vertical bars.
- Pump command state and active pipe highlighting.
- Three tower outlet branches with V2, V3, and V4 routed back toward the
  groundwater reservoir.
- Recorded controller-side channel values.
- A replay timeline for each merged run.
- A simple "Running" vs "Idle" indicator based on pump/valve activity.
- A sensor-jump warning when tank readings change by more than 300 units between
  consecutive 1-second rows.

This is meant to test the local visualization idea before connecting to a live
database reader, MQTT stream, or ProtoTwin frontend.

Current scope:

- Replay only.
- No live database polling.
- No SQLite writes.
- No changes to the existing data collection architecture.
- Controller-side channel values are not displayed as calibrated physical flow
  measurements.
