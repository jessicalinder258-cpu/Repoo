"""Request and response schemas."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskFilter(str, Enum):
    all = "all"
    active = "active"
    completed = "completed"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=2000)
    priority: Priority = Priority.medium
    due_date: date | None = None

    @field_validator("title", "notes")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def reject_blank_title(cls, value: str) -> str:
        if not value:
            raise ValueError("title must not be blank")
        return value


class TaskUpdate(BaseModel):
    """Every field is optional; only the ones provided are changed."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    priority: Priority | None = None
    due_date: date | None = None
    completed: bool | None = None

    @field_validator("title", "notes")
    @classmethod
    def strip_whitespace(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("title")
    @classmethod
    def reject_blank_title(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("title must not be blank")
        return value


class Task(BaseModel):
    id: int
    title: str
    notes: str
    priority: Priority
    due_date: date | None
    completed: bool
    created_at: datetime
    completed_at: datetime | None


class Stats(BaseModel):
    total: int
    active: int
    completed: int
