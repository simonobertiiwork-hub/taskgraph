import asyncpg
from fastapi import Body, Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate

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
def create_tasks(task_data: TaskCreate, db: Session = Depends(get_db)):
    """Создать новую задачу (статус new проставится автоматически)."""
    task = Task(title=task_data.title)
    db.add(task)
    db.commit()
    db.refresh(task)  # подтягиваем id после вставки
    return task