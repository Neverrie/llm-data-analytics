# LLM Data Analyst (Rebuild)

Минимальная версия проекта после очистки legacy-агентов.

## Current stack
- `frontend/` — Next.js UI
- `backend/` — FastAPI API
- `android-app/` — Android client (временная совместимость)

## Backend runtime
- Auth/chat/datasets/artifacts API
- SQLite в `outputs/app.db`
- Docker sandbox execution core

## Sandbox core
Код исполняется только через sandbox-слой:
- `backend/app/sandbox/models.py`
- `backend/app/sandbox/runner.py`
- `backend/app/sandbox/docker_runner.py`
- `backend/app/sandbox/factory.py`

`DockerSandboxRunner` запускает одноразовый контейнер с ограничениями:
- `--network none`
- `--cap-drop ALL`
- `--security-opt no-new-privileges`
- memory/cpu/pids/time limits

Dev endpoint:
- `POST /api/dev/sandbox/run`

## MCP-like tools layer
Добавлен in-process MCP-like dispatcher поверх sandbox:
- `backend/app/mcp/models.py`
- `backend/app/mcp/tools.py`
- `backend/app/mcp/server.py`

Доступный tool:
- `run_python(code, dataset_path?, run_id?)`

Dev endpoints:
- `GET /api/dev/mcp/tools`
- `POST /api/dev/mcp/call`

Этот слой:
- не зависит от LLM
- не генерирует код
- только валидирует аргументы и выполняет переданный Python через sandbox

## Env
Ключевые переменные:

```env
OUTPUTS_DIR=/outputs
DATASETS_DIR=/datasets
HOST_OUTPUTS_DIR=D:/Projects/.../outputs
HOST_DATASETS_DIR=D:/Projects/.../datasets
SANDBOX_DOCKER_IMAGE=llm-data-analytics-sandbox:latest
SANDBOX_DOCKER_USER=1000:1000
```

## Run

```bash
docker compose up -d --build
```

## Next stage
Следующий этап: Qwen agent loop будет вызывать `run_python` через MCP-like слой.

Внешний настоящий MCP transport можно добавить позже, не меняя sandbox core.
