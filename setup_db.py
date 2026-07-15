import sqlite3

from config import DB_NAME

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS runs (
    run_name TEXT PRIMARY KEY,
    run_type TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS esp32_matlab_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_name TEXT,
    timestamp REAL,
    flow_p1 REAL,
    flow_p2 REAL,
    flow_valve1 REAL,
    flow_outlet REAL,
    pump1_pwm REAL,
    pump2_pwm REAL,
    valve1 INTEGER,
    valve2 INTEGER,
    valve3 INTEGER,
    valve4 INTEGER,
    FOREIGN KEY (run_name) REFERENCES runs(run_name)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS arduino_tank_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_name TEXT,
    timestamp TEXT,
    tank1 REAL,
    tank2 REAL,
    tank3 REAL,
    raw_line TEXT,
    FOREIGN KEY (run_name) REFERENCES runs(run_name)
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_esp32_run ON esp32_matlab_data(run_name)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_esp32_timestamp ON esp32_matlab_data(timestamp)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_arduino_run ON arduino_tank_data(run_name)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_arduino_timestamp ON arduino_tank_data(timestamp)")

conn.commit()
conn.close()

print(f"Database setup complete: {DB_NAME}")
print("Tables ready: runs, esp32_matlab_data, arduino_tank_data")