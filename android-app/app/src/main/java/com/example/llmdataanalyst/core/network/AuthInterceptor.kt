package com.example.llmdataanalyst.core.network

import okhttp3.Interceptor
import okhttp3.Response

class AuthInterceptor(
    private val authStateHolder: AuthStateHolder
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = authStateHolder.tokenState.value
        val requestBuilder = chain.request().newBuilder()
        if (!token.isNullOrBlank()) {
            requestBuilder.addHeader("Authorization", "Bearer $token")
        }
        return chain.proceed(requestBuilder.build())
    }
}
