package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.model.ChatDetailResponse
import com.example.llmdataanalyst.core.model.ChatItem
import com.example.llmdataanalyst.core.model.ChatMessageCreateRequest
import com.example.llmdataanalyst.core.model.ChatMessageItem
import com.example.llmdataanalyst.core.model.ChatSendResult
import com.example.llmdataanalyst.core.model.ChatStreamEvent
import com.example.llmdataanalyst.core.model.CreateChatRequest
import com.example.llmdataanalyst.core.model.Lab3AskRequest
import com.example.llmdataanalyst.core.network.ChatStreamClient
import com.example.llmdataanalyst.core.network.StreamingUnavailableException
import com.example.llmdataanalyst.feature.chat.ArtifactTableParser
import com.example.llmdataanalyst.feature.chat.ChatContentBlock
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

enum class ChatExecutionMode {
    GeneralChat,
    DatasetAgent
}

class ChatRepository(
    private val apiProvider: ApiProvider,
    private val settingsRepository: SettingsRepository,
    private val streamClient: ChatStreamClient
) {
    suspend fun createChat(datasetName: String? = null): ChatItem =
        apiProvider.api().createChat(CreateChatRequest("Новый анализ", "lab3_chat", datasetName))

    suspend fun getChat(chatId: String): ChatDetailResponse = apiProvider.api().getChat(chatId)

    suspend fun sendMessageJson(chatId: String, request: ChatMessageCreateRequest): ChatMessageItem =
        apiProvider.api().sendChatMessage(chatId, request)

    suspend fun sendLab3Json(datasetName: String, question: String): JsonElement {
        return apiProvider.api().lab3Ask(
            Lab3AskRequest(
                datasetName = datasetName,
                question = question,
                analysisMode = "code_interpreter",
                includeHistory = true,
                maxToolCalls = 6
            )
        )
    }

    suspend fun getLab3Result(): JsonElement = apiProvider.api().lab3Result()

    suspend fun listArtifacts(): List<ArtifactItem> = apiProvider.api().artifacts().items

    fun sendMessageStream(chatId: String, request: ChatMessageCreateRequest): Flow<ChatStreamEvent> = flow {
        val baseUrl = settingsRepository.baseUrlFlow.first()
        streamClient.sendMessageStream(baseUrl, chatId, request).collect { emit(it) }
    }

    fun sendLab3Stream(datasetName: String, question: String): Flow<ChatStreamEvent> = flow {
        val baseUrl = settingsRepository.baseUrlFlow.first()
        val body = buildJsonObject {
            put("dataset_name", datasetName)
            put("question", question)
            put("analysis_mode", "code_interpreter")
            put("include_history", true)
            put("max_tool_calls", 6)
        }
        streamClient.sendLab3AskStream(baseUrl, body).collect { emit(it) }
    }

    fun sendMessage(
        mode: ChatExecutionMode,
        chatId: String?,
        request: ChatMessageCreateRequest,
        streamingEnabled: Boolean,
        datasetName: String?
    ): Flow<ChatSendResult> {
        if (mode == ChatExecutionMode.GeneralChat) {
            if (chatId.isNullOrBlank()) return flowOf(ChatSendResult.Failed("Чат не создан"))
            if (!streamingEnabled) return flowOf(ChatSendResult.FallbackUsed)
            return streamGeneral(chatId, request)
        }

        if (datasetName.isNullOrBlank()) {
            return flowOf(ChatSendResult.Failed("Для режима анализа выберите датасет"))
        }
        if (!streamingEnabled) return flowOf(ChatSendResult.FallbackUsed)
        return streamDatasetAgent(datasetName, request.content)
    }

    private fun streamGeneral(chatId: String, request: ChatMessageCreateRequest): Flow<ChatSendResult> = flow {
        try {
            sendMessageStream(chatId, request).collect { emit(mapEvent(it)) }
        } catch (e: Exception) {
            if (e is StreamingUnavailableException) emit(ChatSendResult.FallbackUsed)
            else emit(ChatSendResult.Failed(e.message ?: "Ошибка стриминга"))
        }
    }

    private fun streamDatasetAgent(datasetName: String, question: String): Flow<ChatSendResult> = flow {
        try {
            sendLab3Stream(datasetName, question).collect { emit(mapEvent(it)) }
        } catch (e: Exception) {
            if (e is StreamingUnavailableException) emit(ChatSendResult.FallbackUsed)
            else emit(ChatSendResult.Failed(e.message ?: "Ошибка стриминга"))
        }
    }

    private fun mapEvent(event: ChatStreamEvent): ChatSendResult {
        return when (event) {
            is ChatStreamEvent.MessageStart -> ChatSendResult.AssistantMessageStarted
            is ChatStreamEvent.MessageDelta -> ChatSendResult.AssistantDelta(event.content)
            is ChatStreamEvent.ToolStart -> ChatSendResult.ToolProgress("▶ ${event.title ?: event.name ?: "Запуск"}")
            is ChatStreamEvent.ToolLog -> ChatSendResult.ToolProgress(event.content)
            is ChatStreamEvent.ToolEnd -> ChatSendResult.ToolProgress("✓ ${event.name ?: "Инструмент"}: ${event.status ?: "ok"}")
            is ChatStreamEvent.ArtifactCreated -> ChatSendResult.ArtifactCreated(event.artifactId, event.title, event.mimeType)
            is ChatStreamEvent.Error -> ChatSendResult.Failed(event.message)
            is ChatStreamEvent.Done -> ChatSendResult.Completed(event.messageId)
            is ChatStreamEvent.Unknown -> ChatSendResult.ToolProgress(event.rawData.take(180))
        }
    }

    fun stripDatasetTechnicalPrefix(text: String): String {
        val marker = "Запрос пользователя:"
        val idx = text.indexOf(marker)
        if (text.startsWith("Используй выбранный датасет:") && idx >= 0) {
            return text.substring(idx + marker.length).trim()
        }
        return text
    }

    suspend fun buildPreviewUrl(artifactId: String): String {
        val baseUrl = settingsRepository.baseUrlFlow.first().trimEnd('/')
        return "$baseUrl/api/artifacts/$artifactId/preview"
    }

    suspend fun getArtifact(artifactId: String): ArtifactItem = apiProvider.api().getArtifact(artifactId)

    suspend fun getArtifactPreviewRaw(artifactId: String): Pair<String, String> {
        val response = apiProvider.api().getArtifactPreview(artifactId)
        val contentType = response.headers()["Content-Type"].orEmpty()
        val body = response.body()?.string().orEmpty()
        return contentType to body
    }

    suspend fun buildVisualBlockFromArtifact(
        artifactId: String,
        fallbackTitle: String?,
        fallbackMimeType: String?
    ): ChatContentBlock {
        return runCatching {
            val metadata = apiProvider.api().getArtifact(artifactId)
            val title = metadata.title ?: metadata.filename ?: fallbackTitle
            val mime = metadata.mimeType ?: fallbackMimeType
            val previewUrl = buildPreviewUrl(artifactId)
            if (isImageArtifact(title, mime)) {
                return@runCatching ChatContentBlock.ImageArtifactBlock(
                    artifactId = artifactId,
                    title = title,
                    mimeType = mime,
                    previewUrl = previewUrl
                )
            }
            val previewResponse = apiProvider.api().getArtifactPreview(artifactId)
            if (!previewResponse.isSuccessful) {
                return@runCatching ChatContentBlock.UnsupportedArtifactBlock(artifactId, title, mime)
            }
            val contentType = previewResponse.headers()["Content-Type"].orEmpty().lowercase()
            val raw = previewResponse.body()?.string().orEmpty()
            if (raw.isBlank()) return@runCatching ChatContentBlock.UnsupportedArtifactBlock(artifactId, title, mime)
            if (contentType.contains("application/json") || looksLikeJson(raw)) {
                val parsed = ArtifactTableParser.parse(raw, title, artifactId)
                parsed.table ?: parsed.jsonFallback ?: ChatContentBlock.UnsupportedArtifactBlock(artifactId, title, mime)
            } else {
                ChatContentBlock.UnsupportedArtifactBlock(artifactId, title, mime)
            }
        }.getOrElse {
            ChatContentBlock.UnsupportedArtifactBlock(artifactId, fallbackTitle, fallbackMimeType)
        }
    }

    private fun isImageArtifact(title: String?, mime: String?): Boolean {
        val lowerTitle = title.orEmpty().lowercase()
        val lowerMime = mime.orEmpty().lowercase()
        return lowerMime.contains("image/png") ||
            lowerMime.contains("image/jpeg") ||
            lowerMime.contains("image/jpg") ||
            lowerMime.contains("image/webp") ||
            lowerTitle.endsWith(".png") ||
            lowerTitle.endsWith(".jpg") ||
            lowerTitle.endsWith(".jpeg") ||
            lowerTitle.endsWith(".webp")
    }

    private fun looksLikeJson(raw: String): Boolean {
        val t = raw.trim()
        return t.startsWith("{") || t.startsWith("[")
    }
}
