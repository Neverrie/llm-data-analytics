# llm-data-analytics-final

Учебный проект **LLM Data Analyst Lab**.

## Стек

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + Python
- LLM provider: Ollama (локально на хосте)

## Быстрый запуск

```bash
docker compose up --build
```

После запуска:

- Frontend: http://localhost:3003
- Backend API health: http://localhost:8003/api/health
- Swagger docs: http://localhost:8003/docs

## Задание 2 — API Pipeline

Lab 2 реализует рабочий pipeline:

1. Backend читает Uber Customer Reviews Dataset (2024) из папки `datasets`.
2. Для текста используется колонка `content`.
3. `score` используется как дополнительный сигнал и нормализуется backend-ом.
4. Данные отправляются в Ollama batch-ами.
5. Ответ валидируется через Pydantic.
6. Результат сохраняется в `outputs/lab2_result.json`.

Текущий датасет в репозитории: `datasets/customers_reviews.csv`.

### Параметры запуска Lab 2

- `limit`: сколько отзывов обработать
- `batch_size`: сколько отзывов отправлять в модель за один запрос
- `min_score` / `max_score`: фильтр по оценке

Backend ограничивает `limit` максимумом (сейчас `MAX_LIMIT=100`) и возвращает предупреждение в `warnings`.

### Проверка Ollama

1. Убедиться, что Ollama запущена:

```bash
ollama list
```

2. Убедиться, что модель установлена:

```bash
ollama pull qwen3:8b
```

3. Если backend работает в Docker, он обращается к Ollama на хосте через:

`http://host.docker.internal:11434`

### URL для проверки

- Frontend Lab 2: http://localhost:3003/lab2
- Backend docs: http://localhost:8003/docs
- Lab2 status: http://localhost:8003/api/lab2/status

### curl примеры

```bash
curl -X POST "http://localhost:8003/api/lab2/run" ^
  -H "Content-Type: application/json" ^
  -d "{\"limit\":5,\"batch_size\":5,\"min_score\":null,\"max_score\":null}"
```

```bash
curl -X POST "http://localhost:8003/api/lab2/run" ^
  -H "Content-Type: application/json" ^
  -d "{\"limit\":12,\"batch_size\":5,\"min_score\":null,\"max_score\":null}"
```
