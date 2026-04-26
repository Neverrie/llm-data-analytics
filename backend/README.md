# Backend (FastAPI)

Backend-часть проекта LLM Data Analyst Lab.

## Запуск через Docker Compose

Из корня репозитория:

```bash
docker compose up --build
```

Swagger:

- http://localhost:8003/docs

## Lab 2: API Pipeline

Pipeline:

1. Читает Uber Customer Reviews Dataset (2024)
2. Нормализует входные поля (включая `score`)
3. Фильтрует данные по `min_score`/`max_score`
4. Разбивает на batch-и (`batch_size`)
5. Отправляет batch в Ollama (`/api/generate`, `stream=false`, `format=json`)
6. Валидирует результат через Pydantic
7. Сохраняет общий результат в `outputs/lab2_result.json`

## Endpoint-ы

- `GET /api/lab2/status`
- `GET /api/lab2/sample-data?limit=5`
- `POST /api/lab2/run`
- `GET /api/lab2/result`
- `GET /api/lab2/download`

## Переменные окружения

- `OLLAMA_BASE_URL` (по умолчанию `http://host.docker.internal:11434`)
- `OLLAMA_MODEL` (по умолчанию `qwen3:8b`)
- `LAB2_DATASET_FILENAME` (по умолчанию `customer_reviews`)
- `DATASETS_DIR`
- `OUTPUTS_DIR`
