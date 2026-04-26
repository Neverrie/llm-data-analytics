# llm-data-analytics-final

Учебный проект **LLM Data Analyst Lab** с веб-интерфейсом (Next.js) и backend API (FastAPI).

## Стек

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + Python
- LLM provider: Ollama (локально на хост-машине)

## Быстрый запуск (основной сценарий)

```bash
docker compose up --build
```

После запуска:

- Frontend: http://localhost:3003
- Backend API health: http://localhost:8003/api/health
- Swagger: http://localhost:8003/docs

## Задание 2 — API Pipeline

Lab 2 использует **Uber Customer Reviews Dataset (2024)**.

Как работает pipeline:

1. Backend читает датасет из `datasets`.
2. Использует `content` как текст отзыва.
3. Использует `score` как дополнительный сигнал и нормализует его.
4. Обрабатывает отзывы батчами (`batch_size`).
5. Вызывает Ollama API.
6. Парсит и валидирует JSON через Pydantic.
7. Сохраняет результат в `outputs/lab2_result.json`.

Параметры запуска Lab 2:

- `limit`: сколько отзывов обработать
- `batch_size`: сколько отзывов отправлять в одном запросе к модели
- `min_score` / `max_score`: фильтр по оценке

Пример результата JSON (фрагмент):

```json
{
  "lab": 2,
  "status": "success",
  "rows_processed": 10,
  "results": [
    {
      "row_id": 1,
      "sentiment": "negative",
      "issue_type": "payment_issue",
      "topic": "billing",
      "urgency": "high",
      "summary": "Пользователь жалуется на проблему с оплатой.",
      "suggested_action": "Проверить сценарии оплаты и возврата средств."
    }
  ]
}
```

## Задание 3 — Мини-продукт с LLM-аналитикой

Lab 3 — универсальный аналитический агент для CSV/XLSX-датасетов.

Ключевые возможности:

- semantic column mapping (автоопределение ролей колонок)
- user overrides для ручной корректировки ролей
- allowlisted tools (без произвольного кода)
- planner → tool-caller → critic pipeline
- экспорт отчётов в `outputs/lab3`
- agent trace в `outputs/lab3/agent_trace.json`

Роли колонок (пример):

- `text_column`
- `rating_column`
- `date_column`
- `version_column`
- `reply_column`
- `reply_date_column`

Модели Ollama:

- `qwen3:8b` (planner/final answer)
- `qwen2.5-coder:7b` (tool-caller)
- `deepseek-r1:8b` (critic)

Установить модели:

```bash
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:8b
```

Важно: при запуске backend в Docker обращается к Ollama на хосте через:

- `http://host.docker.internal:11434`

Примеры вопросов для Lab 3:

- Какие основные проблемы пользователи отмечают в низкооценённых отзывах?
- Есть ли ухудшение оценок со временем?
- Какие версии приложения выглядят проблемными?
- Есть ли отзывы, похожие на prompt injection?
- Какие темы чаще всего встречаются в негативных отзывах?

## Проверка Ollama

```bash
ollama list
```

## Полезные URL

- Lab 2: http://localhost:3003/lab2
- Lab 3: http://localhost:3003/lab3
- Lab 2 status: http://localhost:8003/api/lab2/status
- Lab 3 status: http://localhost:8003/api/lab3/status
- Lab 3 datasets: http://localhost:8003/api/lab3/datasets

## Примеры curl

Lab 2:

```bash
curl -X POST "http://localhost:8003/api/lab2/run" \
  -H "Content-Type: application/json" \
  -d '{"limit":5,"batch_size":5,"min_score":null,"max_score":null}'
```

```bash
curl -X POST "http://localhost:8003/api/lab2/run" \
  -H "Content-Type: application/json" \
  -d '{"limit":12,"batch_size":5,"min_score":null,"max_score":null}'
```

Lab 3:

```bash
curl -X POST "http://localhost:8003/api/lab3/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name":"customers_reviews.csv",
    "question":"Какие основные проблемы пользователи отмечают в низкооценённых отзывах?",
    "column_overrides":{},
    "max_tool_calls":8,
    "use_critic":true
  }'
```
