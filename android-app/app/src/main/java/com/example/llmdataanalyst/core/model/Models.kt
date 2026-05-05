package com.example.llmdataanalyst.core.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class HealthResponse(
    val status: String,
    val service: String
)

@Serializable
data class AuthLoginRequest(
    val email: String,
    val password: String
)

@Serializable
data class AuthRegisterRequest(
    val email: String,
    val password: String,
    @SerialName("display_name") val displayName: String
)

@Serializable
data class UserPublic(
    val id: String,
    val email: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("is_demo") val isDemo: Boolean
)

@Serializable
data class AuthResponse(
    val user: UserPublic,
    @SerialName("access_token") val accessToken: String,
    @SerialName("token_type") val tokenType: String = "bearer"
)

@Serializable
data class WorkspaceCounts(
    val chats: Int,
    val datasets: Int,
    val artifacts: Int
)

@Serializable
data class ChatItem(
    val id: String,
    val title: String,
    val kind: String,
    @SerialName("dataset_name") val datasetName: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    val archived: Boolean = false
)

@Serializable
data class WorkspaceResponse(
    val user: UserPublic,
    val counts: WorkspaceCounts,
    @SerialName("recent_chats") val recentChats: List<ChatItem> = emptyList(),
    @SerialName("recent_artifacts") val recentArtifacts: List<ArtifactItem> = emptyList()
)

@Serializable
data class ChatsResponse(
    val items: List<ChatItem> = emptyList()
)

@Serializable
data class DatasetItem(
    val id: String,
    val name: String,
    val source: String,
    @SerialName("rows_count") val rowsCount: Int? = null,
    @SerialName("columns_count") val columnsCount: Int? = null,
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("preview_available") val previewAvailable: Boolean = false
)

@Serializable
data class DatasetsResponse(
    val items: List<DatasetItem> = emptyList()
)

@Serializable
data class ArtifactItem(
    val id: String,
    val kind: String? = null,
    val title: String? = null,
    val filename: String? = null,
    @SerialName("mime_type") val mimeType: String? = null,
    @SerialName("size_bytes") val sizeBytes: Long? = null,
    @SerialName("created_at") val createdAt: String? = null,
    val metadata: JsonElement? = null
)

@Serializable
data class ArtifactsResponse(
    val items: List<ArtifactItem> = emptyList()
)

@Serializable
data class CreateChatRequest(
    val title: String,
    val kind: String,
    @SerialName("dataset_name") val datasetName: String? = null
)

@Serializable
data class ChatMessageCreateRequest(
    val role: String,
    val content: String,
    val blocks: List<JsonElement> = emptyList(),
    val metadata: Map<String, JsonElement> = emptyMap()
)

@Serializable
data class ChatMessageItem(
    val id: String,
    @SerialName("chat_id") val chatId: String,
    val role: String,
    val content: String,
    val blocks: List<JsonElement> = emptyList(),
    val metadata: JsonElement? = null,
    @SerialName("created_at") val createdAt: String
)

@Serializable
data class ChatDetailResponse(
    val chat: ChatItem,
    val messages: List<ChatMessageItem> = emptyList()
)

@Serializable
data class ArtifactCreatedPayload(
    @SerialName("artifact_id") val artifactId: String = "",
    val title: String? = null,
    @SerialName("mime_type") val mimeType: String? = null
)

sealed interface ChatStreamEvent {
    data class MessageStart(val chatId: String? = null, val role: String? = null) : ChatStreamEvent
    data class MessageDelta(val content: String) : ChatStreamEvent
    data class ToolStart(val name: String? = null, val title: String? = null) : ChatStreamEvent
    data class ToolLog(val content: String) : ChatStreamEvent
    data class ToolEnd(val name: String? = null, val status: String? = null) : ChatStreamEvent
    data class ArtifactCreated(
        val artifactId: String,
        val title: String? = null,
        val mimeType: String? = null
    ) : ChatStreamEvent
    data class Error(val message: String) : ChatStreamEvent
    data class Done(val status: String? = null, val messageId: String? = null) : ChatStreamEvent
    data class Unknown(val event: String, val rawData: String) : ChatStreamEvent
}

sealed interface ChatSendResult {
    data object LocalUserMessageCreated : ChatSendResult
    data object AssistantMessageStarted : ChatSendResult
    data class AssistantDelta(val content: String) : ChatSendResult
    data class ToolProgress(val message: String) : ChatSendResult
    data class ArtifactCreated(val artifactId: String, val title: String?, val mimeType: String?) : ChatSendResult
    data class Completed(val messageId: String?) : ChatSendResult
    data class Failed(val message: String) : ChatSendResult
    data object FallbackUsed : ChatSendResult
}
