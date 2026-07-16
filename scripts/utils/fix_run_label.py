import sqlite3
import pandas as pd
from config import DB_NAME

START = "2026-07-15T13:56:08"
END = "2026-07-15T14:10:55"
OLD_RUN = "full_cycle_run_004"
NEW_RUN = "pump_pwm_sweep_run_002"

conn = sqlite3.connect(DB_NAME)

print("Before relabel:")
q = """
SELECT run_name, COUNT(*) AS n
FROM arduino_tank_data
WHERE timestamp >= ? AND timestamp <= ?
GROUP BY run_name
ORDER BY run_name
"""
print(pd.read_sql_query(q, conn, params=[START, END]).to_string(index=False))

cur = conn.cursor()
cur.execute(
    """
    UPDATE arduino_tank_data
    SET run_name = ?
    WHERE timestamp >= ?
      AND timestamp <= ?
      AND run_name = ?
    """,
    [NEW_RUN, START, END, OLD_RUN],
)

print("\nRows relabeled:", cur.rowcount)
conn.commit()

print("\nAfter relabel:")
print(pd.read_sql_query(q, conn, params=[START, END]).to_string(index=False))

conn.close()