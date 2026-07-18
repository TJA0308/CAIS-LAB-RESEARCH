import csv
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import create_app


def make_test_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE runs (
            run_name TEXT PRIMARY KEY,
            run_type TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE esp32_matlab_data (
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
            valve4 INTEGER
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE arduino_tank_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            tank1 REAL,
            tank2 REAL,
            tank3 REAL,
            raw_line TEXT,
            run_name TEXT
        )
        """
    )
    cur.execute(
        """
        INSERT INTO runs (run_name, run_type, notes, created_at)
        VALUES (?, ?, ?, ?)
        """,
        ("test_run_001", "test", "fixture run", "2026-01-01 00:00:00"),
    )
    cur.execute(
        """
        INSERT INTO esp32_matlab_data (
            run_name, timestamp, flow_p1, flow_p2, flow_valve1, flow_outlet,
            pump1_pwm, pump2_pwm, valve1, valve2, valve3, valve4
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("test_run_001", 0.0, 1.0, 2.0, 3.0, 4.0, 100.0, 0.0, 1, 0, 0, 0),
    )
    cur.execute(
        """
        INSERT INTO arduino_tank_data (timestamp, tank1, tank2, tank3, raw_line, run_name)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("2026-01-01T00:00:00.000", 10.0, 20.0, 30.0, "10,20,30", "test_run_001"),
    )
    conn.commit()
    conn.close()


def make_timeseries(export_dir: Path) -> None:
    export_dir.mkdir()
    path = export_dir / "test_run_001_merged_timeseries.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "run_name",
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
            ],
        )
        writer.writeheader()
        for second in range(5):
            writer.writerow(
                {
                    "run_name": "test_run_001",
                    "t_seconds": second,
                    "pump1_pwm": 100,
                    "pump2_pwm": 0,
                    "valve1": 1,
                    "valve2": 0,
                    "valve3": 0,
                    "valve4": 0,
                    "flow_p1": second + 1,
                    "flow_p2": 0,
                    "flow_valve1": second,
                    "flow_outlet": 0,
                    "tower": 10 + second,
                    "treated": 20 + second,
                    "raw": 30 + second,
                }
            )


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "water_testbed_test.db"
    export_dir = tmp_path / "exports"
    make_test_db(db_path)
    make_timeseries(export_dir)
    return TestClient(create_app(db_path=db_path, export_dir=export_dir))


def test_health_uses_fixture_database(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database_available"] is True
    assert payload["database_path"].endswith("water_testbed_test.db")


def test_list_runs(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/runs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["run_id"] == "test_run_001"
    assert payload["runs"][0]["has_timeseries"] is True


def test_valid_run_detail(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/runs/test_run_001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == "test_run_001"
    assert payload["esp32_rows"] == 1
    assert payload["arduino_rows"] == 1


def test_invalid_run_id_returns_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/runs/not_a_run")
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found: not_a_run"


def test_timeseries_filters_and_limits(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/runs/test_run_001/timeseries?start_s=1&end_s=3&limit=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["returned_rows"] == 2
    assert payload["total_matching_rows"] == 3
    assert [row["t_seconds"] for row in payload["rows"]] == [1.0, 2.0]


def test_timeseries_invalid_range_returns_422(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    response = client.get("/runs/test_run_001/timeseries?start_s=3&end_s=1")
    assert response.status_code == 422
    assert response.json()["detail"] == "start_s must be less than or equal to end_s"
