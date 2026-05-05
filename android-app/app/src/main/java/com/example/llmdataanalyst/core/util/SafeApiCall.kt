package com.example.llmdataanalyst.core.util

suspend fun <T> safeApiCall(block: suspend () -> T): AppResult<T> {
    return try {
        AppResult.Success(block())
    } catch (e: Exception) {
        AppResult.Error(e.toUserMessage(), e)
    }
}
