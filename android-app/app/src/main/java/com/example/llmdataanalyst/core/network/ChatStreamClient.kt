package com.example.llmdataanalyst.core.network

import com.example.llmdataanalyst.core.model.ChatMessageCreateRequest
import com.example.llmdataanalyst.core.model.ChatStreamEvent
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.flowOn
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import okhttp3.Call
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class StreamingUnavailableException(message: String) : RuntimeException(message)

class ChatStreamClient(
    private val authStateHolder: AuthStateHolder
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        explicitNulls = false
    }
    private val parser = SseParser(json)

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .writeTimeout(120, TimeUnit.SECONDS)
        .callTimeout(0, TimeUnit.MILLISECONDS)
        .addInterceptor(AuthInterceptor(authStateHolder))
        .build()

    fun sendMessageStream(
        baseUrl: String,
        chatId: String,
        request: ChatMessageCreateRequest
    ): Flow<ChatStreamEvent> = streamJsonBody(
        baseUrl = baseUrl,
        apiPath = "/api/chats/$chatId/messages/stream",
        bodyJson = json.encodeToString(ChatMessageCreateRequest.serializer(), request)
    )

    fun sendLab3AskStream(
        baseUrl: String,
        body: JsonElement
    ): Flow<ChatStreamEvent> = streamJsonBody(
        baseUrl = baseUrl,
        apiPath = "/api/lab3/ask/stream",
        bodyJson = json.encodeToString(JsonElement.serializer(), body)
    )

    private fun streamJsonBody(
        baseUrl: String,
        apiPath: String,
        bodyJson: String
    ): Flow<ChatStreamEvent> = callbackFlow {
        val url = "${baseUrl.trimEnd('/')}$apiPath"
        val body = bodyJson.toRequestBody("application/json".toMediaType())
        val httpRequest = Request.Builder()
            .url(url)
            .post(body)
            .header("Accept", "text/event-stream")
            .header("Content-Type", "application/json")
            .build()
        val call: Call = client.newCall(httpRequest)

        try {
            val response = call.execute()
            response.use { resp ->
                if (!resp.isSuccessful) {
                    close(StreamingUnavailableException("HTTP ${resp.code}"))
                    return@callbackFlow
                }
                val ct = resp.header("Content-Type").orEmpty().lowercase()
                if (!ct.contains("text/event-stream")) {
                    close(StreamingUnavailableException("Unexpected content-type: $ct"))
                    return@callbackFlow
                }
                val source = resp.body?.source() ?: run {
                    close(StreamingUnavailableException("Empty stream body"))
                    return@callbackFlow
                }
                while (!source.exhausted()) {
                    val line = source.readUtf8Line() ?: break
                    parser.consumeLine(line)?.let { trySend(it) }
                }
                parser.flush()?.let { trySend(it) }
                close()
            }
        } catch (e: Exception) {
            close(e)
        }

        awaitClose { call.cancel() }
    }.flowOn(Dispatchers.IO)
}
