# llm-data-analytics-final

Учебный проект **LLM Data Analyst Lab** с веб-интерфейсом (Next.js) и backend API (FastAPI).

## Стек

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + Python
- LLM provider: Ollama (локально на хост-машине)
- UI: чистый Material Design-like dashboard + переключаемые светлая/тёмная темы

## Быстрый запуск (основной сценарий)

```bash
docker compose up --build
```

После запуска:

- Frontend: http://localhost:3003
- Backend API health: http://localhost:8003/api/health
- Swagger: http://localhost:8003/docs

## OpenRouter setup

1. Создайте `.env` из шаблона:
`cp .env.example .env`
2. Заполните переменные:
- `OPENROUTER_API_KEY=your_key`
- `LLM_PROVIDER=openrouter`
- `OPENROUTER_MODEL=openai/gpt-oss-120b:free`
3. Запустите проект:
`docker compose up --build`

Важно: не коммитьте `.env`.

## Задание 2 — API Pipeline

Lab 2 использует **Uber Customer Reviews Dataset (2024)**.

Pipeline:

1. Backend читает датасет из `datasets`.
2. Использует `content` как текст отзыва.
3. Использует `score` как дополнительный сигнал и нормализует его.
4. Обрабатывает отзывы батчами (`batch_size`).
5. Вызывает Ollama API.
6. Парсит и валидирует JSON через Pydantic.
7. Сохраняет результат в `outputs/lab2_result.json`.

## Задание 3 — Мини-продукт с LLM-аналитикой

Lab 3 — универсальный аналитический агент для CSV/XLSX-датасетов.

Что добавлено:

- upload датасетов через UI (`/api/lab3/upload-dataset`), сохранение в `datasets/uploads`
- workspace UI: sidebar + chat-область вместо длинного вертикального скролла
- follow-up диалог с `session_id` и кратким session context
- markdown форматирование финального ответа во вкладке «Ответ»
- универсальный semantic column mapping (включая `target_column`)
- user overrides для ролей колонок
- человеко-понятные подписи ролей колонок в UI и подсказки «зачем нужна роль»
- режимы анализа:
  - `fast` (рекомендуется для демонстрации)
  - `balanced`
  - `full`
- универсальные quick scenarios для разных типов датасетов
- tools вынесены в Advanced-блок в UI
- allowlisted tools + защита от prompt injection
- исправлен warning date parsing в Docker логах (без `Could not infer format...`)

## Lab 3 Code Interpreter Mode

В режиме `code_interpreter` модель сама генерирует Python-код, backend выполняет код в sandbox, затем модель получает `stdout/stderr/files` и продолжает анализ.

Отличие от safe-tools mode:
- safe-tools mode: модель вызывает заранее определенные backend tools;
- code_interpreter mode: модель строит вычисления через собственный Python-код в sandbox loop.

Ограничения sandbox:
- запрещены опасные импорты (`os`, `subprocess`, `socket`, `requests` и др.);
- запрещены опасные токены (`open(`, `exec(`, `eval(`, `__import__`, `..` и др.);
- execution timeout 15 секунд;
- ограничение на размер stdout/stderr и количество/размер файлов.

### Роли колонок простым языком

Агент определяет роли колонок (текст, рейтинг, дата, целевая переменная и т.д.) и затем использует общий набор tools для любых CSV/XLSX.
Если автоопределение ошиблось, роль можно исправить вручную в блоке «Роли колонок».
Это делает анализ универсальным и не привязанным к конкретным названиям колонок.

### Режимы анализа

- `fast`: heuristic mapping + rule-based planner + один LLM-вызов для финального ответа.
- `balanced`: heuristic mapping + LLM planner + финальный ответ (+ critic опционально).
- `full`: heuristic + LLM-assisted mapping + LLM planner + финальный ответ (+ critic опционально).

Обновления качества Lab 3:

- critic возвращает JSON с русскими замечаниями и рекомендациями;
- финальный ответ пользователя может быть Markdown, JSON от него не требуется;
- при невалидном planner JSON показывается короткий warning и включается fallback;
- категориальный анализ разделяет признаки на:
  - классические категориальные,
  - ordinal/rating,
  - count-like числовые.

В ответе агента возвращаются:

