"""Роутер для задач (tasks)."""

import asyncio
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.core.exceptions import NotFoundError, ConflictError

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def get_tasks(db: AsyncSession = Depends(get_db)):
    """Вернуть все задачи из БД."""
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks


@router.post("")
async def create_task(task_data: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Создать новую задачу (статус new проставится автоматически)."""
    task = Task(title=task_data.title)
    db.add(task)
    await db.commit()
    await db.refresh(task)  # подтягиваем id после вставки
    return task


@router.get("/slow")
async def get_tasks_slow(
    db: AsyncSession = Depends(get_db),
    delay: int = Query(2, ge=0, le=10),
):
    """Вернуть все задачи с задержкой на уровне БД (удерживает соединение)."""
    await db.execute(text("SELECT pg_sleep(:delay)"), {"delay": delay})
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks


@router.get("/heavy")
async def get_tasks_heavy(db: AsyncSession = Depends(get_db)):
    """Тяжёлый запрос: сортировка по случайному числу (без индекса)."""
    result = await db.execute(select(Task).order_by(func.random()))
    tasks = result.scalars().all()
    return tasks


@router.get("/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Вернуть одну задачу по id"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise NotFoundError("Task not found")
    return task


@router.patch("/{task_id}")
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить задачу с атомарной проверкой версии (optimistic lock)."""
    values_to_update = {"version": Task.version + 1}

    if task_data.title is not None:
        values_to_update["title"] = task_data.title
    if task_data.status is not None:
        values_to_update["status"] = task_data.status

    stmt = (
        update(Task)
        .where(
            Task.id == task_id,
            Task.version == task_data.version
        )
        .values(**values_to_update)
        .returning(Task)
    )
    result = await db.execute(stmt)
    updated = result.scalar_one_or_none()

    if not updated:
        # проверяем, существует ли задача
        exists = await db.execute(select(Task.id).where(Task.id == task_id))
        if not exists.scalar_one_or_none():
            raise NotFoundError("Task not found")
        raise ConflictError("Version conflict")

    await db.commit()
    await db.refresh(updated)
    return updated