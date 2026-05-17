import asyncio
import asyncpg
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.graph import GraphNode, GraphEdge
from app.models.task import Task
from app.schemas.graph import GraphNodeCreate, GraphEdgeCreate
from app.schemas.task import TaskCreate, TaskUpdate

app = FastAPI()


# ========== HEALTH & UTILS ==========
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/db_check")
async def db_check():
    try:
        conn = await asyncpg.connect(settings.database_url)
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== TASKS ==========

@app.get("/tasks")
async def get_tasks(db: AsyncSession = Depends(get_db)):
    """Вернуть все задачи из БД"""
    result = await db.execute(select(Task))
    tasks = result.scalars().all()  # запрос → список задач
    return tasks


@app.post("/tasks")
async def create_task(task_data: TaskCreate, db: AsyncSession = Depends(get_db)):
    """Создать новую задачу (статус new проставится автоматически)."""
    task = Task(title=task_data.title)
    db.add(task)
    await db.commit()
    await db.refresh(task)  # подтягиваем id после вставки
    return task


@app.get("/tasks/slow")
async def get_tasks_slow(db: AsyncSession = Depends(get_db)):
    """Вернуть все задачи с искусственной задержкой (демонстрация async)."""
    await asyncio.sleep(3)

    result = await db.execute(select(Task))
    tasks = result.scalars().all()  # запрос → все задачи списком
    return tasks


@app.get("/tasks/heavy")
async def get_tasks_heavy(db: AsyncSession = Depends(get_db)):
    """Тяжёлый запрос: сортировка по случайному числу (без индекса)."""
    result = await db.execute(select(Task).order_by(func.random()))
    tasks = result.scalars().all()  # запрос → все задачи списком
    return tasks


@app.get("/tasks/{task_id}")
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Вернуть одну задачу по id"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()  # запрос → одна задача или None
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}")
async def update_task(task_id: int, task_data: TaskUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить задачу по id с проверкой версии (оптимистичная блокировка)."""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()  # запрос → одна задача или None

    # 1. проверить, что задача существует
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 2. проверить версию
    if task.version != task_data.version:
        raise HTTPException(status_code=409, detail="Version conflict")
    
    # 3. обновить поля
    if task_data.title is not None:
        task.title = task_data.title
    if task_data.status is not None:
        task.status = task_data.status
    
    # 4. увеличить версию
    task.version += 1

    # 5. сохранить в БД
    await db.commit()
    await db.refresh(task)
    return task


# ========== GRAPH ==========

@app.post("/graph/nodes")
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


@app.post("/graph/edges")
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


@app.get("/graph/edges")
async def get_graph_edges(db: AsyncSession = Depends(get_db)):
    """Список всех рёбер графа."""
    result = await db.execute(select(GraphEdge))
    edges = result.scalars().all()  # запрос → список связей
    return edges


@app.get("/graph/walk/{node_id}")
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