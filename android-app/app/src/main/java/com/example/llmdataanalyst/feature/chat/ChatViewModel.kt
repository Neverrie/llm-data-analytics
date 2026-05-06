package com.example.llmdataanalyst.feature.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.model.ChatMessageCreateRequest
import com.example.llmdataanalyst.core.model.ChatSendResult
import com.example.llmdataanalyst.core.model.DatasetItem
import com.example.llmdataanalyst.core.repository.ChatExecutionMode
import com.example.llmdataanalyst.core.repository.ChatRepository
import com.example.llmdataanalyst.core.repository.DatasetRepository
import com.example.llmdataanalyst.core.repository.SettingsRepository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
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
    val selectedDatasetId: String? = null,
    val selectedDatasetName: String? = null,
    val executionMode: ChatExecutionMode = ChatExecutionMode.GeneralChat,
    val datasets: List<DatasetItem> = emptyList(),
    val loading: Boolean = false,
    val input: String = "",
    val messages: List<UiChatMessage> = emptyList()
)

class ChatViewModel(
    private val chatRepository: ChatRepository,
    private val datasetRepository: DatasetRepository,
    private val settingsRepository: SettingsRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState

    private val _events = MutableSharedFlow<String>()
    val events = _events.asSharedFlow()

    private var streamJob: Job? = null

    init {
        viewModelScope.launch {
            settingsRepository.baseUrlFlow.collect { url -> _uiState.update { it.copy(baseUrl = url) } }
        }
        viewModelScope.launch {
            settingsRepository.tokenFlow.collect { token -> _uiState.update { it.copy(token = token) } }
        }
        loadDatasets()
    }

    fun updateInput(value: String) = _uiState.update { it.copy(input = value) }

    fun stopStreaming() {
        streamJob?.cancel()
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) {
                updated[idx] = rebuildMessage(
                    updated[idx].copy(isLoading = false, toolProgress = updated[idx].toolProgress + "Остановлено пользователем")
                )
            }
            it.copy(loading = false, messages = updated)
        }
    }

    fun selectDataset(datasetId: String?, datasetName: String?) {
        _uiState.update {
            it.copy(
                selectedDatasetId = datasetId,
                selectedDatasetName = datasetName ?: resolveDatasetName(datasetId, it.datasets),
                executionMode = if (!datasetId.isNullOrBlank()) ChatExecutionMode.DatasetAgent else ChatExecutionMode.GeneralChat
            )
        }
    }

    fun clearSelectedDataset() {
        _uiState.update { it.copy(selectedDatasetId = null, selectedDatasetName = null, executionMode = ChatExecutionMode.GeneralChat) }
    }

    fun executionMode(): ChatExecutionMode {
        return if (!uiState.value.selectedDatasetId.isNullOrBlank()) ChatExecutionMode.DatasetAgent else ChatExecutionMode.GeneralChat
    }

    fun openChat(chatId: String) {
        if (chatId.isBlank()) return
        viewModelScope.launch {
            runCatching { chatRepository.getChat(chatId) }
                .onSuccess { detail ->
                    val mapped = detail.messages.map { msg ->
                        val normalizedContent = if (msg.role == "user") chatRepository.stripDatasetTechnicalPrefix(msg.content) else msg.content
                        val base = UiChatMessage(id = msg.id, role = msg.role, content = normalizedContent, isLoading = false)
                        if (msg.role == "assistant") rebuildMessage(base) else base.copy(blocks = listOf(ChatContentBlock.TextBlock(normalizedContent)))
                    }
                    _uiState.update { it.copy(chatId = chatId, messages = mapped) }
                }
        }
    }

    private fun loadDatasets() {
        viewModelScope.launch {
            when (val result = datasetRepository.listDatasets()) {
                is AppResult.Success -> _uiState.update {
                    val resolvedName = it.selectedDatasetName ?: resolveDatasetName(it.selectedDatasetId, result.data)
                    it.copy(datasets = result.data, selectedDatasetName = resolvedName)
                }
                is AppResult.Error -> Unit
            }
        }
    }

    fun sendMessage() {
        sendMessageWithText(uiState.value.input.trim(), clearInput = true)
    }

    fun sendPreset(prompt: String) {
        sendMessageWithText(prompt.trim(), clearInput = false)
    }

    private fun sendMessageWithText(text: String, clearInput: Boolean) {
        if (text.isBlank() || uiState.value.loading) return
        streamJob = viewModelScope.launch {
            val mode = executionMode()
            val chatId = if (mode == ChatExecutionMode.GeneralChat) {
                uiState.value.chatId ?: chatRepository.createChat(uiState.value.selectedDatasetName).id
            } else {
                uiState.value.chatId ?: chatRepository.createChat(uiState.value.selectedDatasetName).id
            }

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
                    input = if (clearInput) "" else it.input,
                    messages = it.messages + listOf(userMsg, assistant)
                )
            }

            val request = ChatMessageCreateRequest(
                role = "user",
                content = buildRequestContentForMode(text, mode),
                blocks = emptyList(),
                metadata = buildMap {
                    put("client", buildJsonObject { put("platform", "android") })
                    uiState.value.selectedDatasetId?.let { put("dataset_id", JsonPrimitive(it)) }
                    uiState.value.selectedDatasetName?.let { put("dataset_name", JsonPrimitive(it)) }
                }
            )

            var usedFallback = false
            var gotDone = false
            val artifactsBefore = if (mode == ChatExecutionMode.DatasetAgent) chatRepository.listArtifacts().map { it.id }.toSet() else emptySet()

            chatRepository.sendMessage(
                mode = mode,
                chatId = chatId,
                request = request,
                streamingEnabled = settingsRepository.streamingEnabledFlow.first(),
                datasetName = uiState.value.selectedDatasetName
            ).collect { result ->
                when (result) {
                    is ChatSendResult.AssistantDelta -> appendAssistantDelta(result.content)
                    is ChatSendResult.ToolProgress -> appendToolLog(result.message)
                    is ChatSendResult.ArtifactCreated -> {
                        if (result.artifactId.isNotBlank()) {
                            hydrateArtifactBlock(assistantMessageId = assistantId, artifactId = result.artifactId, title = result.title, mimeType = result.mimeType)
                        }
                    }
                    is ChatSendResult.FallbackUsed -> {
                        usedFallback = true
                        _events.emit("Стриминг недоступен, использую обычный режим")
                        if (mode == ChatExecutionMode.DatasetAgent) {
                            val response = chatRepository.sendLab3Json(uiState.value.selectedDatasetName.orEmpty(), text)
                            val finalAnswer = extractLab3FinalAnswer(response)
                            setAssistantFinal(finalAnswer)
                            refreshArtifactsAfterAgent(assistantId, artifactsBefore)
                        } else {
                            val jsonMsg = chatRepository.sendMessageJson(chatId, request)
                            setAssistantFinal(chatRepository.stripDatasetTechnicalPrefix(jsonMsg.content))
                        }
                    }
                    is ChatSendResult.Completed -> {
                        gotDone = true
                        if (mode == ChatExecutionMode.DatasetAgent) {
                            runCatching {
                                val lab3 = chatRepository.getLab3Result()
                                val finalText = extractLab3FinalAnswer(lab3)
                                if (finalText.isNotBlank()) setAssistantFinal(finalText)
                            }
                            refreshArtifactsAfterAgent(assistantId, artifactsBefore)
                        } else {
                            result.messageId?.let { replaceTemporaryAssistantId(assistantId, it) }
                            syncChat(chatId)
                        }
                    }
                    is ChatSendResult.Failed -> {
                        appendError(result.message)
                        _events.emit(result.message)
                    }
                    else -> Unit
                }
            }

            if (!gotDone && !usedFallback) _events.emit("Ответ завершён")
            _uiState.update {
                val updated = it.messages.toMutableList()
                val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
                if (idx >= 0) updated[idx] = rebuildMessage(updated[idx].copy(isLoading = false))
                it.copy(loading = false, messages = updated)
            }
        }
    }

    private fun buildRequestContentForMode(userText: String, mode: ChatExecutionMode): String {
        return if (mode == ChatExecutionMode.DatasetAgent) {
            "$userText\n\nИспользуй доступные инструменты backend при необходимости и верни краткий результат."
        } else {
            userText
        }
    }

    private fun extractLab3FinalAnswer(payload: kotlinx.serialization.json.JsonElement): String {
        return runCatching {
            payload.jsonObject["final_answer"]?.toString()?.trim('"')
        }.getOrNull().orEmpty()
    }

    private suspend fun refreshArtifactsAfterAgent(assistantMessageId: String, beforeIds: Set<String>) {
        val now = chatRepository.listArtifacts()
        val newItems = now.filter { it.id !in beforeIds }.takeLast(6)
        if (newItems.isNotEmpty()) {
            _events.emit("Найдено новых артефактов: ${newItems.size}")
        }
        newItems.forEach { art ->
            hydrateArtifactBlock(
                assistantMessageId = assistantMessageId,
                artifactId = art.id,
                title = art.title ?: art.filename,
                mimeType = art.mimeType
            )
        }
    }

    private fun resolveDatasetName(datasetId: String?, datasets: List<DatasetItem>): String? {
        if (datasetId.isNullOrBlank()) return null
        return datasets.firstOrNull { it.id == datasetId }?.name
    }

    private fun hydrateArtifactBlock(assistantMessageId: String, artifactId: String, title: String?, mimeType: String?) {
        addVisualBlock(
            assistantMessageId,
            ChatContentBlock.UnsupportedArtifactBlock(artifactId = artifactId, title = "Загружаю предпросмотр...", mimeType = mimeType),
            replaceSameArtifact = true
        )
        viewModelScope.launch {
            val block = chatRepository.buildVisualBlockFromArtifact(artifactId, title, mimeType)
            addVisualBlock(assistantMessageId, block, replaceSameArtifact = true)
        }
    }

    private suspend fun syncChat(chatId: String) {
        val currentVisual = uiState.value.messages.lastOrNull { it.role == "assistant" }?.visualBlocks.orEmpty()
        val detail = chatRepository.getChat(chatId)
        val mapped = detail.messages.map {
            val normalizedContent = if (it.role == "user") chatRepository.stripDatasetTechnicalPrefix(it.content) else it.content
            val base = UiChatMessage(id = it.id, role = it.role, content = normalizedContent, isLoading = false)
            if (it.role == "assistant") rebuildMessage(base.copy(visualBlocks = currentVisual)) else base.copy(blocks = listOf(ChatContentBlock.TextBlock(normalizedContent)))
        }
        _uiState.update { it.copy(messages = mapped) }
    }

    private fun appendAssistantDelta(delta: String) {
        _uiState.update {
            val updated = it.messages.toMutableList()
            val idx = updated.indexOfLast { msg -> msg.role == "assistant" && msg.isLoading }
            if (idx >= 0) {
                val merged = sanitizeAssistantText(updated[idx].content + delta)
                updated[idx] = rebuildMessage(updated[idx].copy(content = merged))
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
            if (idx >= 0) updated[idx] = rebuildMessage(updated[idx].copy(content = sanitizeAssistantText(content), isLoading = false))
            it.copy(messages = updated, loading = false)
        }
    }

    private fun replaceTemporaryAssistantId(tempId: String, serverId: String) {
        _uiState.update { it.copy(messages = it.messages.map { msg -> if (msg.id == tempId) msg.copy(id = serverId) else msg }) }
    }

    private fun addVisualBlock(assistantMessageId: String, block: ChatContentBlock, replaceSameArtifact: Boolean = false) {
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
        if (message.role != "assistant") return message.copy(blocks = listOf(ChatContentBlock.TextBlock(message.content)))
        val textBlocks = MarkdownTableParser.parseToBlocks(sanitizeAssistantText(message.content))
        return message.copy(blocks = textBlocks + message.visualBlocks)
    }

    private fun sanitizeAssistantText(text: String): String {
        return text
            .replace(Regex("""<\s*/?\s*FINAL\s*>""", RegexOption.IGNORE_CASE), "")
            .replace(Regex("""^\s*FINAL\s*:?\s*""", RegexOption.IGNORE_CASE), "")
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .trim()
    }

    fun renderMarkdownLikeText(text: String): String {
        return sanitizeAssistantText(text)
            .replace("**", "")
            .replace(Regex("""`{1,3}"""), "")
    }
}

class ChatViewModelFactory(
    private val chatRepository: ChatRepository,
    private val datasetRepository: DatasetRepository,
    private val settingsRepository: SettingsRepository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        @Suppress("UNCHECKED_CAST")
        return ChatViewModel(chatRepository, datasetRepository, settingsRepository) as T
    }
}
