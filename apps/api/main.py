from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = ROOT_DIR / "data" / "db" / "water_testbed.db"
DEFAULT_EXPORT_DIR = ROOT_DIR / "exports"
MAX_TIMESERIES_LIMIT = 5000
DEFAULT_TIMESERIES_LIMIT = 1000
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


class HealthResponse(BaseModel):
    status: str
    database_available: bool
    database_path: str


class RunListItem(BaseModel):
    run_id: str
    run_type: str | None = None
    notes: str | None = None
    created_at: str | None = None
    has_timeseries: bool


class RunsResponse(BaseModel):
    runs: list[RunListItem]


class RunDetailResponse(BaseModel):
    run_id: str
    run_type: str | None = None
    notes: str | None = None
    created_at: str | None = None
    esp32_rows: int
    arduino_rows: int
    has_timeseries: bool


class TimeseriesResponse(BaseModel):
    run_id: str
    source_file: str
    returned_rows: int
    total_matching_rows: int
    limit: int
    start_s: float | None = None
    end_s: float | None = None
    rows: list[dict[str, Any]]


def configured_path(env_name: str, default: Path) -> Path:
    value = os.getenv(env_name)
    return Path(value).resolve() if value else default.resolve()


def numeric(value: str | None) -> float | str | None:
    if value in ("", None):
        return None
    try:
        return float(value)
    except ValueError:
        return value


def open_readonly_connection(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise HTTPException(status_code=500, detail=f"Database not found: {db_path}")
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def create_app(
    db_path: Path | None = None,
    export_dir: Path | None = None,
) -> FastAPI:
    db_path = (db_path or configured_path("WATER_TESTBED_DB", DEFAULT_DB_PATH)).resolve()
    export_dir = (export_dir or configured_path("WATER_TESTBED_EXPORT_DIR", DEFAULT_EXPORT_DIR)).resolve()

    app = FastAPI(
        title="Water Testbed Read-Only API",
        description="Read-only REST access to run metadata and synchronized water-testbed CSV outputs.",
        version="0.1.0",
    )
    app.state.db_path = db_path
    app.state.export_dir = export_dir

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    def connect() -> sqlite3.Connection:
        return open_readonly_connection(app.state.db_path)

    def timeseries_path_for_run(run_id: str) -> Path:
        candidate = (app.state.export_dir / f"{run_id}_merged_timeseries.csv").resolve()
        try:
            candidate.relative_to(app.state.export_dir)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid run_id path") from exc
        return candidate

    def get_run_or_404(run_id: str) -> dict[str, Any]:
        with connect() as conn:
            row = conn.execute(
                """
                SELECT run_name, run_type, notes, created_at
                FROM runs
                WHERE run_name = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
        return row_to_dict(row)

    def raw_row_count(table_name: str, run_id: str) -> int:
        if table_name not in {"esp32_matlab_data", "arduino_tank_data"}:
            raise ValueError(f"Unsupported table: {table_name}")
        with connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) AS row_count FROM {table_name} WHERE run_name = ?",
                (run_id,),
            ).fetchone()
        return int(row["row_count"])

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            database_available=app.state.db_path.exists(),
            database_path=str(app.state.db_path),
        )

    @app.get("/runs", response_model=RunsResponse)
    def list_runs() -> RunsResponse:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT run_name, run_type, notes, created_at
                FROM runs
                ORDER BY run_name
                """
            ).fetchall()

        return RunsResponse(
            runs=[
                RunListItem(
                    run_id=row["run_name"],
                    run_type=row["run_type"],
                    notes=row["notes"],
                    created_at=row["created_at"],
                    has_timeseries=timeseries_path_for_run(row["run_name"]).exists(),
                )
                for row in rows
            ]
        )

    @app.get("/runs/{run_id}", response_model=RunDetailResponse)
    def get_run(run_id: str) -> RunDetailResponse:
        run = get_run_or_404(run_id)
        return RunDetailResponse(
            run_id=run["run_name"],
            run_type=run["run_type"],
            notes=run["notes"],
            created_at=run["created_at"],
            esp32_rows=raw_row_count("esp32_matlab_data", run_id),
            arduino_rows=raw_row_count("arduino_tank_data", run_id),
            has_timeseries=timeseries_path_for_run(run_id).exists(),
        )

    @app.get("/runs/{run_id}/timeseries", response_model=TimeseriesResponse)
    def get_timeseries(
        run_id: str,
        start_s: float | None = Query(default=None, ge=0),
        end_s: float | None = Query(default=None, ge=0),
        limit: int = Query(default=DEFAULT_TIMESERIES_LIMIT, ge=1, le=MAX_TIMESERIES_LIMIT),
    ) -> TimeseriesResponse:
        get_run_or_404(run_id)

        if start_s is not None and end_s is not None and start_s > end_s:
            raise HTTPException(status_code=422, detail="start_s must be less than or equal to end_s")

        csv_path = timeseries_path_for_run(run_id)
        if not csv_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Merged timeseries CSV not found for run: {run_id}",
            )

        rows: list[dict[str, Any]] = []
        total_matching_rows = 0

        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if "t_seconds" not in (reader.fieldnames or []):
                raise HTTPException(
                    status_code=500,
                    detail=f"Merged timeseries CSV is missing t_seconds: {csv_path.name}",
                )

            for raw_row in reader:
                t_seconds = numeric(raw_row.get("t_seconds"))
                if not isinstance(t_seconds, float):
                    continue
                if start_s is not None and t_seconds < start_s:
                    continue
                if end_s is not None and t_seconds > end_s:
                    continue

                total_matching_rows += 1
                if len(rows) >= limit:
                    continue

                rows.append(
                    {
                        key: numeric(value) if key in NUMERIC_COLUMNS else value
                        for key, value in raw_row.items()
                    }
                )

        return TimeseriesResponse(
            run_id=run_id,
            source_file=str(csv_path.relative_to(ROOT_DIR)) if csv_path.is_relative_to(ROOT_DIR) else str(csv_path),
            returned_rows=len(rows),
            total_matching_rows=total_matching_rows,
            limit=limit,
            start_s=start_s,
            end_s=end_s,
            rows=rows,
        )

    return app


app = create_app()
