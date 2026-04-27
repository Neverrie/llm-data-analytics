# llm-data-analytics-final

Учебный проект **LLM Data Analyst Lab** с веб-интерфейсом (Next.js) и backend API (FastAPI).

## Стек

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + Python
- LLM provider: Ollama (локально на хост-машине)
- UI: нейроморфизм + переключаемые светлая/тёмная темы

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

### Роли колонок простым языком

Агент определяет роли колонок (текст, рейтинг, дата, целевая переменная и т.д.) и затем использует общий набор tools для любых CSV/XLSX.
Если автоопределение ошиблось, роль можно исправить вручную в блоке «Роли колонок».
Это делает анализ универсальным и не привязанным к конкретным названиям колонок.

### Режимы анализа

- `fast`: heuristic mapping + rule-based planner + один LLM-вызов для финального ответа.
- `balanced`: heuristic mapping + LLM planner + финальный ответ (+ critic опционально).
- `full`: heuristic + LLM-assisted mapping + LLM planner + финальный ответ (+ critic опционально).

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

Docker Compose уже публикует порты на все интерфейсы хоста.
Если вы откроете порты на роутере/фаерволе, проект будет доступен по вашему публичному IP:

- Frontend: `http://82.162.61.44:3003`
- Backend API: `http://82.162.61.44:8003/api/health`
- Swagger: `http://82.162.61.44:8003/docs`

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
    "analysis_mode":"fast"
  }'
```

Lab 3 upload:

```bash
curl -X POST "http://localhost:8003/api/lab3/upload-dataset" \
  -F "file=@./my_dataset.csv"
```
