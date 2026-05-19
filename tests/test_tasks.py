"""
Интеграционные и валидационные тесты для задач.

Покрывает:
- создание задачи (успех)
- получение несуществующей задачи (404)
- список задач (пустой)
- конфликт версий при обновлении (409)
"""

import pytest


class TestTasksAPI:
    """Тесты для /tasks эндпоинтов."""

    def test_create_task(self, client):
        """Создание задачи - успех (200)."""
        response = client.post("/tasks", json={"title": "Test Task"})
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Task"
        assert data["status"] == "new"
        assert "id" in data
        assert "version" in data

    def test_get_task_not_found(self, client):
        """Валидация: получение несуществующей задачи - 404."""
        response = client.get("/tasks/99999")
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_get_tasks_empty(self, client):
        """Список задач (пустой) - 200."""
        response = client.get("/tasks")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_update_task_version_conflict(self, client):
        """Валидация: обновление с неверной версией - 409 Conflict."""
        create_resp = client.post("/tasks", json={"title": "Conflict Test"})
        task_uuid = create_resp.json()["id"]  # у задачи id, а не result_uuid
        version = create_resp.json()["version"]

        # первое обновление — успех
        resp1 = client.patch(
            f"/tasks/{task_uuid}",
            json={"title": "Updated", "version": version}
        )
        assert resp1.status_code == 200

        # второе обновление с той же версией - конфликт
        resp2 = client.patch(
            f"/tasks/{task_uuid}",
            json={"title": "Another", "version": version}
        )
        assert resp2.status_code == 409
        assert "Version conflict" in resp2.json()["detail"]