# Кейс №2: Индексы

## Проблема

Поиск по полю `title` без индекса выполняется медленно → используется полный скан таблицы.

## Решение

Для ускорения запросов используются индексы:

- `idx_tasks_title` для поиска по полю `title`
- `idx_tasks_status` для фильтрации по полю `status`

---

## Сценарий 1

Данные: ~2к строк в таблице `tasks`
Индекс: `idx_tasks_title`

### Без индекса

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 1500';

→ Seq Scan
→ ~0.343 ms

### Добавляем индекс

CREATE INDEX idx_tasks_title ON tasks(title);

### С индексом

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 1500';

→ Index Scan
→ ~0.136 ms

### Результат

- Seq Scan заменился на Index Scan
- время выполнения уменьшилось

---

## Сценарий 2

Данные: ~20к строк в таблице `tasks`
Индекс: `idx_tasks_title`

### Без индекса

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 15000';

→ Seq Scan
→ ~2.276 ms

### С индексом

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 15000';

→ Index Scan
→ ~0.073 ms

### Результат

- при увеличении объёма данных разница становится значительно больше
- индекс даёт ощутимый прирост производительности

---

## Сценарий 3

Данные: ~20к строк в таблице `tasks`
Индекс: `idx_tasks_status`

Поле `status`:
- большинство строк: 'new'
- небольшая часть: 'done'

### Добавляем индекс

CREATE INDEX idx_tasks_status ON tasks(status);

### Низкая селективность

EXPLAIN ANALYZE SELECT * FROM tasks WHERE status = 'new';

→ Seq Scan
→ ~5.25 ms

### Высокая селективность

EXPLAIN ANALYZE SELECT * FROM tasks WHERE status = 'done';

→ Index Scan
→ ~0.098 ms

### Результат

- индекс не используется, если подходит большинство строк
- индекс используется, если подходит небольшое количество строк

---

## Дополнительно

Проверено на ~200к строк в таблице `tasks`
Индекс: `idx_tasks_title`

### Без индекса

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 150000';

→ Seq Scan
→ ~13.942 ms

### С индексом

EXPLAIN ANALYZE SELECT * FROM tasks WHERE title = 'task 150000';

→ Index Scan
→ ~0.046 ms

### Результат

Поведение сохраняется: при высокой селективности используется индекс, при низкой - нет.

---

## Вывод

Индекс ускоряет запросы, особенно когда данных становится больше.

Но он не всегда используется.

Если подходит много строк, PostgreSQL делает Seq Scan.

Если строк мало, используется Index Scan.

Всё зависит от данных и самого запроса.
