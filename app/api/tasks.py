"""Роутер для задач (tasks)."""

import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
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
async def get_tasks_slow(db: AsyncSession = Depends(get_db)):
    """Вернуть все задачи с искусственной задержкой (демонстрация async)."""
    await asyncio.sleep(3)
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
    """Обновить задачу по id с проверкой версии (оптимистичная блокировка)."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise NotFoundError("Task not found")
    
    if task.version != task_data.version:
        raise ConflictError("Version conflict")
    
    if task_data.title is not None:
        task.title = task_data.title
    if task_data.status is not None:
        task.status = task_data.status
    
    task.version += 1

    await db.commit()
    await db.refresh(task)
    return task