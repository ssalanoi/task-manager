from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session, select

from ..auth import require_api_key
from ..db import get_session
from ..models import Task, TaskPriority, TaskStatus
from ..schemas import TaskCreate, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_api_key)])


def _to_read(task: Task) -> TaskRead:
    tags = [t for t in task.tags_csv.split(",") if t]
    return TaskRead(
        id=task.id,  # type: ignore[arg-type]
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        due_date=task.due_date,
        tags=tags,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _tags_to_csv(tags: List[str]) -> str:
    return ",".join(tags)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, session: Session = Depends(get_session)) -> TaskRead:
    task = Task(
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        due_date=payload.due_date,
        tags_csv=_tags_to_csv(payload.tags),
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return _to_read(task)


@router.get("", response_model=List[TaskRead])
def list_tasks(
    session: Session = Depends(get_session),
    status_: Optional[TaskStatus] = Query(default=None, alias="status"),
    priority: Optional[TaskPriority] = None,
    tag: Optional[str] = None,
    due_before: Optional[str] = None,
    due_after: Optional[str] = None,
) -> List[TaskRead]:
    stmt = select(Task)
    if status_ is not None:
        stmt = stmt.where(Task.status == status_)
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)
    if due_before is not None:
        stmt = stmt.where(Task.due_date.is_not(None)).where(Task.due_date < due_before)  # type: ignore[union-attr]
    if due_after is not None:
        stmt = stmt.where(Task.due_date.is_not(None)).where(Task.due_date > due_after)  # type: ignore[union-attr]
    rows = session.exec(stmt).all()
    if tag:
        norm = tag.strip().lower()
        rows = [r for r in rows if norm in [t for t in r.tags_csv.split(",") if t]]
    return [_to_read(r) for r in rows]


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: int, session: Session = Depends(get_session)) -> TaskRead:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _to_read(task)


@router.put("/{task_id}", response_model=TaskRead)
def update_task(
    task_id: int, payload: TaskUpdate, session: Session = Depends(get_session)
) -> TaskRead:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    data = payload.model_dump(exclude_unset=True)
    if "tags" in data:
        task.tags_csv = _tags_to_csv(data.pop("tags") or [])
    for field, value in data.items():
        setattr(task, field, value)
    task.updated_at = datetime.now(timezone.utc)
    session.add(task)
    session.commit()
    session.refresh(task)
    return _to_read(task)


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
def delete_task(task_id: int, session: Session = Depends(get_session)) -> dict:
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    session.delete(task)
    session.commit()
    return {"deleted": True, "id": task_id}
