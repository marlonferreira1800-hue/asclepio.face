"""Persistência local e opcional somente de métricas."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import FrameMetrics, SessionSummary


class SessionStore:
    def __init__(self, path: str | Path = "data/sessions.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL, ended_at TEXT NOT NULL,
                duration_seconds REAL NOT NULL, sample_count INTEGER NOT NULL,
                mean_quality REAL NOT NULL, level_counts TEXT NOT NULL,
                blink_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                timestamp REAL NOT NULL, payload TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def save(self, summary: SessionSummary, samples: Iterable[FrameMetrics]) -> int:
        cursor = self.connection.execute(
            """INSERT INTO sessions
            (started_at, ended_at, duration_seconds, sample_count, mean_quality, level_counts, blink_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (summary.started_at, summary.ended_at, summary.duration_seconds, summary.sample_count,
             summary.mean_quality, json.dumps(summary.level_counts, ensure_ascii=False), summary.blink_count),
        )
        session_id = int(cursor.lastrowid)
        self.connection.executemany(
            "INSERT INTO samples (session_id, timestamp, payload) VALUES (?, ?, ?)",
            ((session_id, item.timestamp, json.dumps(item.as_dict(), ensure_ascii=False)) for item in samples),
        )
        self.connection.commit()
        return session_id

    def list_sessions(self) -> list[dict[str, object]]:
        rows = self.connection.execute("SELECT * FROM sessions ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]

    def delete(self, session_id: int) -> None:
        self.connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.connection.commit()

    def export_csv(self, session_id: int, destination: str | Path) -> None:
        rows = self.connection.execute(
            "SELECT payload FROM samples WHERE session_id = ? ORDER BY id", (session_id,)
        ).fetchall()
        decoded = [json.loads(row[0]) for row in rows]
        if not decoded:
            raise ValueError("A sessão não contém amostras")
        with Path(destination).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=decoded[0].keys(), extrasaction="ignore")
            writer.writeheader()
            for row in decoded:
                row["notes"] = "; ".join(row.get("notes", []))
                writer.writerow(row)

    def close(self) -> None:
        self.connection.close()
