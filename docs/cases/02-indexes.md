# Кейс №2: Индексы

## Проблема

Поиск по полю `title` без индекса выполняется медленно → используется полный скан таблицы.

## Данные

~2000 строк

## Без индекса

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 1500';

→ Seq Scan
→ ~0.343 ms

## Решение

CREATE INDEX idx_tasks_title ON tasks(title);

## С индексом

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 1500';

→ Index Scan
→ ~0.136 ms

## Результат

- Seq Scan заменился на Index Scan
- время выполнения уменьшилось

## Вывод

Индекс позволяет ускорить поиск по полю за счёт отказа от полного сканирования таблицы.