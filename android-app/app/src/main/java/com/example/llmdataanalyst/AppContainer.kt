package com.example.llmdataanalyst

import android.content.Context
import com.example.llmdataanalyst.core.datastore.AppPreferences
import com.example.llmdataanalyst.core.network.ApiClientFactory
import com.example.llmdataanalyst.core.network.AuthStateHolder
import com.example.llmdataanalyst.core.network.ChatStreamClient
import com.example.llmdataanalyst.core.network.UnauthorizedEventBus
import com.example.llmdataanalyst.core.repository.ApiProvider
import com.example.llmdataanalyst.core.repository.AuthRepository
import com.example.llmdataanalyst.core.repository.ChatRepository
import com.example.llmdataanalyst.core.repository.SettingsRepository
import com.example.llmdataanalyst.core.repository.WorkspaceRepository

class AppContainer(context: Context) {
    private val appPreferences = AppPreferences(context)
    val authStateHolder = AuthStateHolder()
    val unauthorizedEventBus = UnauthorizedEventBus()
    private val apiClientFactory = ApiClientFactory(authStateHolder, unauthorizedEventBus)
    private val apiProvider = ApiProvider(appPreferences, apiClientFactory)
    private val streamClient = ChatStreamClient(authStateHolder)

    val authRepository = AuthRepository(apiProvider, appPreferences, authStateHolder)
    val settingsRepository = SettingsRepository(
        apiProvider = apiProvider,
        baseUrlFlow = appPreferences.baseUrlFlow,
        streamingEnabledFlow = appPreferences.streamingEnabledFlow,
        onSetStreamingEnabled = appPreferences::setStreamingEnabled
    )
    val workspaceRepository = WorkspaceRepository(apiProvider)
    val chatRepository = ChatRepository(apiProvider, settingsRepository, streamClient)
}
