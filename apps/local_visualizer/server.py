import argparse
import csv
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = Path(__file__).resolve().parent / "static"
EXPORT_DIR = ROOT_DIR / "exports"


NUMERIC_COLUMNS = {
    "t_seconds",
    "pump1_pwm",
    "pump2_pwm",
    "valve1",
    "valve2",
    "valve3",
    "valve4",
    "flow_p1",
    "flow_p2",
    "flow_valve1",
    "flow_outlet",
    "tower",
    "treated",
    "raw",
}


def infer_run_name(path):
    suffix = "_merged_timeseries"
    if path.stem.endswith(suffix):
        return path.stem[: -len(suffix)]
    return path.stem


def numeric(value):
    if value in ("", None):
        return None
    try:
        return float(value)
    except ValueError:
        return value


def load_run(path):
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cleaned = {}
            for key, value in row.items():
                cleaned[key] = numeric(value) if key in NUMERIC_COLUMNS else value
            rows.append(cleaned)
    return rows


def run_files():
    return sorted(EXPORT_DIR.glob("*_merged_timeseries.csv"))


def run_summary(path):
    rows = load_run(path)
    duration = None
    if rows:
        times = [row.get("t_seconds") for row in rows if isinstance(row.get("t_seconds"), (int, float))]
        if times:
            duration = max(times) - min(times)
    return {
        "run_name": infer_run_name(path),
        "file": str(path.relative_to(ROOT_DIR)),
        "rows": len(rows),
        "duration_seconds": duration,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def send_json(self, payload, status=200):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/runs":
            self.send_json({"runs": [run_summary(path) for path in run_files()]})
            return

        if parsed.path == "/api/run":
            params = parse_qs(parsed.query)
            run_name = params.get("name", [""])[0]
            candidates = {
                infer_run_name(path): path
                for path in run_files()
            }
            path = candidates.get(run_name)
            if not path:
                self.send_json({"error": f"Unknown run: {run_name}"}, status=404)
                return
            self.send_json({"run_name": run_name, "rows": load_run(path)})
            return

        return super().do_GET()


def main():
    parser = argparse.ArgumentParser(description="Read-only local water-system visualizer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Local visualizer: http://{args.host}:{args.port}")
    print("Source: exports/*_merged_timeseries.csv (read-only)")
    server.serve_forever()


if __name__ == "__main__":
    main()
