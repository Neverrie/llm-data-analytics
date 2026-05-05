package com.example.llmdataanalyst.core.network

import okhttp3.Interceptor
import okhttp3.Response

class UnauthorizedInterceptor(
    private val unauthorizedEventBus: UnauthorizedEventBus
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val response = chain.proceed(chain.request())
        if (response.code == 401) {
            unauthorizedEventBus.emitUnauthorized()
        }
        return response
    }
}
