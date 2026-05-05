package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.ArtifactsResponse
import com.example.llmdataanalyst.core.model.ChatsResponse
import com.example.llmdataanalyst.core.model.DatasetsResponse
import com.example.llmdataanalyst.core.model.WorkspaceResponse
import com.example.llmdataanalyst.core.util.AppResult
import com.example.llmdataanalyst.core.util.safeApiCall

class WorkspaceRepository(
    private val apiProvider: ApiProvider
) {
    suspend fun workspace(): AppResult<WorkspaceResponse> = safeApiCall { apiProvider.api().workspace() }
    suspend fun chats(): AppResult<ChatsResponse> = safeApiCall { apiProvider.api().chats() }
    suspend fun datasets(): AppResult<DatasetsResponse> = safeApiCall { apiProvider.api().datasets() }
    suspend fun artifacts(): AppResult<ArtifactsResponse> = safeApiCall { apiProvider.api().artifacts() }
}
