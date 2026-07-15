import sqlite3
from pathlib import Path

import pandas as pd

from config import DB_NAME, RUN_NAME, ANALYSIS_DIR

INPUT_FILE = Path(ANALYSIS_DIR) / f"{RUN_NAME}_anomaly_report.csv"
OUTPUT_FILE = Path(ANALYSIS_DIR) / f"{RUN_NAME}_anomaly_summary.csv"

if not INPUT_FILE.exists():
    raise FileNotFoundError(f"Could not find anomaly report: {INPUT_FILE}")

df = pd.read_csv(INPUT_FILE)

conn = sqlite3.connect(DB_NAME)

esp32_rows = pd.read_sql_query(
    "SELECT COUNT(*) AS n FROM esp32_matlab_data WHERE run_name = ?",
    conn,
    params=(RUN_NAME,)
)["n"].iloc[0]

arduino_rows = pd.read_sql_query(
    "SELECT COUNT(*) AS n FROM arduino_tank_data WHERE run_name = ?",
    conn,
    params=(RUN_NAME,)
)["n"].iloc[0]

conn.close()

if df.empty:
    summary = pd.DataFrame(columns=["rule", "source", "count", "source_rows", "percent_of_source_rows"])
else:
    summary = (
        df.groupby(["rule", "source"])
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    def source_total(source):
        if source == "arduino":
            return arduino_rows
        if source == "esp32":
            return esp32_rows
        return None

    summary["source_rows"] = summary["source"].apply(source_total)
    summary["percent_of_source_rows"] = (summary["count"] / summary["source_rows"] * 100).round(2)

summary.to_csv(OUTPUT_FILE, index=False)

print("Anomaly summary:")
print(summary)
print(f"\nSaved to {OUTPUT_FILE}")
