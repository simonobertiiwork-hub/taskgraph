import time
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from app.core.handlers import register_exception_handlers
from app.api import health_router, tasks_router, graph_router


app = FastAPI(
    title="TaskGraph API",
    description="Graph-based domain model",
    version="0.8.0"
)

# регистрация обработчиков ошибок
register_exception_handlers(app)


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


# ========== CORS ==========

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== ROUTERS ==========

app.include_router(health_router)
app.include_router(tasks_router)
app.include_router(graph_router)