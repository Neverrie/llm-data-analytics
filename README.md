# llm-data-analytics-final

Учебный каркас проекта **LLM Data Analyst Lab**.

## Что внутри

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + Python
- Заглушки API для Lab 1/2/3
- Подготовленный клиент для будущей интеграции с Ollama
- Docker Compose для запуска всего проекта одной командой

## Основной запуск (рекомендуется)

```bash
docker compose up --build
```

После запуска:

- Frontend: http://localhost:3003
- Backend API health: http://localhost:8003/api/health
- Swagger docs: http://localhost:8003/docs

## Структура

```text
llm-data-analytics-final/
+-- frontend/
+-- backend/
+-- datasets/
+-- outputs/
+-- docker-compose.yml
L-- README.md
```

## Дополнительно: локальный запуск без Docker

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Backend

```bash
cd backend
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## План развития

1. Lab 1: Prompt Engineering EDA
2. Lab 2: API Pipeline: CSV -> LLM -> JSON
3. Lab 3: Mini-product with LLM analytics agent

