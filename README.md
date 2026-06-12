# LLM Data Analyst

Веб-приложение для анализа датасетов с LLM-агентом, вызовом Python-инструментов и изолированным выполнением кода в Docker.

## Возможности

- регистрация, вход и демо-пользователь;
- создание, переименование и удаление чатов;
- сохранение истории сообщений и контекста агента;
- загрузка, preview, profile и удаление CSV/XLSX-датасетов;
- анализ данных через OpenRouter-совместимую LLM;
- function calling через внутренний MCP-like слой;
- выполнение Python-кода в одноразовых Docker-контейнерах;
- сохранение графиков, таблиц и файлов как артефактов;
- просмотр, скачивание и удаление артефактов;
- SSE-стрим событий агента и отмена активного запуска;
- светлая и тёмная темы.

## Архитектура

```text
Пользователь
  -> Next.js frontend
  -> FastAPI chat endpoint
  -> dataset agent loop
  -> OpenRouter / Qwen
  -> tool call: run_python
  -> in-process MCP-like dispatcher
  -> DockerSandboxRunner
  -> одноразовый Python sandbox
  -> stdout / stderr / files
  -> агент формирует финальный ответ
  -> сообщения и артефакты сохраняются в SQLite
```

Основные каталоги:

```text
frontend/                  Next.js UI
backend/app/agents/        агентный цикл и модели результата
backend/app/llm/           OpenRouter/OpenAI-compatible клиент
backend/app/mcp/           инструменты и dispatcher
backend/app/sandbox/       интерфейс и Docker sandbox runner
backend/app/routers/       FastAPI endpoints
backend/app/services/      бизнес-логика чатов, auth и артефактов
backend/sandbox.Dockerfile образ Python sandbox
docker-compose.yml         локальный запуск проекта
```

## Требования

- Docker Desktop с Linux containers;
- Docker Compose v2;
- доступ Docker Desktop к диску проекта;
- OpenRouter API key;
- Windows PowerShell или другой терминал.

Node.js и Python на host не обязательны для стандартного Docker-запуска.

## Настройка

Создайте локальный `.env` на основе `.env.example`:

```powershell
Copy-Item .env.example .env
```

Обязательные значения:

```env
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=qwen/qwen3.6-flash

HOST_OUTPUTS_DIR=D:/absolute/path/to/project/outputs
HOST_DATASETS_DIR=D:/absolute/path/to/project/datasets
```

Windows-пути должны быть абсолютными, использовать прямые слеши и указывать на реальные каталоги проекта.

Остальные переменные:

```env
CORS_ORIGINS=http://localhost:3003,http://127.0.0.1:3003
NEXT_PUBLIC_API_BASE_URL=auto

LLM_PROVIDER=openrouter
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

SANDBOX_DOCKER_IMAGE=llm-data-analytics-sandbox:latest
SANDBOX_DOCKER_USER=0:0
SANDBOX_ALLOW_NETWORK=true
SANDBOX_PYTHON_USERBASE_DIR=/outputs/.sandbox_userbase
SANDBOX_PIP_CACHE_DIR=/outputs/.sandbox_pip_cache

OUTPUTS_DIR=/outputs
DATASETS_DIR=/datasets
ENABLE_DEV_ENDPOINTS=false
```

Для доступа по внешнему IP добавьте frontend origin в `CORS_ORIGINS`. При `NEXT_PUBLIC_API_BASE_URL=auto` frontend обращается к backend на том же hostname и порту `8003`.

## Запуск

```powershell
docker compose up -d --build
```

После запуска:

