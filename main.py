import asyncpg
from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.routers import tasks_router, graph_router


app = FastAPI()


# ========== HEALTH & UTILS ==========

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


# ========== ROUTERS ==========

app.include_router(tasks_router)
app.include_router(graph_router)