import asyncio

import asyncpg
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate

app = FastAPI()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/db_check")
async def db_check():
    try:
        conn = await asyncpg.connect(settings.database_url)
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks")
async def get_tasks(db: AsyncSession = Depends(get_db)):
    """Вернуть все задачи из БД"""
    result = await db.execute(select(Task))
    tasks = result.scalars().all()  # запрос → список задач
    return tasks


@app.post("/tasks")
async def create_task(task_data: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Создать новую задачу (статус new проставится автоматически)."""
    task = Task(title=task_data.title)
    db.add(task)
    await db.commit()
    await db.refresh(task)  # подтягиваем id после вставки
    return task


@app.get("/tasks/slow")
async def get_tasks_slow(db: AsyncSession = Depends(get_db)):
    """Вернуть все задачи с искусственной задержкой (демонстрация async)."""
    await asyncio.sleep(3)

    result = await db.execute(select(Task))
    tasks = result.scalars().all()  # запрос → все задачи списком
    return tasks


@app.get("/tasks/heavy")
async def get_tasks_heavy(db: AsyncSession = Depends(get_db)):
    """Тяжёлый запрос: сортировка по случайному числу (без индекса)."""
    result = await db.execute(select(Task).order_by(func.random()))
    tasks = result.scalars().all()  # запрос → все задачи списком
    return tasks


@app.get("/tasks/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Вернуть одну задачу по id"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()  # запрос → одна задача или None
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}")
async def update_task(task_id: int, task_data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить задачу по id с проверкой версии (оптимистичная блокировка)."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()  # запрос → одна задача или None

    # 1. проверить, что задача существует
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 2. проверить версию
    if task.version != task_data.version:
        raise HTTPException(status_code=409, detail="Version conflict")
    
    # 3. обновить поля
    if task_data.title is not None:
        task.title = task_data.title
    if task_data.status is not None:
        task.status = task_data.status
    
    # 4. увеличить версию
    task.version += 1

    # 5. сохранить в БД
    await db.commit()
    await db.refresh(task)
    return task