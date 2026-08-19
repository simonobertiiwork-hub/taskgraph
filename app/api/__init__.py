"""API роутеры."""

from app.api.health import router as health_router
from app.api.tasks import router as tasks_router
from app.api.graph import router as graph_router
from app.api.ai import router as ai_router

__all__ = [
    "ai_router",
    "health_router",
    "tasks_router",
    "graph_router",
]