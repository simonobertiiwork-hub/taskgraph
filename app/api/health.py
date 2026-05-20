"""Health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}


@router.get("/db_check")
async def db_check(db: AsyncSession = Depends(get_db)):
    """Проверка подключения к базе данных."""
    result = await db.execute(text("SELECT 1"))
    return {"result": result.scalar_one()}