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

Docker sandbox (backend внутри контейнера):
- `HOST_OUTPUTS_DIR=/absolute/path/to/project/outputs`
- `HOST_DATASETS_DIR=/absolute/path/to/project/datasets`

Пример для Windows:
- `HOST_OUTPUTS_DIR=D:/Projects/llm-data-analytics-final/outputs`
- `HOST_DATASETS_DIR=D:/Projects/llm-data-analytics-final/datasets`

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

## Sandbox и защита от prompt injection

### Зачем нужен sandbox
LLM может сгенерировать произвольный Python-код. Без изоляции это риск:
- чтение чувствительных файлов (`.env`, ssh-ключи, системные директории),
- сетевые запросы наружу (утечка данных),
- запуск подпроцессов и системных команд,
- бесконечные/тяжелые вычисления, перегрузка сервера.

Sandbox нужен, чтобы разрешить полезные аналитические действия (pandas, numpy, matplotlib), но запретить все, что выходит за рамки анализа данных.

### Как реализовано в проекте
- Код выполняется backend-сервисом, не на клиенте.
- Для каждого запуска создается отдельная run-директория в `outputs/lab3/code_runs/<run_id>`.
- В окружение выполнения передаются только необходимые данные:
  - `df` (если выбран датасет),
  - рабочая `output_dir` для результатов.
- Графики автоматически сохраняются как `plot_*.png` (в т.ч. при `plt.show()`), чтобы их можно было зарегистрировать как артефакты и отдать в UI.

### Ограничения выполнения
- Таймаут выполнения кода.
- Ограничение на размер stdout/stderr.
- Ограничение на количество и размер создаваемых файлов.
- Запрещены опасные импорты/операции (включая доступ к ОС, сеть, subprocess и т.д. — по правилам sandbox).

### Поток выполнения (end-to-end)
1. Пользователь пишет запрос.
2. LLM в planner-режиме решает: нужен код или обычный текст.
3. Если нужен код:
   - код отправляется в sandbox,
   - backend исполняет и получает `status/stdout/stderr/files`.
4. При ошибке backend запускает ограниченный цикл самокоррекции (retry).
5. Успешные файлы регистрируются в `artifacts` (БД + preview/download endpoints).
6. В SSE отправляется `artifact_created` с `artifact_id`, `mime_type`, `preview_url`.
7. Web/Android рендерят изображение/таблицу прямо в чате.

### Где здесь prompt injection
Prompt injection в датасете/сообщениях — это попытка заставить модель:
- игнорировать системные инструкции,
- выполнить вредный код,
- вывести секреты,
- сделать сетевой exfiltration.

В этом проекте защита многоуровневая:
- Системный промпт и протокол тегов (`<PYTHON>`, `<FINAL>`) ограничивают формат ответа модели.
- Код всегда идет через sandbox, а не напрямую в систему.
- Результаты проходят через backend-контроль и регистрацию артефактов.
- Артефактные пути валидируются и ограничены разрешенными директориями.
- Клиенты получают только то, что backend разрешил и зарегистрировал.

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
