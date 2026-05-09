package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.DatasetItem
import com.example.llmdataanalyst.core.model.DatasetPreviewResponse
import com.example.llmdataanalyst.core.model.DatasetProfileResponse
import com.example.llmdataanalyst.core.util.AppResult
import com.example.llmdataanalyst.core.util.safeApiCall
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File

class DatasetRepository(
    private val apiProvider: ApiProvider
) {
    suspend fun listDatasets(): AppResult<List<DatasetItem>> = safeApiCall {
        apiProvider.api().datasets().items
    }

    suspend fun uploadDataset(file: File): AppResult<DatasetItem> = safeApiCall {
        val req = file.asRequestBody("application/octet-stream".toMediaTypeOrNull())
        val part = MultipartBody.Part.createFormData("file", file.name, req)
        apiProvider.api().uploadDataset(part)
    }

    suspend fun previewDataset(datasetId: String, limit: Int = 30): AppResult<DatasetPreviewResponse> = safeApiCall {
        apiProvider.api().datasetPreview(datasetId, limit)
    }

    suspend fun profileDataset(datasetId: String): AppResult<DatasetProfileResponse> = safeApiCall {
        apiProvider.api().datasetProfile(datasetId)
    }

    suspend fun deleteDataset(datasetId: String): AppResult<Unit> = safeApiCall {
        apiProvider.api().deleteDataset(datasetId)
        Unit
    }
}
