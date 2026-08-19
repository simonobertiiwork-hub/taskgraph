from fastapi import APIRouter

from app.schemas.ai import AIDecompositionResult
from app.services.ai_service import decompose_task


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/decompose",
    response_model=AIDecompositionResult,
)
async def decompose_task_endpoint(
    title: str,
) -> AIDecompositionResult:
    """Разделить задачу на связанные подзадачи."""

    return decompose_task(title)