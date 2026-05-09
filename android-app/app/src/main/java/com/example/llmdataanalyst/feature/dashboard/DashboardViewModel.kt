package com.example.llmdataanalyst.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.model.ChatItem
import com.example.llmdataanalyst.core.model.DatasetItem
import com.example.llmdataanalyst.core.model.UpdateChatRequest
import com.example.llmdataanalyst.core.model.WorkspaceResponse
import com.example.llmdataanalyst.core.repository.WorkspaceRepository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DashboardUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val workspace: WorkspaceResponse? = null,
    val chats: List<ChatItem> = emptyList(),
    val datasets: List<DatasetItem> = emptyList(),
    val artifacts: List<ArtifactItem> = emptyList()
) {
    val chatsCount: Int get() = workspace?.counts?.chats ?: chats.size
    val datasetsCount: Int get() = workspace?.counts?.datasets ?: datasets.size
    val artifactsCount: Int get() = workspace?.counts?.artifacts ?: artifacts.size
}

class DashboardViewModel(
    private val workspaceRepository: WorkspaceRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState
    private val _events = MutableSharedFlow<String>()
    val events = _events.asSharedFlow()

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            val wsDef = async { workspaceRepository.workspace() }
            val chatsDef = async { workspaceRepository.chats() }
            val datasetsDef = async { workspaceRepository.datasets() }
            val artifactsDef = async { workspaceRepository.artifacts() }

            val ws = wsDef.await()
            val chats = chatsDef.await()
            val datasets = datasetsDef.await()
            val artifacts = artifactsDef.await()

            val error = listOf(ws, chats, datasets, artifacts)
                .filterIsInstance<AppResult.Error>()
                .firstOrNull()
                ?.message

            _uiState.update {
                val activeChats = (chats as? AppResult.Success)?.data?.items.orEmpty().filter { c -> !c.archived }
                it.copy(
                    loading = false,
                    error = error,
                    workspace = (ws as? AppResult.Success)?.data,
                    chats = activeChats,
                    datasets = (datasets as? AppResult.Success)?.data?.items.orEmpty(),
                    artifacts = (artifacts as? AppResult.Success)?.data?.items.orEmpty()
                )
            }
        }
    }

    fun renameChat(chatId: String, title: String) {
        if (title.isBlank()) return
        viewModelScope.launch {
            when (val result = workspaceRepository.updateChat(chatId, UpdateChatRequest(title = title.trim()))) {
                is AppResult.Success -> {
                    _uiState.update { state ->
                        state.copy(chats = state.chats.map { if (it.id == chatId) result.data else it })
                    }
                    _events.emit("Чат переименован")
                }
                is AppResult.Error -> _events.emit(result.message)
            }
        }
    }

    fun deleteChat(chatId: String) {
        viewModelScope.launch {
            when (val result = workspaceRepository.deleteChat(chatId)) {
                is AppResult.Success -> {
                    _uiState.update { state -> state.copy(chats = state.chats.filterNot { it.id == chatId }) }
                    _events.emit("Чат удалён")
                }
                is AppResult.Error -> _events.emit(result.message)
            }
        }
    }
}

class DashboardViewModelFactory(
    private val workspaceRepository: WorkspaceRepository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        @Suppress("UNCHECKED_CAST")
        return DashboardViewModel(workspaceRepository) as T
    }
}
