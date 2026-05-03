# Кейс №2: Индексы

## Проблема

Поиск по полю `title` без индекса выполняется медленно → используется полный скан таблицы.

## Сценарий 1

Данные: ~2000 строк в таблице `tasks`

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

---

## Сценарий 2

Данные: ~20000 строк в таблице `tasks`

## Без индекса

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 15000';

→ Seq Scan
→ ~2.276 ms

## С индексом

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 15000';

→ Index Scan
→ ~0.073 ms

## Результат

- при увеличении объёма разница становится значительно больше
- индекс даёт ощутимый прирост производительности

## Вывод

Индекс ускоряет поиск по полю за счёт отказа от полного сканирования таблицы.