- frontend: [http://localhost:3003](http://localhost:3003)
- backend API: [http://localhost:8003/api](http://localhost:8003/api)
- health check: [http://localhost:8003/api/health](http://localhost:8003/api/health)
- OpenAPI: [http://localhost:8003/docs](http://localhost:8003/docs)

Проверка контейнеров:

```powershell
docker compose ps
docker compose logs --tail 100 backend
docker compose logs --tail 100 frontend
```

Остановка:

```powershell
docker compose down
```

Данные сохраняются в локальных каталогах:

```text
outputs/app.db       SQLite
outputs/mcp_runs/    результаты запусков Python
datasets/            загруженные датасеты
```

## Sandbox

`DockerSandboxRunner` создаёт `script.py` в рабочем каталоге и запускает новый контейнер:

- `--rm`;
- `--cap-drop ALL`;
- `--security-opt no-new-privileges`;
- лимиты памяти, CPU, процессов и времени;
- рабочий каталог доступен как `/work`;
- выбранный датасет доступен только для чтения как `/input/dataset.csv`;
- stdout и stderr читаются через `subprocess.run(capture_output=True)`;
- созданные файлы возвращаются в структурированном результате.

Агент должен сохранять результаты только в `/work`, например:

```python
plt.savefig("/work/main_chart.png")
df.to_csv("/work/summary.csv", index=False)
```

При `SANDBOX_ALLOW_NETWORK=true` код может устанавливать пакеты:

```python
import subprocess
import sys

subprocess.check_call([
    sys.executable,
    "-m",
    "pip",
    "install",
    "--user",
    "package-name",
])
```

Пакеты сохраняются в `outputs/.sandbox_userbase` и доступны следующим запускам.

### Модель безопасности

Sandbox ограничивает ресурсы и capabilities, но при включённой сети и запуске от `0:0` это не строгая недоверенная среда. Для публичного развёртывания рекомендуется:

- установить `SANDBOX_ALLOW_NETWORK=false`;
- использовать непривилегированного пользователя после выравнивания прав bind mount;
- ограничить доступ к Docker socket отдельным proxy;
- не публиковать dev endpoints;
- добавить rate limiting и ограничения размера загружаемых файлов.

## MCP-like слой

Сейчас используется in-process dispatcher, не внешний MCP transport.

Доступный инструмент:

```text
run_python(code, dataset_path?, run_id?)
```

MCP-like слой:

- не генерирует Python-код;
- не анализирует данные;
- проверяет разрешённые пути;
- передаёт выполнение в sandbox;
- возвращает status, stdout, stderr, files и elapsed time.

## Агент

Агент получает:

- текущий запрос;
- последние сообщения чата;
- краткую информацию о прошлых execution-блоках;
- список существующих артефактов;
- путь выбранного датасета.

Цикл ограничен 30 шагами, но обычная задача ориентирована на 4–6 вызовов инструмента. После 6 шагов агент получает мягкую рекомендацию завершить анализ. Каждый запуск использует единый рабочий каталог, поэтому следующие действия могут продолжать предыдущие и обновлять созданные файлы.

За один ход разрешён один сфокусированный `run_python`. Слишком большой монолитный скрипт отклоняется с просьбой разделить работу. При ошибке Python stderr возвращается модели, чтобы она исправила конкретный сбой, не пересоздавая уже готовые артефакты. Если пользователь явно запросил `.md`, `.csv`, `.json` или `.xlsx`, цикл не считает задачу успешно завершённой без соответствующего файла.

Для аналитического запроса минимум один `run_python` обязателен. Backend не генерирует аналитический Python-код и не выполняет fallback-анализ самостоятельно.

## Основные API

Auth:

```text
POST /api/auth/register
POST /api/auth/login
POST /api/auth/demo-login
GET  /api/auth/me
```

Chats:

```text
GET    /api/chats
POST   /api/chats
GET    /api/chats/{chat_id}
PATCH  /api/chats/{chat_id}
DELETE /api/chats/{chat_id}
POST   /api/chats/{chat_id}/messages
POST   /api/chats/{chat_id}/messages/stream
POST   /api/chats/{chat_id}/cancel
```

Datasets:

```text
GET    /api/datasets
POST   /api/datasets/upload
GET    /api/datasets/{dataset_id}/preview
GET    /api/datasets/{dataset_id}/profile
DELETE /api/datasets/{dataset_id}
```

Artifacts:

```text
GET    /api/artifacts
GET    /api/artifacts/{artifact_id}
GET    /api/artifacts/{artifact_id}/preview
GET    /api/artifacts/{artifact_id}/download
DELETE /api/artifacts/{artifact_id}
```

## Диагностические endpoints

Они отключены по умолчанию. Для локальной разработки:

```env
ENABLE_DEV_ENDPOINTS=true
```

После перезапуска становятся доступны:

```text
POST /api/dev/sandbox/run
GET  /api/dev/mcp/tools
POST /api/dev/mcp/call
POST /api/dev/llm/chat
POST /api/dev/agent/run
```

Не включайте их на публичном сервере: sandbox, MCP и LLM endpoints не требуют пользовательской авторизации.

## Проверки

Полная Docker-сборка:

```powershell
docker compose up -d --build
```

Backend syntax:

```powershell
python -m compileall -q backend/app
```

Frontend production build внутри Docker:

```powershell
docker compose build frontend
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8003/api/health
```

Sandbox smoke test при `ENABLE_DEV_ENDPOINTS=true`:

```powershell
$body = @{
  code = "print('hello from sandbox')"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:8003/api/dev/sandbox/run `
  -ContentType "application/json" `
  -Body $body
```

Ожидаемый результат:

```json
{
  "status": "success",
  "stdout": "hello from sandbox\n",
  "stderr": "",
  "files": [],
  "exit_code": 0
}
```

## Troubleshooting

### Backend не может запустить sandbox

Проверьте:

```powershell
docker version
docker compose ps
docker exec llm-analytics-backend docker version
```

Backend должен иметь доступ к `/var/run/docker.sock`.

### Windows-путь превращается в `/app/D:/...`

Убедитесь, что `HOST_OUTPUTS_DIR` и `HOST_DATASETS_DIR` заданы абсолютными Windows-путями с прямыми слешами.

### `PermissionError` в `/work`

Все sandbox-запуски должны использовать одного пользователя. Текущая локальная конфигурация использует:

```env
SANDBOX_DOCKER_USER=0:0
```

### LLM не отвечает

Проверьте:

- `OPENROUTER_API_KEY`;
- точное имя `OPENROUTER_MODEL`;
- доступ backend-контейнера в интернет;
- `docker compose logs backend`.

### Frontend обращается не к тому backend

При `NEXT_PUBLIC_API_BASE_URL=auto`:

- `localhost:3003` использует `localhost:8003`;
- внешний hostname использует тот же hostname и порт `8003`.

Для фиксированного адреса задайте полный API URL:

```env
NEXT_PUBLIC_API_BASE_URL=http://example-host:8003/api
```
