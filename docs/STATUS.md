# Project Status

## Working (backend intelligence layer)
- SQLite schema + run-indexed experiment tracking (~15.4K controller, ~14.1K tank rows)
- Arduino tank logging; MATLAB .mat import
- Wall-clock synchronization -> merged 1-second time-series (6 runs)
- Auditable cleaning (raw vs clean, per-run drop logging)
- Time-series plotting, rule-based anomaly/data-quality detection, run/stage summaries
- Flow-response model: 7-run leave-one-run-out, RF R2 0.77 / MAE 1.75 (generalizes)
- Tank forecasting: 6-run LORO, honestly reported vs a persistence baseline
- Tank horizon sweep: 10/30/60/120s evaluated; persistence remains best by MAE
- Poster figures: architecture, synchronized timeline, flow overlay, model charts, feature importance

## Explored (validated, ready to fold in later)
- Temporal features improve the flow model (RF R2 0.77 -> 0.83); see
  `scripts/models/flow_temporal_features.py`
- Tank forecasting cannot beat persistence on current data via longer horizons
  -> a data-coverage/design limit, not a bug

## Poster-ready runs
- full_cycle_run_004 (hero), full_cycle_run_002, valve_routing_run_001, pump_pwm_sweep_run_001

## Exclude from results
- config_test_001 (duplicate of combined_run_001), arduino_test_001 (orphan)

## ProtoTwin / digital-twin visualization (FUTURE WORK)
- Status: the live ProtoTwin 3-D / TypeScript frontend is NOT working yet.
- What is done: the backend already emits a ProtoTwin-ready 1-second JSON state
  stream. `scripts/visualization/prototwin_stream.py` replays a merged run to an MQTT topic
  (dry-run by default; `--broker` to publish). This proves the integration path.
- Minimal next step: subscribe one ProtoTwin element (e.g., a single tank level)
  to `water_testbed/state` and drive it from a real run before attempting the full scene.
- Framing: the digital-twin *backend* (synchronized state history + validated models)
  works; the visualization *frontend* is the remaining layer.

## Remaining / next
- (Optional) fold temporal features into the main flow model on merged data
- (Optional) sensor -> volume calibration; delta tank modeling
- Collect 1-2 targeted runs: one long combined pump+valve run; one protocol replicate
- ProtoTwin: wire one live element via MQTT
- Commit + push after tomorrow's meeting
