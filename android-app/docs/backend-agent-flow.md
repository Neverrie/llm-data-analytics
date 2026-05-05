# Backend Agent Flow (Web -> Backend)

## Что реально вызывает веб

Основной путь анализа данных в вебе:
- `POST /api/lab3/ask/stream`
- fallback: `POST /api/lab3/ask`
- после стрима веб дополнительно читает `GET /api/lab3/result`
- для артефактов использует:
  - `GET /api/artifacts`
  - `POST /api/artifacts/register` (регистрация файлов из `/outputs/lab3/...`)
  - preview/download через `/api/artifacts/{id}/preview|download`

Путь обычного чата:
- `POST /api/chats/{chat_id}/messages`
- используется для сохранения сообщений (в вебе user/assistant также сохраняются в чат)

## Payload для lab3 ask

Веб отправляет в `/api/lab3/ask/stream`:
- `dataset_name: string`
- `question: string`
- `analysis_mode: "code_interpreter"`
- `include_history: true`
- `max_tool_calls: 6`

## Как передаётся датасет

- Через `dataset_name` в `lab3/ask` payload.
- В chat context (`/chats`) веб также хранит `dataset_name` у чата.

## Как приходят результаты

SSE события:
- `message_start`
- `message_delta`
- `tool_start`
- `tool_log`
- `tool_end`
- `artifact_created`
- `error`
- `done`

Итоговый расширенный результат читается из `GET /api/lab3/result`.

## Что должен использовать Android

Для режима анализа данных (есть выбранный dataset):
- основной endpoint: `POST /api/lab3/ask/stream`
- fallback: `POST /api/lab3/ask`
- после завершения: `GET /api/lab3/result` + синхронизация артефактов через `GET /api/artifacts`

Для обычного чата (без dataset):
- `POST /api/chats/{chat_id}/messages/stream`
- fallback: `POST /api/chats/{chat_id}/messages`
