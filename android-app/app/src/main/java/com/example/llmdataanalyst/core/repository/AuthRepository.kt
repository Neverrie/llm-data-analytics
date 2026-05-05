package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.datastore.AppPreferences
import com.example.llmdataanalyst.core.model.AuthLoginRequest
import com.example.llmdataanalyst.core.model.AuthResponse
import com.example.llmdataanalyst.core.model.UserPublic
import com.example.llmdataanalyst.core.network.AuthStateHolder
import com.example.llmdataanalyst.core.util.AppResult
import com.example.llmdataanalyst.core.util.safeApiCall
import kotlinx.coroutines.flow.Flow

class AuthRepository(
    private val apiProvider: ApiProvider,
    private val appPreferences: AppPreferences,
    private val authStateHolder: AuthStateHolder
) {
    val tokenFlow: Flow<String?> = appPreferences.tokenFlow
    val baseUrlFlow: Flow<String> = appPreferences.baseUrlFlow

    suspend fun login(email: String, password: String): AppResult<AuthResponse> = safeApiCall {
        val response = apiProvider.api().login(AuthLoginRequest(email = email, password = password))
        setToken(response.accessToken)
        response
    }

    suspend fun demoLogin(): AppResult<AuthResponse> = safeApiCall {
        val response = apiProvider.api().demoLogin()
        setToken(response.accessToken)
        response
    }

    suspend fun me(): AppResult<UserPublic> = safeApiCall { apiProvider.api().me() }

    suspend fun logout() {
        setToken(null)
    }

    suspend fun setBaseUrl(url: String) {
        appPreferences.setBaseUrl(url)
    }

    private suspend fun setToken(token: String?) {
        authStateHolder.updateToken(token)
        appPreferences.setToken(token)
    }
}
