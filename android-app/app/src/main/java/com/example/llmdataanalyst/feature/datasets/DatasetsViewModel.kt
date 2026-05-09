package com.example.llmdataanalyst.feature.datasets

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.model.DatasetItem
import com.example.llmdataanalyst.core.model.DatasetPreviewResponse
import com.example.llmdataanalyst.core.model.DatasetProfileResponse
import com.example.llmdataanalyst.core.repository.DatasetRepository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.io.File

data class DatasetsUiState(
    val loading: Boolean = false,
    val error: String? = null,
    val items: List<DatasetItem> = emptyList(),
    val selectedDatasetId: String? = null,
    val preview: DatasetPreviewResponse? = null,
    val profile: DatasetProfileResponse? = null
)

class DatasetsViewModel(
    private val datasetRepository: DatasetRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(DatasetsUiState())
    val uiState: StateFlow<DatasetsUiState> = _uiState

    fun loadDatasets() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            when (val result = datasetRepository.listDatasets()) {
                is AppResult.Success -> _uiState.update {
                    it.copy(loading = false, items = result.data, selectedDatasetId = it.selectedDatasetId ?: result.data.firstOrNull()?.id)
                }
                is AppResult.Error -> _uiState.update { it.copy(loading = false, error = result.message) }
            }
        }
    }

    fun uploadDataset(file: File) {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            when (val result = datasetRepository.uploadDataset(file)) {
                is AppResult.Success -> {
                    loadDatasets()
                    _uiState.update { it.copy(selectedDatasetId = result.data.id) }
                }
                is AppResult.Error -> _uiState.update { it.copy(loading = false, error = result.message) }
            }
        }
    }

    fun selectDataset(datasetId: String) {
        _uiState.update { it.copy(selectedDatasetId = datasetId) }
    }

    fun deleteDataset(datasetId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            when (val result = datasetRepository.deleteDataset(datasetId)) {
                is AppResult.Success -> {
                    val oldSelected = _uiState.value.selectedDatasetId
                    loadDatasets()
                    if (oldSelected == datasetId) {
                        _uiState.update { it.copy(selectedDatasetId = null, preview = null, profile = null) }
                    }
                }
                is AppResult.Error -> _uiState.update { it.copy(loading = false, error = result.message) }
            }
        }
    }

    fun loadDetail(datasetId: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null, selectedDatasetId = datasetId) }
            val preview = datasetRepository.previewDataset(datasetId)
            val profile = datasetRepository.profileDataset(datasetId)
            _uiState.update {
                it.copy(
                    loading = false,
                    preview = (preview as? AppResult.Success)?.data,
                    profile = (profile as? AppResult.Success)?.data,
                    error = (preview as? AppResult.Error)?.message ?: (profile as? AppResult.Error)?.message
                )
            }
        }
    }
}

class DatasetsViewModelFactory(
    private val datasetRepository: DatasetRepository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        @Suppress("UNCHECKED_CAST")
        return DatasetsViewModel(datasetRepository) as T
    }
}
