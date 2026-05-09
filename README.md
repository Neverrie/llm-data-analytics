# LLM Data Analyst

Учебный production-like проект `Neverrie/llm-data-analytics`: чатовый ассистент для анализа датасетов через LLM.

Проект включает:
- Web клиент (Next.js)
- Android клиент (Jetpack Compose)
- Backend (FastAPI)
- Dataset-agent с выполнением Python-кода в sandbox
- Отображение результатов в чате: `markdown`, графики, таблицы, файлы, шаги выполнения

## 1) Кратко о проекте

Пользователь общается с ассистентом в чате, выбирает датасет и задаёт аналитические вопросы. Backend маршрутизирует запрос:
- либо отвечает без выполнения кода,
- либо запускает dataset-agent, который через tool-calling вызывает `run_python(code)`.

Python-код выполняется в sandbox, а результаты сохраняются как артефакты и message blocks для Web/Android UI.

## 2) Архитектура

```text
User
  -> Web / Android
  -> FastAPI backend
  -> Chat router
     -> answer_directly
     -> analyze_with_code
        -> LangChain tool-calling agent
        -> run_python(code)
        -> Docker sandbox
        -> stdout / stderr / files
        -> artifact service
        -> message blocks
  -> UI render
```

Ключевые моменты:
- **LangChain** используется как абстракция LLM-моделей, сообщений и tool-calling.
- Основной режим: `LAB3_CODE_INTERPRETER_ENGINE=tool_calling`.

## 3) Dataset-agent flow

1. Router определяет маршрут (`answer_directly` или `analyze_with_code`).
2. Для `analyze_with_code` агент получает tool `run_python`.
3. LLM вызывает `run_python(code)`.
4. Backend исполняет код в sandbox.
5. Tool возвращает structured JSON (`status/stdout/stderr/files/elapsed_seconds`).
6. LLM формирует финальный ответ.
7. Backend сохраняет blocks: `markdown`, `code`, `execution`, `chart`, `table`, `file`, `warning`.

Важно:
- Backend **не генерирует аналитический fallback-код** вместо модели.
- Если LLM не вызвал `run_python` в analytical path — это contract error.
- Источник истины по файлам: `execution.files` и зарегистрированные `artifacts`, а не текст модели.

## 4) Sandbox

Исполнители:
- `DockerSandboxRunner` (основной)
- `LocalSubprocessRunner` (dev fallback)

Docker runner:
- запускается из backend-контейнера через host Docker daemon (docker socket)
- требует docker CLI внутри backend image
- использует sandbox image: `llm-data-analytics-sandbox:latest`
- одноразовый контейнер на запуск
- ограничения: `--network none`, `--cap-drop ALL`, non-root user, лимиты CPU/RAM/PIDs/time

Переменные:
```env
SANDBOX_RUNNER_MODE=docker
SANDBOX_DOCKER_IMAGE=llm-data-analytics-sandbox:latest
SANDBOX_DOCKER_USER=1000:1000
SANDBOX_ALLOW_ROOT_RETRY=false
HOST_OUTPUTS_DIR=/absolute/path/to/project/outputs
HOST_DATASETS_DIR=/absolute/path/to/project/datasets
```

Пути:
- `OUTPUTS_DIR=/outputs` — путь **внутри backend container**
- `HOST_OUTPUTS_DIR` — путь **на host**, нужен для bind mount в sandbox run

Windows пример:
```env
HOST_OUTPUTS_DIR=D:/Projects/llm-data-analytics-final/outputs
HOST_DATASETS_DIR=D:/Projects/llm-data-analytics-final/datasets
```

## 5) Troubleshooting sandbox

Проверки:
```bash
docker compose exec backend which docker
docker compose exec backend docker version
docker compose exec backend docker image inspect llm-data-analytics-sandbox:latest
```

Если docker CLI missing в backend:
```bash
docker compose build --no-cache --pull backend
docker compose up -d --force-recreate --no-deps backend
```

Если ошибка вида `/app/D:/...`:
- Проверьте `HOST_OUTPUTS_DIR` / `HOST_DATASETS_DIR`.
- Для Windows это host-path (`D:/...`), его нельзя «резолвить» как Linux путь внутри контейнера.

Если `dataset not found`:
- public datasets: `/datasets`
- uploaded datasets: `/outputs/users/<user_id>/datasets`
- resolver должен уметь оба источника.

## 6) LLM providers

Текущий рабочий провайдер в проекте:
- `openrouter`

