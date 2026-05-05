package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.Lab2RunRequest
import com.example.llmdataanalyst.core.util.safeApiCall
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement

class Lab2Repository(
    private val apiProvider: ApiProvider
) {
    private val json = Json { prettyPrint = true; isLenient = true; ignoreUnknownKeys = true }

    suspend fun status() = safeApiCall { apiProvider.api().lab2Status() }
    suspend fun sampleData() = safeApiCall { apiProvider.api().lab2SampleData() }
    suspend fun run() = safeApiCall { apiProvider.api().lab2Run(Lab2RunRequest()) }
    suspend fun result() = safeApiCall { apiProvider.api().lab2Result() }
    suspend fun download() = safeApiCall { apiProvider.api().lab2Download() }

    fun pretty(element: JsonElement?): String {
        return if (element == null) "—" else json.encodeToString(JsonElement.serializer(), element)
    }
}
