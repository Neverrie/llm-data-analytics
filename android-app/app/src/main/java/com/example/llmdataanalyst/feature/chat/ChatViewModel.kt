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

data class UiArtifact(
    val id: String,
    val title: String?,
    val mimeType: String?
)

data class UiChatMessage(
    val id: String,
    val role: String,
    val content: String,
    val isLoading: Boolean = false,
    val toolProgress: List<String> = emptyList(),
    val artifacts: List<UiArtifact> = emptyList(),
    val error: String? = null
)

data class ChatUiState(
    val chatId: String? = null,
    val baseUrl: String = "",
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
    }

    fun updateInput(value: String) = _uiState.update { it.copy(input = value) }

    fun stopStreaming() {
        streamJob?.cancel()
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) {
                updated[idx] = updated[idx].copy(
                    isLoading = false,
                    toolProgress = updated[idx].toolProgress + "Остановлено пользователем"
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
            val userMsg = UiChatMessage(id = "local-user-${System.currentTimeMillis()}", role = "user", content = text)
            val assistantId = "local-assistant-${System.currentTimeMillis()}"
            val assistant = UiChatMessage(id = assistantId, role = "assistant", content = "", isLoading = true)
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
                    is ChatSendResult.ArtifactCreated -> appendArtifact(result.artifactId, result.title, result.mimeType)
                    is ChatSendResult.FallbackUsed -> {
                        usedFallback = true
                        _events.emit("Стриминг недоступен, использую обычный режим")
                        val jsonMsg = chatRepository.sendMessageJson(chatId, request)
                        setAssistantFinal(jsonMsg.content)
                    }
                    is ChatSendResult.Completed -> {
                        gotDone = true
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
                if (idx >= 0) updated[idx] = updated[idx].copy(isLoading = false)
                it.copy(loading = false, messages = updated)
            }
        }
    }

    private suspend fun syncChat(chatId: String) {
        val detail = chatRepository.getChat(chatId)
        val mapped = detail.messages.map {
            UiChatMessage(
                id = it.id,
                role = it.role,
                content = it.content,
                isLoading = false
            )
        }
        _uiState.update { it.copy(messages = mapped) }
    }

    private fun appendAssistantDelta(delta: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) updated[idx] = updated[idx].copy(content = updated[idx].content + delta)
            it.copy(messages = updated)
        }
    }

    private fun appendToolLog(line: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) updated[idx] = updated[idx].copy(toolProgress = updated[idx].toolProgress + line)
            it.copy(messages = updated)
        }
    }

    private fun appendArtifact(id: String, title: String?, mimeType: String?) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) {
                val exists = updated[idx].artifacts.any { a -> a.id == id }
                if (!exists) updated[idx] = updated[idx].copy(artifacts = updated[idx].artifacts + UiArtifact(id, title, mimeType))
            }
            it.copy(messages = updated)
        }
    }

    private fun appendError(message: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) updated[idx] = updated[idx].copy(error = message, isLoading = false)
            it.copy(messages = updated, loading = false)
        }
    }

    private fun setAssistantFinal(content: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) updated[idx] = updated[idx].copy(content = content, isLoading = false)
            it.copy(messages = updated, loading = false)
        }
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
