import sqlite3
from config import DB_NAME, TANK_MAPPING

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

print("\n=== TABLES ===")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
for row in cur.fetchall():
    print(row[0])

print("\n=== RUNS ===")
try:
    cur.execute("SELECT run_name, run_type, notes, created_at FROM runs ORDER BY created_at DESC")
    for row in cur.fetchall():
        print(row)
except sqlite3.OperationalError:
    print("runs table not found")

print("\n=== ROW COUNTS ===")
cur.execute("SELECT COUNT(*) FROM esp32_matlab_data")
print("ESP32/MATLAB rows:", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM arduino_tank_data")
print("Arduino tank rows:", cur.fetchone()[0])

print("\n=== ROWS BY RUN_NAME ===")
cur.execute("""
SELECT run_name, COUNT(*)
FROM esp32_matlab_data
GROUP BY run_name
ORDER BY run_name
""")
print("ESP32/MATLAB:")
for row in cur.fetchall():
    print(row)

cur.execute("""
SELECT run_name, COUNT(*)
FROM arduino_tank_data
GROUP BY run_name
ORDER BY run_name
""")
print("Arduino:")
for row in cur.fetchall():
    print(row)

print("\n=== ESP32 MAX VALUES ===")
cur.execute("""
SELECT
    MAX(flow_p1),
    MAX(flow_p2),
    MAX(flow_valve1),
    MAX(flow_outlet),
    MAX(pump1_pwm),
    MAX(pump2_pwm)
FROM esp32_matlab_data
""")
print(cur.fetchone())

print("\n=== TANK MAPPING ===")
print(f"tank1 = {TANK_MAPPING['tank1']}")
print(f"tank2 = {TANK_MAPPING['tank2']}")
print(f"tank3 = {TANK_MAPPING['tank3']}")

print("\n=== LATEST ARDUINO ROWS ===")
cur.execute("""
SELECT run_name, timestamp, tank1, tank2, tank3, raw_line
FROM arduino_tank_data
ORDER BY id DESC
LIMIT 10
""")
for row in cur.fetchall():
    print(row)
print("\n=== LATEST ESP32 NONZERO-FLOW ROWS ===")
cur.execute("""
SELECT run_name, timestamp, flow_p1, flow_p2, flow_valve1, flow_outlet, pump1_pwm, pump2_pwm
FROM esp32_matlab_data
WHERE flow_p1 > 0 OR flow_p2 > 0 OR flow_valve1 > 0 OR flow_outlet > 0
ORDER BY id DESC
LIMIT 10
""")
for row in cur.fetchall():
    print(row)

print("\n=== BASIC DATA QUALITY CHECKS ===")
cur.execute("""
SELECT COUNT(*)
FROM arduino_tank_data
WHERE tank1 IS NULL AND tank2 IS NULL AND tank3 IS NULL
""")
print("Arduino fully-null rows:", cur.fetchone()[0])

cur.execute("""
SELECT COUNT(*)
FROM esp32_matlab_data
WHERE timestamp IS NULL
""")
print("ESP32 rows missing timestamp:", cur.fetchone()[0])

conn.close()
