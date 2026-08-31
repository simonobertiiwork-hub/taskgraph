# Step 4 — Pool Exhaustion + 20 AI evals

Распакуйте архив в `C:\projects\taskgraph` с заменой файлов. Ветка остаётся
`feature/ai-incident-analyst`.

## 1. Запустить контейнеры

```bat
docker compose up -d db ollama app
```

## 2. Проверить тесты

```bat
docker compose exec app python -m pytest -q
```

Ожидается не меньше `79 passed, 1 skipped`.

## 3. Воспроизвести Pool Exhaustion

```bat
docker compose exec app python -m demos pool-exhaustion --confirm-load
```

Ожидаемый конец:

```text
Before pool timeouts: 3
After pool timeouts: 0
Result: PASSED
```

## 4. Обновить RAG и запустить AI-анализ

```bat
docker compose exec app python -m demos rag-index
docker compose exec app python -m demos ai-incident-analyst --scenario pool-exhaustion
```

Ожидаемый конец AI-запуска:

```text
Selected tools: get_pool_metrics
Validation errors: 0
Documentation sources: 1
Result: PASSED
```

Источников может быть от 1 до 5.

## 5. Выполнить 20 offline evals

```bat
docker compose exec app python -m demos ai-evals
```

Ожидаемый результат:

```text
Cases: 20
Tool selection accuracy: 100.0%
Completion rate: 100.0%
Grounding rate: 100.0%
Result: PASSED
```

Пока не коммитьте. Пришлите один скриншот последних строк шагов 3–5.
