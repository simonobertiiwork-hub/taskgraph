"""API роутеры."""

from app.routers.tasks import router as tasks_router
from app.routers.graph import router as graph_router

__all__ = [
    "tasks_router",
    "graph_router",
]