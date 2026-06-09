"""Роутер для задач (tasks)."""

import asyncio
import json
import time
import random
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.core.exceptions import NotFoundError, ConflictError
from app.core.rabbitmq import publish_message
from app.core.redis import redis_client
from app.core.tasks import process_task

CACHE_TTL_SECONDS = 30

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def get_tasks(db: AsyncSession = Depends(get_db)):
    """Вернуть все задачи из БД."""
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks


@router.get("/stats")
async def get_tasks_stats(
    db: AsyncSession = Depends(get_db)
):
    """Вернуть статистику задач для Redis Cache Case."""

    cache_key = "tasks:stats"

    start = time.perf_counter()

    cached = await redis_client.get(cache_key)

    if cached:
        duration_ms = round(
            (time.perf_counter() - start) * 1000,
            3
        )

        return {
            "source": "redis",
            "cache": "hit",
            "duration_ms": duration_ms,
            "stats": json.loads(cached)
        }

    result = await db.execute(
        select(
            Task.status,
            func.count(Task.id)
        ).group_by(Task.status)
    )

    stats = {
        status: count
        for status, count in result.all()
    }

    await redis_client.set(
        cache_key,
        json.dumps(stats),
        ex=CACHE_TTL_SECONDS
    )

    duration_ms = round(
        (time.perf_counter() - start) * 1000,
        3
    )

    return {
        "source": "postgres",
        "cache": "miss",
        "duration_ms": duration_ms,
        "stats": stats
    }


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
):
    """Вернуть все задачи с задержкой на уровне БД (удерживает соединение)."""

    delay = random.randint(1, 10)

    await db.execute(
        text("SELECT pg_sleep(:delay)"), 
        {"delay": delay}
    )

    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks


@router.get("/heavy")
async def get_tasks_heavy(db: AsyncSession = Depends(get_db)):
    """Тяжёлый запрос: сортировка по случайному числу (без индекса)."""
    result = await db.execute(
        select(Task.id, Task.title)
        .order_by(func.random())
        .limit(1000)
    )
    tasks = result.all()
    return tasks


@router.post("/prepare-statuses")
async def prepare_task_statuses(db: AsyncSession = Depends(get_db)):
    """Подготовить тестовые данные для Redis Cache Case."""
    await db.execute(
        update(Task)
        .where(Task.id <= 300)
        .values(status="new")
    )

    await db.execute(
        update(Task)
        .where(Task.id > 300, Task.id <= 700)
        .values(status="in_progress")
    )

    await db.execute(
        update(Task)
        .where(Task.id > 700)
        .values(status="done")
    )

    await db.commit()

    return {
        "message": "Task statuses prepared",
        "distribution": {
            "new": "id <= 300",
            "in_progress": "301 <= id <= 700",
            "done": "id > 700"
        }
    }


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


@router.post("/rabbit-test")
async def rabbit_test():
    publish_message("TaskGraph RabbitMQ test")
    return {"status": "message sent"}


@router.post("/celery-test")
async def celery_test():
    task = process_task.delay(123)

    return {
        "task_id": task.id,
        "status": "submitted"
    }