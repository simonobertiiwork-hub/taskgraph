"""Тесты AI endpoints."""


def test_decompose_task_returns_structured_result(client):
    response = client.post(
        "/ai/decompose",
        params={"title": "Добавить AI-модуль"},
    )

    assert response.status_code == 200

    data = response.json()

    assert "Добавить AI-модуль" in data["summary"]

    assert [subtask["local_id"] for subtask in data["subtasks"]] == [
        "analysis",
        "implementation",
        "tests",
    ]

    assert data["subtasks"][0]["depends_on"] == []
    assert data["subtasks"][1]["depends_on"] == ["analysis"]
    assert data["subtasks"][2]["depends_on"] == ["implementation"]