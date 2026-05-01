import asyncpg
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

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
def get_tasks(db: Session = Depends(get_db)):
    """Вернуть все задачи из БД"""
    tasks = db.query(Task).all()
    return tasks


@app.post("/tasks")
def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    """Создать новую задачу (статус new проставится автоматически)."""
    task = Task(title=task_data.title)
    db.add(task)
    db.commit()
    db.refresh(task)  # подтягиваем id после вставки
    return task


@app.get("/tasks/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Вернуть одну задачу по id"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, task_data: TaskUpdate, db: Session = Depends(get_db)):
    # 1. найти задачу
    task = db.query(Task).filter(Task.id == task_id).first()
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
    db.commit()
    db.refresh(task)
    return task