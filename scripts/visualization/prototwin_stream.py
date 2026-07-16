"""
Minimal ProtoTwin / MQTT bridge (proof of integration path).

Replays a wall-clock-synchronized merged run as a 1-second JSON state stream on
an MQTT topic that a ProtoTwin scene can subscribe to. Runs DRY-RUN by default
(prints the messages it would publish) so it works with no broker and no extra
dependencies. Only when --broker is given does it publish over MQTT.

This demonstrates that the backend already produces a ProtoTwin-ready state
stream. The live 3-D visualization itself is future work.

Examples:
    python -m scripts.visualization.prototwin_stream
    python -m scripts.visualization.prototwin_stream --limit 0
    python -m scripts.visualization.prototwin_stream --broker localhost
"""
import argparse
import json
import time
from pathlib import Path

import pandas as pd

from config import EXPORT_DIR

STATE_FIELDS = [
    "t_seconds",
    "pump1_pwm", "pump2_pwm",
    "valve1", "valve2", "valve3", "valve4",
    "flow_p1", "flow_p2", "flow_valve1", "flow_outlet",
    "tower", "treated", "raw",
]


def load_run(run_name):
    path = Path(EXPORT_DIR) / f"{run_name}_merged_timeseries.csv"
    if not path.exists():
        raise SystemExit(f"Merged file not found: {path}")
    return pd.read_csv(path)


def build_payload(row, run_name, columns):
    payload = {"run": run_name}
    for column in columns:
        value = row[column]
        payload[column] = None if pd.isna(value) else float(value)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", default="full_cycle_run_004")
    parser.add_argument("--broker", default=None, help="MQTT broker host; omit for dry-run")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--topic", default="water_testbed/state")
    parser.add_argument("--limit", type=int, default=10, help="rows to stream (0 = all)")
    parser.add_argument("--rate", type=float, default=0.0, help="seconds between messages")
    args = parser.parse_args()

    data = load_run(args.run)
    columns = [column for column in STATE_FIELDS if column in data.columns]

    client = None
    if args.broker:
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            raise SystemExit("paho-mqtt not installed. Install it, or run dry-run (omit --broker).")
        client = mqtt.Client()
        client.connect(args.broker, args.port, 60)
        client.loop_start()

    total = len(data)
    count = total if args.limit == 0 else min(args.limit, total)
    mode = f"MQTT {args.broker}:{args.port}" if client else "DRY-RUN (no broker)"
    print(f"Streaming {count}/{total} rows from '{args.run}' to topic '{args.topic}' [{mode}]")

    for i in range(count):
        message = json.dumps(build_payload(data.iloc[i], args.run, columns))
        if client:
            client.publish(args.topic, message)
        else:
            print(message)
        if args.rate:
            time.sleep(args.rate)

    if client:
        client.loop_stop()
        client.disconnect()
    print("Done.")


if __name__ == "__main__":
    main()
