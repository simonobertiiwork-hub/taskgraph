"""
Тесты безопасности

Покрывает:
- защита от SQL-инъекций через параметризованные запросы
"""

import pytest


class TestSecurity:
    """Тесты безопасности API."""

    def test_sql_injection_in_title(self, client):
        """Проверка защиты от SQL-инъекций в поле title."""
        malicious_title = "test'; DROP TABLE tasks; --"
        response = client.post("/tasks", json={"title": malicious_title})
        assert response.status_code == 200

        # проверяем, что таблица tasks всё ещё существует
        tasks_response = client.get("/tasks")
        assert tasks_response.status_code == 200

    def test_sql_injection_in_mode_name(self, client):
        """Проверка защиты от SQL-инъекций в имени вершины графа."""
        malicious_name = "A; DROP TABLE graph_nodes; --"
        response = client.post("/graph/nodes", json={"name": malicious_name})
        assert response.status_code == 200

        # проверяем, что таблица graph_nodes всё ещё существует
        nodes_response = client.get("/graph/nodes")
        assert nodes_response.status_code == 200