OpenRouter:
```env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=
OPENROUTER_MODEL=qwen/qwen3.6-flash
OPENROUTER_FALLBACK_MODELS=qwen/qwen3.5-plus-20260420
LAB3_CODE_INTERPRETER_ENGINE=tool_calling
```

## 7) Dataset storage

Типы датасетов:

1. Public/common datasets:
- хранятся в `/datasets`
- доступны всем пользователям

2. Uploaded/private datasets:
- хранятся в `/outputs/users/<user_id>/datasets`
- доступны только владельцу

Backend использует dataset resolver:
- сначала lookup в registry (private/public)
- затем fallback к public `/datasets`
- path traversal запрещён
- dataset reference всегда должен быть scoped текущим пользователем

## 8) Chat context

- Каждый чат имеет `chat_id`.
- Для dataset-agent: `effective_session_id = chat_id`.
- Backend не должен доверять внешнему `session_id`, если он отличается от `chat_id`.
- Conversation context строго scoped по `chat_id`.
- История/артефакты/ошибки из других чатов не должны попадать в prompt.

Follow-up intent resolver:
- `retry_previous_task`
- `continue_previous_task`
- `refine_previous_answer`
- `new_task`

Пример:
- "попробуй ещё раз" продолжает последнюю аналитическую задачу **в этом же чате**.
- новый чат не наследует контекст старого.

## 9) Message blocks / UI rendering

Поддерживаемые block types:
- `markdown`
- `chart`
- `table`
- `file`
- `code`
- `execution`
- `warning`

Рекомендуемый порядок в assistant message:
1. markdown summary
2. chart/image blocks
3. table/file blocks
4. execution steps accordion

UI принципы:
- код скрыт по умолчанию
- execution steps — collapsible
- preview изображений через auth-aware запрос
- download через authenticated fetch, не через «голый» `<a href>`

## 10) SSE events

Используются события:
- `run_started`
- `message_delta`
- `tool_log`
- `code_preview`
- `code_executed`
- `artifact_created`
- `cancelled`
- `error`
- `done`

## 11) Stop / cancel request

Поддержка остановки запроса:
- Web: кнопка "Остановить" + `AbortController`
- Backend endpoint:
  - `POST /api/agent-runs/{run_id}/cancel`
- Для Docker-runner отмена останавливает sandbox container по `run_id/container name`

## 12) Android specifics

Актуальный поток для dataset-agent:
- использовать `POST /api/chats/{chat_id}/agent/stream`
- после `done` выполнять `syncChat(chatId)`
- `GET /api/lab3/result` не источник истины для чатового UI
- нельзя подмешивать глобальный `lab3_result` в UI текущего чата

## 13) Quick start

```bash
docker compose up -d --build
```

После старта:
- Frontend: `http://localhost:3003`
- Backend health: `http://localhost:8003/api/health`
- Swagger: `http://localhost:8003/docs`

Проверка конфигурации backend:
```bash
docker compose exec backend python -c "from app.config import settings; print(settings.llm_provider); print(settings.openrouter_model); print(settings.lab3_code_interpreter_engine)"
```

Проверка docker из backend:
```bash
docker compose exec backend docker version
```

## 14) Security notes

- API keys храните только в `.env`.
- Не коммитьте ключи в git.
- Mount `docker.sock` — **dev-only** подход.
- Для production лучше выносить sandbox в отдельный sandbox-manager service.
- Sandbox должен работать без сети и с жёсткими resource limits.

---

## Структура проекта

- `frontend/` — Next.js workspace UI
- `backend/` — FastAPI backend
- `android-app/` — Android Compose client
- `datasets/` — built-in datasets
- `outputs/` — SQLite, run artifacts, uploaded datasets


## Lab 2 — API-пайплайн: данные → LLM → JSON

Реализация:

```text
backend/app/services/lab2_service.py

Lab 2 реализует автоматический pipeline:

CSV/XLSX dataset → LLM API → structured JSON result

Пайплайн:

Читает датасет отзывов из /datasets.
Берёт текст отзыва из колонки content.
Отправляет данные в LLM через API батчами.
Получает строгий JSON-ответ.
Валидирует структуру, row_id, дубли и пропущенные строки.
Сохраняет результат в:
/outputs/lab2_result.json

Основные endpoints:

GET  /api/lab2/sample
POST /api/lab2/run
GET  /api/lab2/result

Датасет задаётся через .env:

LAB2_DATASET_FILENAME=customers_reviews

Пример файла:

datasets/customers_reviews.csv