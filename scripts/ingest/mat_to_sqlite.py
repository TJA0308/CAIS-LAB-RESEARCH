import sqlite3
import numpy as np
from scipy.io import loadmat
from pathlib import Path

from config import DB_NAME, RUN_NAME, MAT_FILE

mat_path = Path(MAT_FILE)

if not mat_path.exists():
    raise FileNotFoundError(f"Could not find MAT file: {MAT_FILE}")

# Load MATLAB file
mat = loadmat(MAT_FILE, squeeze_me=True, struct_as_record=False)

# Accept both possible MATLAB variable names
if "serialDataStruct" in mat:
    s = mat["serialDataStruct"]
elif "s" in mat:
    s = mat["s"]
else:
    print("Variables found in MAT file:")
    for key in mat.keys():
        if not key.startswith("__"):
            print("-", key)
    raise KeyError("Could not find serialDataStruct or s in MAT file")

# Extract data fields
try:
    flows = np.array(s.flows)
    pumps = np.array(s.pumps)
    valves = np.array(s.valves)
    timestamps = np.array(s.timestamp).squeeze()
except AttributeError as e:
    print("Fields found inside MATLAB struct:")
    if hasattr(s, "_fieldnames"):
        for field in s._fieldnames:
            print("-", field)
    raise AttributeError(f"Missing expected field in MATLAB struct: {e}")

# Make sure arrays are 2D where needed
if flows.ndim == 1:
    flows = flows.reshape(4, -1)

if pumps.ndim == 1:
    pumps = pumps.reshape(2, -1)

if valves.ndim == 1:
    valves = valves.reshape(4, -1)

# Validate shapes
if flows.shape[0] != 4:
    raise ValueError(f"Expected 4 flow channels, got shape {flows.shape}")

if pumps.shape[0] != 2:
    raise ValueError(f"Expected 2 pump channels, got shape {pumps.shape}")

if valves.shape[0] != 4:
    raise ValueError(f"Expected 4 valve channels, got shape {valves.shape}")

n = len(timestamps)

if flows.shape[1] != n:
    raise ValueError(f"Flow length mismatch: flows={flows.shape}, timestamps={n}")

if pumps.shape[1] != n:
    raise ValueError(f"Pump length mismatch: pumps={pumps.shape}, timestamps={n}")

if valves.shape[1] != n:
    raise ValueError(f"Valve length mismatch: valves={valves.shape}, timestamps={n}")

# Connect to SQLite
conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

# Create runs table if it does not exist
cur.execute("""
CREATE TABLE IF NOT EXISTS runs (
    run_name TEXT PRIMARY KEY,
    run_type TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

# Create ESP32/MATLAB table if it does not exist
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

# Add run metadata.
# INSERT OR IGNORE avoids overwriting if this run already exists.
cur.execute("""
INSERT OR IGNORE INTO runs (run_name, run_type, notes)
VALUES (?, ?, ?)
""", (
    RUN_NAME,
    "esp32_matlab_import",
    f"Imported from {MAT_FILE}"
))

# Prevent duplicate imports for the same run.
# If you re-run this file, it replaces old rows for this RUN_NAME.
cur.execute("DELETE FROM esp32_matlab_data WHERE run_name = ?", (RUN_NAME,))

# Insert rows
for i in range(n):
    cur.execute("""
        INSERT INTO esp32_matlab_data (
            run_name, timestamp,
            flow_p1, flow_p2, flow_valve1, flow_outlet,
            pump1_pwm, pump2_pwm,
            valve1, valve2, valve3, valve4
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        RUN_NAME,
        float(timestamps[i]),
        float(flows[0, i]),
        float(flows[1, i]),
        float(flows[2, i]),
        float(flows[3, i]),
        float(pumps[0, i]),
        float(pumps[1, i]),
        int(valves[0, i]),
        int(valves[1, i]),
        int(valves[2, i]),
        int(valves[3, i]),
    ))

conn.commit()
conn.close()

print(f"Imported {n} rows from {MAT_FILE} into {DB_NAME}")
print(f"Run name: {RUN_NAME}")
print("Duplicate protection: old rows for this run_name were replaced.")