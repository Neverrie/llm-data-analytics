# Android App (MVP)

Нативный клиент на Kotlin + Jetpack Compose для backend `llm-data-analytics-final`.

## Что реализовано

- Этап 1: каркас проекта, Compose, Navigation, DataStore, Retrofit/OkHttp, Settings с `GET /api/health`.
- Этап 2: login + demo login, токен в DataStore, `Authorization: Bearer`, `GET /api/auth/me`, auto-logout при `401`.
- Этап 3: Dashboard с данными `workspace/chats/datasets/artifacts`.

## Запуск

1. Откройте папку `android-app` в Android Studio.
2. Дождитесь Gradle Sync.
3. Запустите `app` на эмуляторе/девайсе.

По умолчанию `baseUrl` = `http://10.0.2.2:8003/` (эмулятор Android -> localhost хоста).
