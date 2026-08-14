"""SQLite connection handling and schema management."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    notes        TEXT    NOT NULL DEFAULT '',
    priority     TEXT    NOT NULL DEFAULT 'medium'
                 CHECK (priority IN ('low', 'medium', 'high')),
    due_date     TEXT,
    completed    INTEGER NOT NULL DEFAULT 0 CHECK (completed IN (0, 1)),
    created_at   TEXT    NOT NULL,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks (completed);
"""


class Database:
    """Owns the SQLite file and hands out short-lived connections.

    An in-memory database only survives as long as its connection, so that
    case reuses a single shared connection guarded by a lock.
    """

    def __init__(self, path: str | Path = "data/tasks.db") -> None:
        self.path = str(path)
        self._in_memory = self.path == ":memory:"
        self._shared: sqlite3.Connection | None = None
        self._lock = threading.Lock()

        if not self._in_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection, committing on success and rolling back on error."""
        if self._in_memory:
            with self._lock:
                if self._shared is None:
                    self._shared = self._new_connection()
                try:
                    yield self._shared
                    self._shared.commit()
                except Exception:
                    self._shared.rollback()
                    raise
            return

        connection = self._new_connection()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def close(self) -> None:
        if self._shared is not None:
            self._shared.close()
            self._shared = None
