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
4. Разбивает на batch-ы (`batch_size`)
5. Отправляет batch в Ollama (`/api/generate`, `stream=false`, `format=json`)
6. Валидирует результат через Pydantic
7. Сохраняет общий результат в `outputs/lab2_result.json`

## Lab 3: Universal Analytics Agent

Lab 3 поддерживает универсальный анализ CSV/XLSX и upload датасетов.

Ключевые возможности:

- semantic column mapping (включая `target_column`)
- user overrides для ролей колонок
- allowlisted tools
- режимы `fast` / `balanced` / `full`
- trace и отчёты в `outputs/lab3`
- session context для follow-up вопросов (`outputs/lab3/sessions`)
- markdown-ответы в workspace UI
- исправлен warning pandas date parsing в column mapper

Режимы:

- `fast`: только heuristics + rule-based planner + один LLM-вызов для финального ответа
- `balanced`: LLM planner + финальный ответ (+ critic опционально)
- `full`: LLM-assisted mapping + LLM planner + финальный ответ (+ critic опционально)

В ответе `/api/lab3/ask`:

- `analysis_mode`
- `llm_calls_count`
- `elapsed_seconds`
- `warnings`

### Upload endpoint

- `POST /api/lab3/upload-dataset`
- Форматы: `.csv`, `.xlsx`, `.xls`
- Ограничение: 20 MB
- Сохранение: `datasets/uploads`
- Безопасная обработка имени файла (без path traversal)

### Основные endpoints Lab 3

- `GET /api/lab3/status`
- `GET /api/lab3/datasets`
- `POST /api/lab3/upload-dataset`
- `GET /api/lab3/profile?dataset_name=...`
- `POST /api/lab3/map-columns`
- `GET /api/lab3/tools`
- `POST /api/lab3/run-tool`
- `POST /api/lab3/ask`
- `GET /api/lab3/session?session_id=...`
- `POST /api/lab3/reset-session`
- `GET /api/lab3/result`
- `GET /api/lab3/download-report`

### Модели

- `LAB3_PLANNER_MODEL=qwen3:8b`
- `LAB3_TOOL_CALLER_MODEL=qwen2.5-coder:7b`
- `LAB3_CRITIC_MODEL=deepseek-r1:8b`

Установка моделей:

```bash
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:8b
```

### Безопасность

- CSV-строки считаются только данными, а не инструкциями
- Выполняются только tools из allowlist
- Нет произвольного выполнения Python-кода из ответа LLM
- Аргументы tools валидируются
- Чувствительные колонки (`username`, `image`) исключаются из контекста LLM

## Переменные окружения

- `OLLAMA_BASE_URL` (по умолчанию `http://host.docker.internal:11434`)
- `OLLAMA_MODEL` (по умолчанию `qwen3:8b`)
- `LAB2_DATASET_FILENAME` (по умолчанию `customer_reviews`)
- `LAB3_PLANNER_MODEL` (по умолчанию `qwen3:8b`)
- `LAB3_TOOL_CALLER_MODEL` (по умолчанию `qwen2.5-coder:7b`)
- `LAB3_CRITIC_MODEL` (по умолчанию `deepseek-r1:8b`)
- `DATASETS_DIR`
- `OUTPUTS_DIR`
