"""
Интеграционные и валидационные тесты для графа.

Покрывает:
- создание вершин
- создание рёбер
- обнаружение цикла (400 Bad Request)
- рекурсивный обход графа
- обход от несуществующей вершины (404)
"""

import pytest


class TestGraphAPI:
    """Тесты для /graph эндпоинтов."""

    def test_create_node(self, client):
        """Создание вершины графа - успех (200)."""
        response = client.post("/graph/nodes", json={"name": "Node A"})
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Node A"
        assert "id" in data

    def test_create_edge_success(self, client):
        """Создание ребра - успех (200)."""
        node1 = client.post("/graph/nodes", json={"name": "A"}).json()
        node2 = client.post("/graph/nodes", json={"name": "B"}).json()

        response = client.post(
            "/graph/edges",
            json={"parent_id": node1["id"], "child_id": node2["id"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parent_id"] == node1["id"]
        assert data["child_id"] == node2["id"]

    def test_create_edge_cycle_detected(self, client):
        """Валидация: попытка создать цикл → 400 Bad Request."""
        node1 = client.post("/graph/nodes", json={"name": "X"}).json()
        node2 = client.post("/graph/nodes", json={"name": "Y"}).json()

        client.post(
            "/graph/edges", 
            json={"parent_id": node1["id"], "child_id": node2["id"]}
        )

        response = client.post(
            "/graph/edges",
            json={"parent_id": node2["id"], "child_id": node1["id"]}
        )
        assert response.status_code == 400
        assert "Cycle detected" in response.json()["detail"]

    def test_walk_graph(self, client):
        """Рекурсивный обход графа - успех (200)."""
        a = client.post("/graph/nodes", json={"name": "A"}).json()
        b = client.post("/graph/nodes", json={"name": "B"}).json()
        c = client.post("/graph/nodes", json={"name": "C"}).json()

        client.post(
            "/graph/edges", 
            json={"parent_id": a["id"], "child_id": b["id"]}
        )
        client.post(
            "/graph/edges", 
            json={"parent_id": b["id"], "child_id": c["id"]}
        )

        response = client.get(f"/graph/walk/{a['id']}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["name"] == "A"
        assert data[1]["name"] == "B"
        assert data[2]["name"] == "C"

    def test_walk_node_not_found(self, client):
        """Валидация: обход от несуществующей вершины - 404."""
        response = client.get("/graph/walk/99999")
        assert response.status_code == 404
