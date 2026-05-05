package com.example.llmdataanalyst.feature.lab2

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.repository.Lab2Repository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement

data class Lab2UiState(
    val loading: Boolean = false,
    val running: Boolean = false,
    val error: String? = null,
    val status: JsonElement? = null,
    val sampleData: JsonElement? = null,
    val result: JsonElement? = null,
    val info: String? = null
)

class Lab2ViewModel(
    private val lab2Repository: Lab2Repository
) : ViewModel() {
    private val _uiState = MutableStateFlow(Lab2UiState())
    val uiState: StateFlow<Lab2UiState> = _uiState

    fun load() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            val status = lab2Repository.status()
            val sample = lab2Repository.sampleData()
            val result = lab2Repository.result()
            _uiState.update {
                it.copy(
                    loading = false,
                    status = (status as? AppResult.Success)?.data,
                    sampleData = (sample as? AppResult.Success)?.data,
                    result = (result as? AppResult.Success)?.data,
                    error = (status as? AppResult.Error)?.message
                        ?: (sample as? AppResult.Error)?.message
                        ?: (result as? AppResult.Error)?.message
                )
            }
        }
    }

    fun runPipeline() {
        viewModelScope.launch {
            _uiState.update { it.copy(running = true, error = null, info = null) }
            when (val run = lab2Repository.run()) {
                is AppResult.Success -> _uiState.update { it.copy(running = false, info = "Pipeline запущен", result = run.data) }
                is AppResult.Error -> _uiState.update { it.copy(running = false, error = run.message) }
            }
        }
    }
}

class Lab2ViewModelFactory(
    private val lab2Repository: Lab2Repository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        @Suppress("UNCHECKED_CAST")
        return Lab2ViewModel(lab2Repository) as T
    }
}
