# Step 3 — RAG + Race Condition

Распакуйте архив в `C:\projects\taskgraph` с заменой файлов. Работайте в ветке
`feature/ai-incident-analyst`.

## 1. Пересобрать контейнер и применить миграцию

```bat
docker compose down
docker compose build app
docker compose up -d db ollama app
docker compose exec app alembic upgrade head
```

PostgreSQL теперь запускается из образа `pgvector/pgvector:pg15`. Существующий
volume остаётся тем же; миграция создаёт расширение `vector` и таблицу
`ai_document_chunks`.

## 2. Проверить тесты

```bat
docker compose exec app python -m pytest -q
```

Ожидается не меньше `78 passed, 1 skipped`.

## 3. Построить RAG-индекс

```bat
docker compose exec app python -m demos rag-index
```

Ожидаемый конец: `Result: PASSED`. Повторный запуск должен показать
`changed: 0`: это проверка инкрементальной индексации.

## 4. Создать свежий Race Condition run

```bat
docker compose exec app python -m demos race-condition --confirm-write
```

Ожидаемый конец: `Result: PASSED`.

## 5. Запустить AI-анализ второго сценария

```bat
docker compose exec app python -m demos ai-incident-analyst --scenario race-condition
```

Ожидаемый конец:

```text
Selected tools: get_concurrency_metrics
Validation errors: 0
Documentation sources: 1
Result: PASSED
```

Число источников может быть от 1 до 5. Если оно равно 0, сам evidence-отчёт
всё равно остаётся валидным, но нужно прислать `report.json` для проверки
порога релевантности.

Пока не коммитьте. Пришлите скриншот последних строк шага 5 либо архив самой
свежей папки `demos\results\ai_incident_analyst\...`.
