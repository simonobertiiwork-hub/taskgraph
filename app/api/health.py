"""Health check endpoints."""

import asyncpg
from fastapi import APIRouter, HTTPException

from app.core.config import  settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}


@router.get("/db_check")
async def db_check():
    """Проверка подключения к базе данных."""
    try:
        conn = await asyncpg.connect(settings.database_url)
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))