package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.util.AppResult
import com.example.llmdataanalyst.core.util.safeApiCall
import kotlinx.coroutines.flow.first

class ArtifactRepository(
    private val apiProvider: ApiProvider,
    private val settingsRepository: SettingsRepository
) {
    suspend fun listArtifacts() = safeApiCall { apiProvider.api().artifacts().items }

    suspend fun getArtifact(artifactId: String) = safeApiCall { apiProvider.api().getArtifact(artifactId) }

    suspend fun getPreview(artifactId: String) = safeApiCall { apiProvider.api().getArtifactPreview(artifactId) }

    suspend fun download(artifactId: String) = safeApiCall { apiProvider.api().downloadArtifact(artifactId) }

    suspend fun buildPreviewUrl(artifactId: String): String {
        val baseUrl = settingsRepository.baseUrlFlow.first().trimEnd('/')
        return "$baseUrl/api/artifacts/$artifactId/preview"
    }

    suspend fun buildDownloadUrl(artifactId: String): String {
        val baseUrl = settingsRepository.baseUrlFlow.first().trimEnd('/')
        return "$baseUrl/api/artifacts/$artifactId/download"
    }
}
