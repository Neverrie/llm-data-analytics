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
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
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

    fun sendLab3Stream(datasetName: String, question: String, chatId: String, clientMessageId: String? = null): Flow<ChatStreamEvent> = flow {
        val baseUrl = settingsRepository.baseUrlFlow.first()
        val body = buildJsonObject {
            put("dataset_name", datasetName)
            put("question", question)
            put("analysis_mode", "code_interpreter")
            put("session_id", chatId)
            put("include_history", true)
            put("max_tool_calls", 6)
            if (!clientMessageId.isNullOrBlank()) {
                put("client_message_id", clientMessageId)
            }
        }
        streamClient.sendLab3AskStream(baseUrl, chatId, body).collect { emit(it) }
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
        if (chatId.isNullOrBlank()) return flowOf(ChatSendResult.Failed("Чат не создан"))
        return streamDatasetAgent(datasetName, request.content, chatId, request.clientMessageId)
    }

    private fun streamGeneral(chatId: String, request: ChatMessageCreateRequest): Flow<ChatSendResult> = flow {
        try {
            sendMessageStream(chatId, request).collect { emit(mapEvent(it)) }
        } catch (e: Exception) {
            if (e is StreamingUnavailableException) emit(ChatSendResult.FallbackUsed)
            else emit(ChatSendResult.Failed(e.message ?: "Ошибка стриминга"))
        }
    }

    private fun streamDatasetAgent(datasetName: String, question: String, chatId: String, clientMessageId: String?): Flow<ChatSendResult> = flow {
        try {
            sendLab3Stream(datasetName, question, chatId, clientMessageId).collect { emit(mapEvent(it)) }
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
            is ChatStreamEvent.ArtifactCreated -> ChatSendResult.ArtifactCreated(event.artifactId, event.title, event.mimeType, event.previewUrl)
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

    suspend fun parseServerBlocks(message: ChatMessageItem): List<ChatContentBlock> {
        if (message.role != "assistant") {
            return listOf(ChatContentBlock.TextBlock(stripDatasetTechnicalPrefix(message.content)))
        }
        if (message.blocks.isEmpty()) {
            return listOf(ChatContentBlock.MarkdownBlock(message.content))
        }

        val resolved = mutableListOf<ChatContentBlock>()
        message.blocks.forEach { block ->
            val obj = block as? JsonObject ?: return@forEach
            when (obj["type"]?.jsonPrimitive?.contentOrNull?.lowercase()) {
                "markdown", "text" -> {
                    val text = obj["content"]?.jsonPrimitive?.contentOrNull ?: message.content
                    if (text.isNotBlank()) resolved += ChatContentBlock.MarkdownBlock(text)
                }
                "warning" -> {
                    val text = obj["content"]?.jsonPrimitive?.contentOrNull.orEmpty()
                    val details = obj["details"]?.jsonPrimitive?.contentOrNull
                    val errorType = obj["error_type"]?.jsonPrimitive?.contentOrNull
                    if (text.isNotBlank()) {
                        resolved += ChatContentBlock.WarningBlock(text = text, details = details, errorType = errorType)
                    }
                }
                "table" -> {
                    val columns = obj["columns"]?.let { toStringList(it) }.orEmpty()
                    val rows = obj["rows"]?.let { toRows(it, columns) }.orEmpty()
                    val artifactId = obj["artifact_id"]?.jsonPrimitive?.contentOrNull
                    if (columns.isNotEmpty() && rows.isNotEmpty()) {
                        resolved += ChatContentBlock.TableBlock(
                            title = obj["title"]?.jsonPrimitive?.contentOrNull,
                            columns = columns,
                            rows = rows,
                            sourceArtifactId = artifactId
                        )
                    }
                }
                "chart" -> {
                    val url = obj["preview_url"]?.jsonPrimitive?.contentOrNull ?: obj["url"]?.jsonPrimitive?.contentOrNull
                    val title = obj["title"]?.jsonPrimitive?.contentOrNull
                    val artifactId = obj["artifact_id"]?.jsonPrimitive?.contentOrNull ?: extractArtifactIdFromUrl(url).orEmpty()
                    if (!url.isNullOrBlank()) {
                        resolved += ChatContentBlock.ImageArtifactBlock(
                            artifactId = artifactId,
                            title = title,
                            mimeType = "image/png",
                            previewUrl = absolutizeUrl(url)
                        )
                    }
                }
                "file" -> {
                    val path = obj["path"]?.jsonPrimitive?.contentOrNull
                    val downloadUrl = obj["download_url"]?.jsonPrimitive?.contentOrNull
                    val title = obj["title"]?.jsonPrimitive?.contentOrNull ?: obj["filename"]?.jsonPrimitive?.contentOrNull
                    val artifactId = obj["artifact_id"]?.jsonPrimitive?.contentOrNull ?: extractArtifactIdFromUrl(downloadUrl ?: path)
                    if (!artifactId.isNullOrBlank()) {
                        resolved += buildVisualBlockFromArtifact(artifactId, title, null)
                    } else if (!downloadUrl.isNullOrBlank()) {
                        resolved += ChatContentBlock.UnsupportedArtifactBlock(
                            artifactId = downloadUrl,
                            title = title,
                            mimeType = null
                        )
                    }
                }
                "raw" -> {
                    val payload = obj["payload"]
                    if (payload != null) {
                        resolved += ChatContentBlock.JsonBlock(payload.toString())
                    }
                }
            }
        }

        if (resolved.isEmpty()) {
            resolved += ChatContentBlock.MarkdownBlock(message.content)
        }
        return resolved
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
            if (isImageArtifact(title, mime, metadata.filename, metadata.path)) {
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

    private fun isImageArtifact(title: String?, mime: String?, filename: String?, path: String?): Boolean {
        val lowerTitle = title.orEmpty().lowercase()
        val lowerMime = mime.orEmpty().lowercase()
        val lowerFilename = filename.orEmpty().lowercase()
        val lowerPath = path.orEmpty().lowercase()
        return lowerMime.contains("image/png") ||
            lowerMime.contains("image/jpeg") ||
            lowerMime.contains("image/jpg") ||
            lowerMime.contains("image/webp") ||
            lowerTitle.endsWith(".png") ||
            lowerTitle.endsWith(".jpg") ||
            lowerTitle.endsWith(".jpeg") ||
            lowerTitle.endsWith(".webp") ||
            lowerFilename.endsWith(".png") ||
            lowerFilename.endsWith(".jpg") ||
            lowerFilename.endsWith(".jpeg") ||
            lowerFilename.endsWith(".webp") ||
            lowerPath.endsWith(".png") ||
            lowerPath.endsWith(".jpg") ||
            lowerPath.endsWith(".jpeg") ||
            lowerPath.endsWith(".webp")
    }

    private fun looksLikeJson(raw: String): Boolean {
        val t = raw.trim()
        return t.startsWith("{") || t.startsWith("[")
    }

    private suspend fun absolutizeUrl(url: String): String {
        if (url.startsWith("http://") || url.startsWith("https://")) return url
        val baseUrl = settingsRepository.baseUrlFlow.first().trimEnd('/')
        return if (url.startsWith("/")) "$baseUrl$url" else "$baseUrl/$url"
    }

    private fun extractArtifactIdFromUrl(urlOrPath: String?): String? {
        val value = urlOrPath.orEmpty()
        val m = Regex("""/api/artifacts/([^/]+)/""").find(value)
        return m?.groupValues?.getOrNull(1)
    }

    private fun toStringList(element: JsonElement): List<String> {
        return (element as? JsonArray)?.mapNotNull { it.jsonPrimitive.contentOrNull } ?: emptyList()
    }

    private fun toRows(element: JsonElement, columns: List<String>): List<List<String>> {
        val arr = element as? JsonArray ?: return emptyList()
        if (arr.isEmpty()) return emptyList()
        val first = arr.first()
        return if (first is JsonObject) {
            arr.map { item ->
                val rowObj = item.jsonObject
                columns.map { col -> rowObj[col]?.jsonPrimitive?.contentOrNull ?: "—" }
            }
        } else {
            arr.map { item ->
                val row = (item as? JsonArray)?.map { it.jsonPrimitive.contentOrNull ?: "—" }.orEmpty()
                if (columns.isEmpty()) row else row + List((columns.size - row.size).coerceAtLeast(0)) { "—" }
            }
        }
    }
}
