# Poster Notes

## Recommended Poster Focus

Main claim:

> This project built a reproducible data pipeline for a laboratory
> water-treatment testbed that stores raw experiment data, synchronizes
> independent hardware streams, exposes recorded runs through a read-only API,
> and supports visual replay and data-quality review.

This framing is directly supported by the repository and avoids overclaiming
model validation or autonomous control.

## What To Emphasize

- Data collection architecture: Arduino ultrasonic tank readings plus
  ESP32/MATLAB controller logs.
- SQLite database with raw, run-indexed experiment records.
- Synchronization into one-second merged CSV files.
- Cleaning and analysis outputs that preserve raw database records.
- Rule-based data-quality checks and run/stage summaries.
- Read-only FastAPI service for run metadata and synchronized timeseries access.
- Browser replay interface for recorded experimental runs.

## Suggested Poster Sections

1. Problem and goal
   - Laboratory testbed data is produced by separate sensors, controllers, and
     logging systems.
   - The goal is to make recorded runs easier to synchronize, inspect, compare,
     and reuse.

2. System architecture
   - Show the pipeline from sensors/logs to SQLite, merged CSVs, FastAPI, and
     replay UI.

3. Data pipeline
   - Explain `.mat` import, Arduino logging, run identifiers, and raw database
     preservation.

4. Synchronized system data
   - Show a one-second synchronized timeline for `full_cycle_run_004`.

5. Data-quality review
   - Show cleaning summaries, anomaly/data-quality rules, and run/stage
     summaries.

6. Replay interface
   - Show the browser visualizer as a read-only recorded-run replay tool.

7. Limitations and future work
   - Sensor calibration, first-principles tank modeling, replicated runs, and
     live visualization remain future work.

## Preliminary Analysis Framing

If modeling outputs are mentioned, use cautious wording:

- Existing flow-response scripts estimate recorded controller-side `flow_*`
  channel values from pump PWM and valve command histories.
- This is preliminary open-loop input-output characterization, not calibrated
  physical flow prediction.
- Existing tank-forecasting results are exploratory and do not validate a
  predictive digital twin.
- Short-horizon tank forecasting should be compared against persistence and
  first-principles mass-balance models before stronger claims are made.

Avoid:

- "AI-powered controller"
- "validated predictive digital twin"
- "physical flow prediction"
- "autonomous control"
- "validated model"

## Strongest Visuals

Primary:

- `plots/architecture_diagram.png`
- `plots/synchronized_timeline_full_cycle_run_004.png`
- Browser replay interface screenshot, if captured after running the local demo.

Supporting:

- `plots/full_cycle_run_004_combined_timeline.png`
- `analysis/cleaning_summary.csv`
- `analysis/run_comparison_summary.csv`
- `plots/tank_forecasting_model_results.png`, only if framed as exploratory.
- `plots/flow_response_model_results.png`, only if framed as exploratory.

## Poster-Safe Captions

Architecture:

> Run-indexed data pipeline for the water-treatment testbed: ESP32/MATLAB
> controller logs and Arduino ultrasonic tank readings are stored in SQLite,
> synchronized into one-second CSVs, and exposed through a read-only API and
> recorded-run replay interface.

Synchronized timeline:

> One-second synchronized run showing pump commands, valve states, recorded
> controller-side channel values, and raw ultrasonic tank readings on a shared
> time axis.

Replay interface:

> Read-only browser replay of a recorded testbed run, showing command states,
> tank sensor readings, controller-side channel values, and active command paths.

Data-quality summary:

> Cleaning and data-quality outputs are generated as separate analysis files so
> raw SQLite records remain unchanged.

Exploratory flow characterization:

> Preliminary open-loop characterization estimating recorded controller-side
> channel values from pump and valve command histories.

Tank forecasting:

> Exploratory short-horizon tank forecasting did not establish a validated
> predictive model and motivates calibration and first-principles modeling.
