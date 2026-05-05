package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.HealthResponse
import com.example.llmdataanalyst.core.util.AppResult
import com.example.llmdataanalyst.core.util.safeApiCall
import kotlinx.coroutines.flow.Flow
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json

class SettingsRepository(
    private val apiProvider: ApiProvider,
    val baseUrlFlow: Flow<String>,
    val tokenFlow: Flow<String?>,
    val streamingEnabledFlow: Flow<Boolean>,
    private val onSetStreamingEnabled: suspend (Boolean) -> Unit
) {
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun checkHealth(): AppResult<HealthResponse> {
        return safeApiCall {
            val response = apiProvider.api().healthRaw()
            val isRedirect = response.code() in 300..399 || !response.headers()["Location"].isNullOrBlank()
            if (isRedirect) {
                throw IllegalStateException("Адрес ведёт не на backend API. Проверьте порт или URL.")
            }
            val contentType = response.headers()["Content-Type"].orEmpty().lowercase()
            if (!contentType.contains("application/json")) {
                throw IllegalStateException("Сервер ответил не API-ответом. Проверьте адрес backend.")
            }
            if (!response.isSuccessful) {
                throw IllegalStateException("HTTP ${response.code()}: ${response.message()}")
            }
            val bodyText = response.body()?.string()
                ?: throw IllegalStateException("Пустой ответ от сервера")
            json.decodeFromString<HealthResponse>(bodyText)
        }
    }

    suspend fun setStreamingEnabled(enabled: Boolean) = onSetStreamingEnabled(enabled)
}
