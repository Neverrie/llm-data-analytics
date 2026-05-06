# LLM Data Analyst

Production-like учебный проект: **web + backend + android** для диалога с LLM, выполнения Python-кода в sandbox и отображения артефактов (графики, таблицы, отчеты) в чате.

## Что внутри
- `frontend/` — Next.js (workspace UI)
- `backend/` — FastAPI (auth, chats, datasets, artifacts, lab2/lab3)
- `android-app/` — Android клиент
- `datasets/` — встроенные и загруженные датасеты
- `outputs/` — результаты, артефакты, SQLite (`outputs/app.db`)

## Ключевые возможности
- Единый workspace: чаты, датасеты, артефакты, настройки.
- 2 режима чата:
  - **General chat** (без датасета): обычный ассистент + опциональный запуск кода в sandbox.
  - **Dataset agent** (с датасетом): анализ данных через Lab3 agent.
- SSE-стриминг ответов и инструментальных событий.
- Артефакты регистрируются в backend и доступны через `/api/artifacts/*`.
- В чате отображаются пользовательские результаты (картинки/таблицы), технические trace-файлы скрываются из основной ленты.

## Быстрый старт
```bash
docker compose up --build -d
```

После старта:
- Frontend: `http://localhost:3003`
- Backend health: `http://localhost:8003/api/health`
- Swagger: `http://localhost:8003/docs`

## Конфигурация (`.env`)
Создать из шаблона:
```bash
cp .env.example .env
```

Минимум:
- `LLM_PROVIDER=openrouter` (или `ollama`)
- `OPENROUTER_API_KEY=...` (если OpenRouter)
- `OPENROUTER_MODEL=openai/gpt-oss-120b:free`

### Важно про URL API
Фронтенд поддерживает авто-режим:
- если открыт `localhost`/`127.0.0.1` -> backend `http://localhost:8003/api`
- если открыт по публичному IP/домену -> backend `http(s)://<тот же хост>:8003/api`

Можно задать вручную:
- `NEXT_PUBLIC_API_BASE_URL=http://<host>:8003/api`

CORS:
- `CORS_ORIGINS=http://localhost:3003,http://127.0.0.1:3003,http://<PUBLIC_IP>:3003`

## Доступ по публичному IP
Порты опубликованы через docker compose:
- frontend: `3003`
- backend: `8003`

Проверка:
- `http://<PUBLIC_IP>:3003`
- `http://<PUBLIC_IP>:8003/api/health`

## Аутентификация
Demo-аккаунт:
- email: `demo@example.com`
- password: `demo`

Основные auth endpoints:
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/demo-login`
- `GET /api/auth/me`

## Lab2 / Lab3
- Lab2 pipeline: анализ customer reviews через API.
- Lab3 agent: семантический анализ датасета, code interpreter, отчеты, графики.

### Code interpreter (кратко)
- Модель возвращает код, backend выполняет в sandbox.
- Sandbox ограничивает опасные операции (файловая система/сеть/исполнение).
- Результаты выполнения и созданные файлы возвращаются в ответ и регистрируются как артефакты.

## SSE события
Для стриминга используются события:
- `message_start`
- `message_delta`
- `tool_start`
- `tool_log`
- `tool_end`
- `artifact_created` (с `artifact_id`, `title`, `mime_type`, `preview_url`)
- `done`
- `error`

## Android
Базовый URL по умолчанию можно менять в настройках приложения.
Рекомендуется указывать:
- локально: `http://10.0.2.2:8003` (эмулятор)
- устройство в сети: `http://<LAN_IP>:8003`
- удаленно: `http://<PUBLIC_IP>:8003`

## Полезные команды
Пересборка backend:
```bash
docker compose up -d --build backend
```

Пересборка frontend:
```bash
docker compose up -d --build frontend
```

Проверка Android-сборки:
```bash
cd android-app
./gradlew :app:compileDebugKotlin
```

## Структура данных и безопасность
- SQLite: `outputs/app.db`
- Артефакты доступны только авторизованному пользователю.
- Пути к файлам валидируются, чтение ограничено разрешенными директориями.

## Примечание
Если меняете env-переменные, перезапускайте соответствующий контейнер с `--build`.
