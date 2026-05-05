package com.example.llmdataanalyst.feature.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.model.ChatItem
import com.example.llmdataanalyst.core.model.DatasetItem
import com.example.llmdataanalyst.core.model.WorkspaceResponse
import com.example.llmdataanalyst.core.repository.WorkspaceRepository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DashboardUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val workspace: WorkspaceResponse? = null,
    val chats: List<ChatItem> = emptyList(),
    val datasets: List<DatasetItem> = emptyList(),
    val artifacts: List<ArtifactItem> = emptyList()
)

class DashboardViewModel(
    private val workspaceRepository: WorkspaceRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState

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
                it.copy(
                    loading = false,
                    error = error,
                    workspace = (ws as? AppResult.Success)?.data,
                    chats = (chats as? AppResult.Success)?.data?.items.orEmpty(),
                    datasets = (datasets as? AppResult.Success)?.data?.items.orEmpty(),
                    artifacts = (artifacts as? AppResult.Success)?.data?.items.orEmpty()
                )
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
