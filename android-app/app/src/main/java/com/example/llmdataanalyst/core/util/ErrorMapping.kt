package com.example.llmdataanalyst.core.util

import retrofit2.HttpException
import java.io.IOException

fun Throwable.toUserMessage(): String {
    return when (this) {
        is HttpException -> {
            when {
                code() in 300..399 -> "Адрес ведёт не на backend API. Проверьте URL в настройках."
                code() == 401 -> "Сессия истекла. Выполните вход снова."
                else -> "HTTP ${code()}: ${message()}"
            }
        }
        is IOException -> {
            val raw = message.orEmpty().lowercase()
            if (raw.contains("refused") || raw.contains("failed to connect") || raw.contains("unexpectedly closed") || raw.contains("timeout")) {
                "Не удалось подключиться к backend. Проверьте сервер и сеть."
            } else {
                "Ошибка сети. Проверьте сервер и сеть."
            }
        }
        is IllegalStateException -> message ?: "Ошибка данных backend"
        else -> message ?: "Неизвестная ошибка"
    }
}
