import pytest
from pydantic import ValidationError

from app.schemas.ai import AIDecompositionResult


def test_valid_ai_decomposition():
    result = AIDecompositionResult.model_validate(
        {
            "summary": "Задача разделена на три этапа",
            "subtasks": [
                {
                    "local_id": "implementation",
                    "title": "Реализовать изменения",
                    "depends_on": [],
                },
                {
                    "local_id": "tests",
                    "title": "Добавить тесты",
                    "depends_on": ["implementation"],
                },
                {
                    "local_id": "release",
                    "title": "Подготовить релиз",
                    "depends_on": ["tests"],
                },
            ],
        }
    )

    assert result.summary == "Задача разделена на три этапа"
    assert len(result.subtasks) == 3
    assert result.subtasks[1].depends_on == ["implementation"]


def test_rejects_unknown_dependency():
    with pytest.raises(
        ValidationError,
        match="Неизвестные зависимости",
    ):
        AIDecompositionResult.model_validate(
            {
                "summary": "Некорректная декомпозиция",
                "subtasks": [
                    {
                        "local_id": "tests",
                        "title": "Добавить тесты",
                        "depends_on": ["missing"],
                    }
                ],
            }
        )


def test_rejects_duplicate_local_id():
    with pytest.raises(
        ValidationError,
        match="local_id должен быть уникальным",
    ):
        AIDecompositionResult.model_validate(
            {
                "summary": "Некорректная декомпозиция",
                "subtasks": [
                    {
                        "local_id": "task",
                        "title": "Первая задача",
                        "depends_on": [],
                    },
                    {
                        "local_id": "task",
                        "title": "Вторая задача",
                        "depends_on": [],
                    },
                ],
            }
        )


def test_rejects_self_dependency():
    with pytest.raises(
        ValidationError,
        match="не может зависеть сама от себя",
    ):
        AIDecompositionResult.model_validate(
            {
                "summary": "Некорректная декомпозиция",
                "subtasks": [
                    {
                        "local_id": "task",
                        "title": "Задача",
                        "depends_on": ["task"],
                    }
                ],
            }
        )