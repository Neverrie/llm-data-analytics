package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.HealthResponse
import com.example.llmdataanalyst.core.util.AppResult
import com.example.llmdataanalyst.core.util.safeApiCall
import kotlinx.coroutines.flow.Flow

class SettingsRepository(
    private val apiProvider: ApiProvider,
    val baseUrlFlow: Flow<String>,
    val streamingEnabledFlow: Flow<Boolean>,
    private val onSetStreamingEnabled: suspend (Boolean) -> Unit
) {
    suspend fun checkHealth(): AppResult<HealthResponse> = safeApiCall { apiProvider.api().health() }
    suspend fun setStreamingEnabled(enabled: Boolean) = onSetStreamingEnabled(enabled)
}
