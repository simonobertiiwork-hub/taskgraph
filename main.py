import time
import asyncpg
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.routers import tasks_router, graph_router


app = FastAPI()

# ========== METRICS ==========

REQUESTS = Counter("http_requests_total", "Total requests", ["method", "endpoint"])
LATENCY = Histogram("http_request_duration_seconds", "Request latency", ["method", "endpoint"])


@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    REQUESTS.labels(method=request.method, endpoint=request.url.path).inc()
    LATENCY.labels(method=request.method, endpoint=request.url.path).observe(duration)
    return response


@app.get("/metrics")
async def get_metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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