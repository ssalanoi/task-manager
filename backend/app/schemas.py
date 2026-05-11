from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .models import TaskPriority, TaskStatus

MAX_TAGS = 10
MAX_TAG_LEN = 32


def _normalise_tags(raw: Optional[List[str]]) -> List[str]:
    if not raw:
        return []
    out: List[str] = []
    seen: set[str] = set()
    for t in raw:
        if not isinstance(t, str):
            raise ValueError("tags must be strings")
        norm = t.strip().lower()
        if not norm:
            continue
        if len(norm) > MAX_TAG_LEN:
            raise ValueError(f"tag '{norm}' exceeds {MAX_TAG_LEN} chars")
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    if len(out) > MAX_TAGS:
        raise ValueError(f"max {MAX_TAGS} tags allowed")
    return out


def _validate_due_date(value: Optional[str], *, must_be_future: bool) -> Optional[str]:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("due_date must be ISO date YYYY-MM-DD") from exc
    if must_be_future and parsed < date.today():
        raise ValueError("due_date must be today or in the future")
    return parsed.isoformat()


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    due_date: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty")
        return v

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: List[str]) -> List[str]:
        return _normalise_tags(v)

    @field_validator("due_date")
    @classmethod
    def _due(cls, v: Optional[str]) -> Optional[str]:
        return _validate_due_date(v, must_be_future=True)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[str] = None
    tags: Optional[List[str]] = None

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty")
        return v

    @field_validator("tags")
    @classmethod
    def _tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return _normalise_tags(v)

    @field_validator("due_date")
    @classmethod
    def _due(cls, v: Optional[str]) -> Optional[str]:
        # On update we permit past dates (e.g. recording an overdue item).
        return _validate_due_date(v, must_be_future=False)


class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[str]
    tags: List[str]
    created_at: datetime
    updated_at: datetime
