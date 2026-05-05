package com.example.llmdataanalyst.core.util

import retrofit2.HttpException
import java.io.IOException

suspend fun <T> safeApiCall(block: suspend () -> T): AppResult<T> {
    return try {
        AppResult.Success(block())
    } catch (e: HttpException) {
        AppResult.Error("HTTP ${e.code()}: ${e.message()}", e)
    } catch (e: IOException) {
        AppResult.Error("Ошибка сети: ${e.message}", e)
    } catch (e: Exception) {
        AppResult.Error(e.message ?: "Неизвестная ошибка", e)
    }
}
