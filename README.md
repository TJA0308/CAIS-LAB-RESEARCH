# Water Treatment Digital Twin Data Pipeline

## Overview
This project builds a database-backed analytics pipeline for a water-treatment digital twin testbed. It integrates tank sensor readings, pump commands, valve states, and flow readings into a SQLite database for experiment tracking, visualization, and anomaly/data-quality analysis.

## System Pathway
- Pump 1: groundwater to raw tank
- Valve 1: raw tank to treated tank
- Pump 2: treated tank to tower tank
- Valves 2/3/4: tower tank to groundwater/output path

## Data Pipeline
Arduino tank sensors -> Python logger -> SQLite
ESP32/MATLAB pump/valve/flow logs -> .mat importer -> SQLite
SQLite -> plots, CSV summaries, anomaly reports, run reports

## Main Files
- config.py: shared run configuration
- setup_db.py: initializes database schema
- arduino_logger.py: logs tank sensor readings
- mat_to_sqlite.py: imports MATLAB .mat data
- check_db.py: validates database contents
- export_summary.py: exports CSV summaries
- plot_run.py: generates time-series plots
- detect_anomalies.py: flags data-quality and system-response events
- summarize_anomalies.py: summarizes anomaly counts and percentages
- compare_runs.py: compares runs
- stage_summary.py: summarizes staged operation windows

## Current Poster Run
- full_cycle_run_001
  - ESP32/MATLAB rows: 2143
  - Arduino tank rows: check latest output from check_db.py
  - Pumps reached 200 PWM
  - Captured multi-stage full-cycle operation

## Tank Mapping
- tank1 = tower
- tank2 = treated
- tank3 = raw

## Notes
Arduino ultrasonic readings may include intermittent `Error` values. These are preserved in the database and analyzed as data-quality events.