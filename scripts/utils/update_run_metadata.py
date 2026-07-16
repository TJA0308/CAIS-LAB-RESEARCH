# Optional helper for updating an existing run's metadata.
# Change the values below if you need to clean up another run name.

import sqlite3
from config import DB_NAME

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

cur.execute("""
UPDATE runs
SET run_type = ?,
    notes = ?
WHERE run_name = ?
""", (
    "combined_arduino_esp32_run",
    "Combined run with Arduino tank sensors and ESP32/MATLAB pump-valve-flow logging",
    "combined_run_001"
))

conn.commit()
conn.close()

print("Updated metadata for combined_run_001")
