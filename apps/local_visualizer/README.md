# Local Water System Visualizer

This is a standalone local prototype. It does not write to SQLite and does not
change the existing database architecture. It reads the existing merged CSV files:

```text
exports/*_merged_timeseries.csv
```

Run it from the repository root:

```powershell
python apps/local_visualizer/server.py
```

Then open:

```text
http://127.0.0.1:8765
```

What it shows:

- A browser-based schematic of the recorded water-system layout.
- Raw/ground, treated, and tower tank sensor readings as animated vertical bars.
- Pump command state and active pipe highlighting.
- Three tower outlet branches with V2, V3, and V4 routed back to ground/output.
- Recorded flow-channel values.
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
