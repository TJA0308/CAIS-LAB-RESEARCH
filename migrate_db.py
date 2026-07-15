# One-time migration helper.
# Only use this if an older water_testbed.db does not have run_name in arduino_tank_data.

import sqlite3
from config import DB_NAME

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

try:
    cur.execute("ALTER TABLE arduino_tank_data ADD COLUMN run_name TEXT")
    print("Added run_name column to arduino_tank_data")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e).lower():
        print("run_name already exists")
    else:
        raise

cur.execute("""
UPDATE arduino_tank_data
SET run_name = 'arduino_test_001'
WHERE run_name IS NULL
""")

conn.commit()
conn.close()

print("Migration complete")
