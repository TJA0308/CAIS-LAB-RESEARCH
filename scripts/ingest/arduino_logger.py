import sqlite3
import time
from datetime import datetime

import serial

from config import DB_NAME, RUN_NAME, SERIAL_PORT, BAUD_RATE, TANK_MAPPING


def parse_value(value):
    value = value.strip()
    if value.lower() == "error" or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

cur.execute("""
INSERT OR IGNORE INTO runs (run_name, run_type, notes)
VALUES (?, ?, ?)
""", (
    RUN_NAME,
    "arduino_tank_logging",
    "Arduino UNO ultrasonic tank sensor logging"
))
conn.commit()

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
time.sleep(2)

print(f"Reading Arduino tank sensors for {RUN_NAME}. Press Ctrl+C to stop.")
print(
    "Sensor mapping: "
    f"tank1={TANK_MAPPING['tank1']}, "
    f"tank2={TANK_MAPPING['tank2']}, "
    f"tank3={TANK_MAPPING['tank3']}"
)

row_count = 0
try:
    while True:
        line = ser.readline().decode(errors="ignore").strip()

        if not line:
            continue

        parts = line.split(",")

        if len(parts) != 3:
            print("Bad line:", line)
            continue

        tank1 = parse_value(parts[0])
        tank2 = parse_value(parts[1])
        tank3 = parse_value(parts[2])

        if tank1 is None and tank2 is None and tank3 is None:
            print("Skipped invalid sensor row:", line)
            continue

        timestamp = datetime.now().isoformat(timespec="milliseconds")

        cur.execute("""
            INSERT INTO arduino_tank_data (
                run_name, timestamp, tank1, tank2, tank3, raw_line
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (RUN_NAME, timestamp, tank1, tank2, tank3, line))

        conn.commit()
        row_count += 1

        print(
            f"Inserted {row_count}: {RUN_NAME}, "
            f"{TANK_MAPPING['tank1']}={tank1}, "
            f"{TANK_MAPPING['tank2']}={tank2}, "
            f"{TANK_MAPPING['tank3']}={tank3}"
        )

except KeyboardInterrupt:
    print(f"Stopped Arduino logger. Inserted {row_count} rows.")

finally:
    ser.close()
    conn.close()
