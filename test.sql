-- =============================================
-- ТЕСТ: цикл в графе и рекурсивный обход
-- =============================================

-- Очищаем таблицы
DELETE FROM graph_edges;
DELETE FROM graph_nodes;

-- Сбрасываем счётчики id
ALTER SEQUENCE graph_nodes_id_seq RESTART WITH 1;
ALTER SEQUENCE graph_edges_id_seq RESTART WITH 1;

-- 1. Добавим вершины
INSERT INTO graph_nodes (name) VALUES ('A'), ('B'), ('C');

-- 2. Создаём граф A → B → C (без цикла)
INSERT INTO graph_edges (parent_id, child_id) VALUES
    ((SELECT id FROM graph_nodes WHERE name = 'A'), (SELECT id FROM graph_nodes WHERE name = 'B')),
    ((SELECT id FROM graph_nodes WHERE name = 'B'), (SELECT id FROM graph_nodes WHERE name = 'C'));

-- 3. Рекурсивный обход от A (без цикла)
WITH RECURSIVE graph_tree AS (
    SELECT id, name, 1 AS depth 
    FROM graph_nodes 
    WHERE name = 'A'

    UNION ALL

    SELECT child.id, child.name, gt.depth + 1 
    FROM graph_tree gt
    JOIN graph_edges e ON e.parent_id = gt.id
    JOIN graph_nodes child ON child.id = e.child_id
)
SELECT id, name, depth
FROM graph_tree;

-- 4. Добавляем цикл: C → A
INSERT INTO graph_edges (parent_id, child_id) VALUES
    ((SELECT id FROM graph_nodes WHERE name = 'C'), (SELECT id FROM graph_nodes WHERE name = 'A'));

-- 5. Рекурсивный обход от A (с циклом, но ограниченный глубиной)
-- Результат: строки будут повторяться (A, B, C, A, B, C, ...) до глубины 10
WITH RECURSIVE graph_tree AS (
    SELECT id, name, 1 AS depth
    FROM graph_nodes
    WHERE name = 'A'

    UNION ALL

    SELECT child.id, child.name, gt.depth + 1
    FROM graph_tree gt
    JOIN graph_edges e ON e.parent_id = gt.id
    JOIN graph_nodes child ON child.id = e.child_id
    WHERE gt.depth < 10  -- ограничиваем глубину, чтобы не зависнуть
)
SELECT id, name, depth
FROM graph_tree;