- `analysis_mode`
- `llm_calls_count`
- `elapsed_seconds`
- `warnings`

### Как продемонстрировать Lab 3

1. Откройте `http://localhost:3003/lab3`.
2. Выберите датасет или загрузите свой CSV/XLSX.
3. Нажмите «Проанализировать структуру».
4. Проверьте и при необходимости исправьте роли колонок.
5. Выберите режим `Быстрый`.
6. Задайте вопрос: «Сделай краткий обзор датасета».
7. Follow-up: «Какие ограничения самые важные?».
8. Follow-up: «Что проверить дальше?».
9. Скачайте отчёт через вкладку «Файлы».

### Модели Ollama

```bash
ollama pull qwen3:8b
ollama pull qwen2.5-coder:7b
ollama pull deepseek-r1:8b
```

Если backend работает в Docker, доступ к Ollama на хосте:

- `http://host.docker.internal:11434`

## Полезные URL

- Lab 2: http://localhost:3003/lab2
- Lab 3: http://localhost:3003/lab3
- Lab 3 status: http://localhost:8003/api/lab3/status
- Lab 3 datasets: http://localhost:8003/api/lab3/datasets
- Lab 3 session: http://localhost:8003/api/lab3/session?session_id=<id>

## Доступ из интернета

Docker Compose публикует порты на все интерфейсы хоста.
После открытия портов на роутере/фаерволе сервис будет доступен по вашему публичному IP и выбранным портам:

- Frontend: `http://<PUBLIC_IP>:3003`
- Backend API: `http://<PUBLIC_IP>:8003/api/health`
- Swagger: `http://<PUBLIC_IP>:8003/docs`

Рекомендуется ограничить доступ к backend (IP allowlist / reverse proxy / basic auth), если сервис публикуется в интернет.

## Примеры curl

Lab 3 ask:

```bash
curl -X POST "http://localhost:8003/api/lab3/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name":"customers_reviews.csv",
    "question":"Сделай краткий обзор датасета",
    "column_overrides":{},
    "max_tool_calls":6,
    "use_critic":false,
    "analysis_mode":"code_interpreter"
  }'
```

Lab 3 upload:

```bash
curl -X POST "http://localhost:8003/api/lab3/upload-dataset" \
  -F "file=@./my_dataset.csv"
```

## Lab 3 Code Interpreter: контракт sandbox

- Backend заранее загружает датасет в `df`, поэтому модель должна работать с `df` и не читать файлы вручную.
- В sandbox запрещены `os/subprocess/socket/requests`, а также `open/eval/exec` и ручной `pd.read_csv/pd.read_excel`.
- Модель получает результат выполнения (`stdout/stderr`) и продолжает анализ по этим данным.
- Это ограничение защищает от prompt injection и произвольного выполнения кода.

### Tag protocol

- Основной протокол Code Interpreter теперь tag-based:
  - код: `<PYTHON> ... </PYTHON>`
  - финал: `<FINAL> ... </FINAL>`
- JSON action loop больше не основной путь (оставлен только для backward compatibility).
- Backend в trace сохраняет `raw_messages` и `parse_mode` для каждого шага.

## Lab 3 Code Interpreter Loop (Updated)

- Mode is LangGraph Code Interpreter with OpenRouter.
- LLM returns either `<PYTHON>...</PYTHON>` or `<FINAL>...</FINAL>`.
- Backend executes generated Python only in our own sandbox and returns `stdout/stderr/files` back to LLM for next step.
- Sandbox blocks file/system/network operations and manual CSV loading; dataframe is preloaded as `df`.
- UI separates:
  - Final markdown answer
  - System warnings
  - Code steps
  - Execution logs
  - Raw JSON trace

### Demo queries

1. `Сделай краткий обзор датасета: строки, колонки, пропуски и 3 главных наблюдения.`
2. `Выдели таргет переменную и посчитай корреляции Спирмана, Пирсона всех колонок с этой переменной, дай свои выводы исходя из полученных данных.`

## Workspace backend foundation
- Added backend foundation for workspace APIs: auth/demo account, chats, datasets registry, artifacts registry.
- Existing Lab2 and Lab3 endpoints are preserved and still available.
- SQLite storage location: outputs/app.db.

Demo account:
- email: demo@example.com`n- password: demo`n
