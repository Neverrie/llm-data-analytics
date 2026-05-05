package com.example.llmdataanalyst.core.datastore

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "app_prefs")

class AppPreferences(private val context: Context) {
    companion object {
        const val DEFAULT_BASE_URL = "http://82.162.61.44:8003"
    }

    private object Keys {
        val baseUrl: Preferences.Key<String> = stringPreferencesKey("base_url")
        val token: Preferences.Key<String> = stringPreferencesKey("auth_token")
        val streamingEnabled: Preferences.Key<Boolean> = booleanPreferencesKey("streaming_enabled")
    }

    val baseUrlFlow: Flow<String> = context.dataStore.data.map { prefs ->
        normalizeUrl(prefs[Keys.baseUrl] ?: DEFAULT_BASE_URL)
    }

    val tokenFlow: Flow<String?> = context.dataStore.data.map { prefs -> prefs[Keys.token] }
    val streamingEnabledFlow: Flow<Boolean> = context.dataStore.data.map { prefs ->
        prefs[Keys.streamingEnabled] ?: true
    }

    suspend fun setBaseUrl(url: String) {
        context.dataStore.edit { prefs -> prefs[Keys.baseUrl] = normalizeUrl(url) }
    }

    suspend fun setToken(token: String?) {
        context.dataStore.edit { prefs ->
            if (token.isNullOrBlank()) {
                prefs.remove(Keys.token)
            } else {
                prefs[Keys.token] = token
            }
        }
    }

    suspend fun setStreamingEnabled(enabled: Boolean) {
        context.dataStore.edit { prefs -> prefs[Keys.streamingEnabled] = enabled }
    }

    private fun normalizeUrl(url: String): String {
        val trimmed = url.trim()
        if (trimmed.isBlank()) return "$DEFAULT_BASE_URL/"
        val withScheme = if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) trimmed else "http://$trimmed"
        return if (withScheme.endsWith("/")) withScheme else "$withScheme/"
    }
}
