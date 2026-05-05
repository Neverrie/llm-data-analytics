package com.example.llmdataanalyst.core.repository

import com.example.llmdataanalyst.core.model.ChatDetailResponse
import com.example.llmdataanalyst.core.model.ChatItem
import com.example.llmdataanalyst.core.model.ChatMessageCreateRequest
import com.example.llmdataanalyst.core.model.ChatMessageItem
import com.example.llmdataanalyst.core.model.ChatSendResult
import com.example.llmdataanalyst.core.model.ChatStreamEvent
import com.example.llmdataanalyst.core.model.CreateChatRequest
import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.network.ChatStreamClient
import com.example.llmdataanalyst.core.network.StreamingUnavailableException
import com.example.llmdataanalyst.feature.chat.ArtifactTableParser
import com.example.llmdataanalyst.feature.chat.ChatContentBlock
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOf

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

    fun sendMessageStream(chatId: String, request: ChatMessageCreateRequest): Flow<ChatStreamEvent> = flow {
        val baseUrl = settingsRepository.baseUrlFlow.first()
        streamClient.sendMessageStream(baseUrl, chatId, request).collect { emit(it) }
    }

    fun sendMessage(
        chatId: String,
        request: ChatMessageCreateRequest,
        streamingEnabled: Boolean
    ): Flow<ChatSendResult> {
        if (!streamingEnabled) return flowOf(ChatSendResult.FallbackUsed)
        return flow {
            try {
                sendMessageStream(chatId, request).collect { event ->
                    when (event) {
                        is ChatStreamEvent.MessageStart -> emit(ChatSendResult.AssistantMessageStarted)
                        is ChatStreamEvent.MessageDelta -> emit(ChatSendResult.AssistantDelta(event.content))
                        is ChatStreamEvent.ToolStart -> emit(ChatSendResult.ToolProgress("▶ ${event.title ?: event.name ?: "Запуск"}"))
                        is ChatStreamEvent.ToolLog -> emit(ChatSendResult.ToolProgress(event.content))
                        is ChatStreamEvent.ToolEnd -> emit(ChatSendResult.ToolProgress("✓ ${event.name ?: "Инструмент"}: ${event.status ?: "ok"}"))
                        is ChatStreamEvent.ArtifactCreated -> emit(
                            ChatSendResult.ArtifactCreated(event.artifactId, event.title, event.mimeType)
                        )
                        is ChatStreamEvent.Error -> emit(ChatSendResult.Failed(event.message))
                        is ChatStreamEvent.Done -> emit(ChatSendResult.Completed(event.messageId))
                        is ChatStreamEvent.Unknown -> Unit
                    }
                }
            } catch (e: Exception) {
                if (e is StreamingUnavailableException) {
                    emit(ChatSendResult.FallbackUsed)
                } else {
                    emit(ChatSendResult.Failed(e.message ?: "Ошибка стриминга"))
                }
            }
        }
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
