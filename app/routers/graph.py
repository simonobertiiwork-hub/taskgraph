"""Роутер для графа (graph)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.graph import GraphNode, GraphEdge
from app.schemas.graph import GraphNodeCreate, GraphEdgeCreate

router = APIRouter(prefix="/graph", tags=["graph"])


@router.post("/nodes")
async def create_graph_node(
    node_data: GraphNodeCreate,
    db: AsyncSession = Depends(get_db),
):
    """Создать вершину графа."""
    node = GraphNode(name=node_data.name)
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


@router.post("/edges")
async def create_graph_edge(
    edge_data: GraphEdgeCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Создать ребро графа с проверкой на цикл.
    Запрещаем создание циклических зависимостей.
    """
    # проверяем, можно ли из child_id дойти до parent_id
    cycle_check_query = text("""
        WITH RECURSIVE path AS (
            SELECT child_id
            FROM graph_edges
            WHERE parent_id = :child_id

            UNION ALL

            SELECT e.child_id
            FROM graph_edges e
            JOIN path p ON e.parent_id = p.child_id
            WHERE p.child_id IS NOT NULL
        )
        SELECT child_id
        FROM path
        WHERE child_id = :parent_id
        LIMIT 1
    """)

    result = await db.execute(
        cycle_check_query,
        {"child_id": edge_data.child_id, "parent_id": edge_data.parent_id},
    )

    if result.first():
        raise HTTPException(
            status_code=400,
            detail="Cycle detected in graph (cannot create this edge)",
        )

    edge = GraphEdge(
        parent_id=edge_data.parent_id,
        child_id=edge_data.child_id,
    )
    db.add(edge)
    await db.commit()
    await db.refresh(edge)
    return edge


@router.get("/edges")
async def get_graph_edges(db: AsyncSession = Depends(get_db)):
    """Список всех рёбер графа."""
    result = await db.execute(select(GraphEdge))
    edges = result.scalars().all()  # запрос → список связей
    return edges


@router.get("/walk/{node_id}")
async def walk_graph(
    node_id: int,
    db: AsyncSession = Depends(get_db),
    max_depth: int = 10,
):
    """Рекурсивный обход графа от указанной вершины (с ограничением глубины)."""
    query = text("""
        WITH RECURSIVE graph_tree AS (
            SELECT gn.id, gn.name, 1 AS depth
            FROM graph_nodes gn
            WHERE gn.id = :node_id

            UNION ALL

            SELECT child.id, child.name, gt.depth + 1
            FROM graph_tree gt
            JOIN graph_edges ge ON ge.parent_id = gt.id
            JOIN graph_nodes child ON child.id = ge.child_id
            WHERE gt.depth < :max_depth
        )
        SELECT id, name, depth
        FROM graph_tree;
    """)
    result = await db.execute(query, {"node_id": node_id, "max_depth": max_depth})
    rows = result.mappings().all()  # запрос → список словарей
    return rows