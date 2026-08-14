"""Database access for tasks."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timezone

from .database import Database
from .models import Stats, Task, TaskCreate, TaskFilter, TaskUpdate

# Ordering: unfinished work first, then by urgency, then newest first.
_ORDER_BY = """
    ORDER BY completed ASC,
             CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END ASC,
             due_date IS NULL ASC,
             due_date ASC,
             created_at DESC
"""

_FILTER_CLAUSES = {
    TaskFilter.all: "",
    TaskFilter.active: "WHERE completed = 0",
    TaskFilter.completed: "WHERE completed = 1",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_task(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        notes=row["notes"],
        priority=row["priority"],
        due_date=date.fromisoformat(row["due_date"]) if row["due_date"] else None,
        completed=bool(row["completed"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=(
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        ),
    )


class TaskRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list(self, task_filter: TaskFilter = TaskFilter.all) -> list[Task]:
        query = f"SELECT * FROM tasks {_FILTER_CLAUSES[task_filter]} {_ORDER_BY}"
        with self.database.connect() as connection:
            rows = connection.execute(query).fetchall()
        return [_to_task(row) for row in rows]

    def get(self, task_id: int) -> Task | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _to_task(row) if row else None

    def create(self, payload: TaskCreate) -> Task:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO tasks (title, notes, priority, due_date, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload.title,
                    payload.notes,
                    payload.priority.value,
                    payload.due_date.isoformat() if payload.due_date else None,
                    _now(),
                ),
            )
            task_id = int(cursor.lastrowid)
        created = self.get(task_id)
        assert created is not None  # just inserted inside the same database
        return created

    def update(self, task_id: int, payload: TaskUpdate) -> Task | None:
        # exclude_unset keeps "field omitted" distinct from "field set to null".
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            return self.get(task_id)

        columns: list[str] = []
        values: list[object] = []

        for field, value in changes.items():
            if field == "priority":
                value = value.value if value is not None else None
            elif field == "due_date":
                value = value.isoformat() if value is not None else None
            elif field == "completed":
                columns.append("completed_at = ?")
                values.append(_now() if value else None)
                value = 1 if value else 0
            columns.append(f"{field} = ?")
            values.append(value)

        values.append(task_id)
        with self.database.connect() as connection:
            cursor = connection.execute(
                f"UPDATE tasks SET {', '.join(columns)} WHERE id = ?", values
            )
            if cursor.rowcount == 0:
                return None
        return self.get(task_id)

    def delete(self, task_id: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0

    def delete_completed(self) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM tasks WHERE completed = 1")
            return cursor.rowcount

    def stats(self) -> Stats:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total,
                       COALESCE(SUM(completed = 0), 0) AS active,
                       COALESCE(SUM(completed = 1), 0) AS completed
                FROM tasks
                """
            ).fetchone()
        return Stats(total=row["total"], active=row["active"], completed=row["completed"])
