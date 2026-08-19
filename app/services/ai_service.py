from app.schemas.ai import AIDecompositionResult


def decompose_task(title: str) -> AIDecompositionResult:
    """Возвращает тестовую декомпозицию задачи.

    Позже тело функции будет заменено вызовом LLM.
    """

    return AIDecompositionResult.model_validate(
        {
            "summary": f"Задача «{title}» разделена на этапы",
            "subtasks": [
                {
                    "local_id": "analysis",
                    "title": "Проанализировать требования",
                    "depends_on": [],
                },
                {
                    "local_id": "implementation",
                    "title": "Реализовать изменения",
                    "depends_on": ["analysis"],
                },
                {
                    "local_id": "tests",
                    "title": "Добавить и запустить тесты",
                    "depends_on": ["implementation"],
                },
            ],
        }
    )