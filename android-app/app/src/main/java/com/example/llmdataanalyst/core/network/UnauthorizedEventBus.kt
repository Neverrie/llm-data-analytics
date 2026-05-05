package com.example.llmdataanalyst.core.network

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow

class UnauthorizedEventBus {
    private val _events = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val events: SharedFlow<Unit> = _events

    fun emitUnauthorized() {
        _events.tryEmit(Unit)
    }
}
