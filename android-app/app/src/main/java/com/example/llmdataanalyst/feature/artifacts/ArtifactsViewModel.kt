package com.example.llmdataanalyst.feature.artifacts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.repository.ArtifactRepository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class ArtifactsUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val items: List<ArtifactItem> = emptyList()
)

class ArtifactsViewModel(
    private val artifactRepository: ArtifactRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(ArtifactsUiState())
    val uiState: StateFlow<ArtifactsUiState> = _uiState

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            when (val result = artifactRepository.listArtifacts()) {
                is AppResult.Success -> _uiState.update { it.copy(loading = false, items = result.data) }
                is AppResult.Error -> _uiState.update { it.copy(loading = false, error = result.message) }
            }
        }
    }
}

class ArtifactsViewModelFactory(
    private val artifactRepository: ArtifactRepository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        @Suppress("UNCHECKED_CAST")
        return ArtifactsViewModel(artifactRepository) as T
    }
}
