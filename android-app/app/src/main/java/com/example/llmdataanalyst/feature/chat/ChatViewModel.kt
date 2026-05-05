package com.example.llmdataanalyst.feature.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.model.ChatMessageCreateRequest
import com.example.llmdataanalyst.core.model.ChatSendResult
import com.example.llmdataanalyst.core.repository.ChatRepository
import com.example.llmdataanalyst.core.repository.SettingsRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

data class UiChatMessage(
    val id: String,
    val role: String,
    val content: String,
    val isLoading: Boolean = false,
    val toolProgress: List<String> = emptyList(),
    val error: String? = null,
    val visualBlocks: List<ChatContentBlock> = emptyList(),
    val blocks: List<ChatContentBlock> = emptyList()
)

data class ChatUiState(
    val chatId: String? = null,
    val baseUrl: String = "",
    val token: String? = null,
    val loading: Boolean = false,
    val input: String = "",
    val messages: List<UiChatMessage> = emptyList()
)

class ChatViewModel(
    private val chatRepository: ChatRepository,
    private val settingsRepository: SettingsRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState

    private val _events = MutableSharedFlow<String>()
    val events = _events.asSharedFlow()

    private var streamJob: Job? = null

    init {
        viewModelScope.launch {
            settingsRepository.baseUrlFlow.collect { url ->
                _uiState.update { it.copy(baseUrl = url) }
            }
        }
        viewModelScope.launch {
            settingsRepository.tokenFlow.collect { token ->
                _uiState.update { it.copy(token = token) }
            }
        }
    }

    fun updateInput(value: String) = _uiState.update { it.copy(input = value) }

    fun stopStreaming() {
        streamJob?.cancel()
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) {
                updated[idx] = rebuildMessage(
                    updated[idx].copy(
                        isLoading = false,
                        toolProgress = updated[idx].toolProgress + "Остановлено пользователем"
                    )
                )
            }
            it.copy(loading = false, messages = updated)
        }
    }

    fun sendMessage() {
        val text = uiState.value.input.trim()
        if (text.isBlank() || uiState.value.loading) return

        streamJob = viewModelScope.launch {
            val chatId = uiState.value.chatId ?: chatRepository.createChat().id
            val userMsg = UiChatMessage(
                id = "local-user-${System.currentTimeMillis()}",
                role = "user",
                content = text,
                blocks = listOf(ChatContentBlock.TextBlock(text))
            )
            val assistantId = "local-assistant-${System.currentTimeMillis()}"
            val assistant = UiChatMessage(
                id = assistantId,
                role = "assistant",
                content = "",
                isLoading = true,
                blocks = listOf(ChatContentBlock.TextBlock(""))
            )
            _uiState.update {
                it.copy(
                    chatId = chatId,
                    loading = true,
                    input = "",
                    messages = it.messages + listOf(userMsg, assistant)
                )
            }

            val request = ChatMessageCreateRequest(
                role = "user",
                content = text,
                blocks = emptyList(),
                metadata = mapOf("client" to buildJsonObject { put("platform", "android") })
            )
            var usedFallback = false
            var gotDone = false

            chatRepository.sendMessage(chatId, request, settingsRepository.streamingEnabledFlow.first()).collect { result ->
                when (result) {
                    is ChatSendResult.AssistantDelta -> appendAssistantDelta(result.content)
                    is ChatSendResult.ToolProgress -> appendToolLog(result.message)
                    is ChatSendResult.ArtifactCreated -> {
                        if (result.artifactId.isNotBlank()) {
                            hydrateArtifactBlock(
                                assistantMessageId = assistantId,
                                artifactId = result.artifactId,
                                title = result.title,
                                mimeType = result.mimeType
                            )
                        }
                    }
                    is ChatSendResult.FallbackUsed -> {
                        usedFallback = true
                        _events.emit("Стриминг недоступен, использую обычный режим")
                        val jsonMsg = chatRepository.sendMessageJson(chatId, request)
                        setAssistantFinal(jsonMsg.content)
                    }
                    is ChatSendResult.Completed -> {
                        gotDone = true
                        result.messageId?.let { replaceTemporaryAssistantId(assistantId, it) }
                        syncChat(chatId)
                    }
                    is ChatSendResult.Failed -> {
                        appendError(result.message)
                        _events.emit(result.message)
                    }
                    else -> Unit
                }
            }

            if (!gotDone && !usedFallback) {
                _events.emit("Ответ завершён")
            }
            _uiState.update {
                val updated = it.messages.toMutableList()
                val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
                if (idx >= 0) updated[idx] = rebuildMessage(updated[idx].copy(isLoading = false))
                it.copy(loading = false, messages = updated)
            }
        }
    }

    private fun hydrateArtifactBlock(
        assistantMessageId: String,
        artifactId: String,
        title: String?,
        mimeType: String?
    ) {
        // placeholder while preview loading
        addVisualBlock(
            assistantMessageId,
            ChatContentBlock.UnsupportedArtifactBlock(
                artifactId = artifactId,
                title = "Загружаю предпросмотр...",
                mimeType = mimeType
            ),
            replaceSameArtifact = true
        )

        viewModelScope.launch {
            val block = chatRepository.buildVisualBlockFromArtifact(artifactId, title, mimeType)
            addVisualBlock(assistantMessageId, block, replaceSameArtifact = true)
        }
    }

    private suspend fun syncChat(chatId: String) {
        val currentVisual = uiState.value.messages
            .lastOrNull { it.role == "assistant" }
            ?.visualBlocks
            .orEmpty()

        val detail = chatRepository.getChat(chatId)
        val mapped = detail.messages.map {
            val base = UiChatMessage(
                id = it.id,
                role = it.role,
                content = it.content,
                isLoading = false
            )
            if (it.role == "assistant") {
                rebuildMessage(base.copy(visualBlocks = currentVisual))
            } else {
                base.copy(blocks = listOf(ChatContentBlock.TextBlock(it.content)))
            }
        }
        _uiState.update { it.copy(messages = mapped) }
    }

    private fun appendAssistantDelta(delta: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) {
                updated[idx] = rebuildMessage(updated[idx].copy(content = updated[idx].content + delta))
            }
            it.copy(messages = updated)
        }
    }

    private fun appendToolLog(line: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) updated[idx] = rebuildMessage(updated[idx].copy(toolProgress = updated[idx].toolProgress + line))
            it.copy(messages = updated)
        }
    }

    private fun appendError(message: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) updated[idx] = rebuildMessage(updated[idx].copy(error = message, isLoading = false))
            it.copy(messages = updated, loading = false)
        }
    }

    private fun setAssistantFinal(content: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) updated[idx] = rebuildMessage(updated[idx].copy(content = content, isLoading = false))
            it.copy(messages = updated, loading = false)
        }
    }

    private fun replaceTemporaryAssistantId(tempId: String, serverId: String) {
        _uiState.update {
            it.copy(messages = it.messages.map { msg -> if (msg.id == tempId) msg.copy(id = serverId) else msg })
        }
    }

    private fun addVisualBlock(
        assistantMessageId: String,
        block: ChatContentBlock,
        replaceSameArtifact: Boolean = false
    ) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.id == assistantMessageId || (msg.role == "assistant" && msg.isLoading) }
            if (idx >= 0) {
                val current = updated[idx]
                val nextVisual = if (replaceSameArtifact) {
                    current.visualBlocks.filterNot { old ->
                        old is ChatContentBlock.UnsupportedArtifactBlock && block is ChatContentBlock.UnsupportedArtifactBlock && old.artifactId == block.artifactId ||
                            old is ChatContentBlock.ImageArtifactBlock && block is ChatContentBlock.ImageArtifactBlock && old.artifactId == block.artifactId ||
                            old is ChatContentBlock.TableBlock && block is ChatContentBlock.TableBlock && old.sourceArtifactId != null && old.sourceArtifactId == block.sourceArtifactId ||
                            old is ChatContentBlock.JsonBlock && block is ChatContentBlock.JsonBlock && old.sourceArtifactId != null && old.sourceArtifactId == block.sourceArtifactId
                    } + block
                } else {
                    current.visualBlocks + block
                }
                updated[idx] = rebuildMessage(current.copy(visualBlocks = nextVisual))
            }
            it.copy(messages = updated)
        }
    }

    private fun rebuildMessage(message: UiChatMessage): UiChatMessage {
        if (message.role != "assistant") {
            return message.copy(blocks = listOf(ChatContentBlock.TextBlock(message.content)))
        }
        val textBlocks = MarkdownTableParser.parseToBlocks(message.content)
        val merged = textBlocks + message.visualBlocks
        return message.copy(blocks = merged)
    }
}

class ChatViewModelFactory(
    private val chatRepository: ChatRepository,
    private val settingsRepository: SettingsRepository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        @Suppress("UNCHECKED_CAST")
        return ChatViewModel(chatRepository, settingsRepository) as T
    }
}
