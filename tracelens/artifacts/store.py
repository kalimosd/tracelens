from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from tracelens.types import AnalysisResult, EvidenceItem


@dataclass(slots=True)
class InMemoryArtifactStore:
    _items: dict[str, AnalysisResult] | None = None

    def __post_init__(self) -> None:
        if self._items is None:
            self._items = {}

    def save(self, result: AnalysisResult) -> str:
        session_id = str(uuid4())
        self._items[session_id] = result
        return session_id

    def load(self, session_id: str) -> AnalysisResult | None:
        return self._items.get(session_id)


class SQLiteArtifactStore:
    def __init__(self, db_path: str | Path = "tracelens_sessions.db") -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS sessions ("
            "  session_id TEXT PRIMARY KEY,"
            "  result_json TEXT NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        self._conn.commit()

    def save(self, result: AnalysisResult) -> str:
        session_id = str(uuid4())
        self._conn.execute(
            "INSERT INTO sessions (session_id, result_json) VALUES (?, ?)",
            (session_id, result.model_dump_json()),
        )
        self._conn.commit()
        return session_id

    def load(self, session_id: str) -> AnalysisResult | None:
        row = self._conn.execute(
            "SELECT result_json FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return AnalysisResult.model_validate_json(row[0])

    def close(self) -> None:
        self._conn.close()
