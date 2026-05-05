package com.example.llmdataanalyst.core.network

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

class AuthStateHolder {
    private val _tokenState = MutableStateFlow<String?>(null)
    val tokenState: StateFlow<String?> = _tokenState

    fun updateToken(token: String?) {
        _tokenState.value = token
    }
}
