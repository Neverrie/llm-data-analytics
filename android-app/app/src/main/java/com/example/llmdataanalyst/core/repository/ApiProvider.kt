package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.datastore.AppPreferences
import com.example.llmdataanalyst.core.network.ApiClientFactory
import com.example.llmdataanalyst.core.network.ApiService
import kotlinx.coroutines.flow.first

class ApiProvider(
    private val appPreferences: AppPreferences,
    private val apiClientFactory: ApiClientFactory
) {
    suspend fun api(): ApiService {
        val baseUrl = appPreferences.baseUrlFlow.first()
        return apiClientFactory.create(baseUrl)
    }
}
