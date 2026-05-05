package com.example.llmdataanalyst.feature.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.llmdataanalyst.core.model.HealthResponse
import com.example.llmdataanalyst.core.model.UserPublic
import com.example.llmdataanalyst.core.repository.AuthRepository
import com.example.llmdataanalyst.core.repository.SettingsRepository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUiState(
    val baseUrl: String = "",
    val streamingEnabled: Boolean = true,
    val health: HealthResponse? = null,
    val currentUser: UserPublic? = null,
    val loading: Boolean = false,
    val error: String? = null
)

class SettingsViewModel(
    private val authRepository: AuthRepository,
    private val settingsRepository: SettingsRepository
) : ViewModel() {
    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState

    init {
        viewModelScope.launch {
            authRepository.baseUrlFlow.collect { url ->
                _uiState.update { it.copy(baseUrl = url) }
            }
        }
        viewModelScope.launch {
            settingsRepository.streamingEnabledFlow.collect { enabled ->
                _uiState.update { it.copy(streamingEnabled = enabled) }
            }
        }
    }

    fun updateBaseUrl(value: String) = _uiState.update { it.copy(baseUrl = value) }

    fun saveBaseUrl() {
        viewModelScope.launch { authRepository.setBaseUrl(uiState.value.baseUrl) }
    }

    fun checkHealth() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            when (val result = settingsRepository.checkHealth()) {
                is AppResult.Success -> _uiState.update { it.copy(loading = false, health = result.data) }
                is AppResult.Error -> _uiState.update { it.copy(loading = false, error = result.message, health = null) }
            }
        }
    }

    fun loadMe() {
        viewModelScope.launch {
            when (val result = authRepository.me()) {
                is AppResult.Success -> _uiState.update { it.copy(currentUser = result.data, error = null) }
                is AppResult.Error -> _uiState.update { it.copy(error = result.message, currentUser = null) }
            }
        }
    }

    fun demoLogin() {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, error = null) }
            when (val result = authRepository.demoLogin()) {
                is AppResult.Success -> _uiState.update { it.copy(loading = false, currentUser = result.data.user) }
                is AppResult.Error -> _uiState.update { it.copy(loading = false, error = result.message) }
            }
        }
    }

    fun logout() {
        viewModelScope.launch { authRepository.logout() }
    }

    fun setStreamingEnabled(enabled: Boolean) {
        viewModelScope.launch { settingsRepository.setStreamingEnabled(enabled) }
    }
}

class SettingsViewModelFactory(
    private val authRepository: AuthRepository,
    private val settingsRepository: SettingsRepository
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        @Suppress("UNCHECKED_CAST")
        return SettingsViewModel(authRepository, settingsRepository) as T
    }
}
