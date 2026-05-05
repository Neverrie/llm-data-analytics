package com.example.llmdataanalyst.feature.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(Unit) {
        viewModel.loadMe()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("Настройки", style = MaterialTheme.typography.headlineSmall)

        Card {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = state.baseUrl,
                    onValueChange = viewModel::updateBaseUrl,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Backend baseUrl") },
                    supportingText = { Text("По умолчанию: http://82.162.61.44:8003") }
                )
                Button(
                    onClick = viewModel::saveBaseUrl,
                    modifier = Modifier.fillMaxWidth(),
                    contentPadding = PaddingValues(vertical = 12.dp)
                ) {
                    Text("Сохранить URL")
                }
                Button(
                    onClick = viewModel::checkHealth,
                    modifier = Modifier.fillMaxWidth(),
                    contentPadding = PaddingValues(vertical = 12.dp)
                ) {
                    if (state.loading) CircularProgressIndicator() else Text("Проверить /api/health")
                }

                if (state.health != null) {
                    Text("Health: ${state.health?.status} (${state.health?.service})")
                }
                if (state.error != null) {
                    Text(state.error ?: "", color = MaterialTheme.colorScheme.error)
                }
            }
        }

        Card {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Стриминг ответов", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Показывать ответ и прогресс анализа по мере генерации",
                    style = MaterialTheme.typography.bodySmall
                )
                Switch(
                    checked = state.streamingEnabled,
                    onCheckedChange = viewModel::setStreamingEnabled
                )
            }
        }

        Card {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text("Пользователь", style = MaterialTheme.typography.titleMedium)
                Text(state.currentUser?.email ?: "Не авторизован")
                Button(onClick = viewModel::demoLogin, modifier = Modifier.fillMaxWidth()) {
                    Text("Demo login")
                }
                Button(onClick = viewModel::logout, modifier = Modifier.fillMaxWidth()) {
                    Text("Выйти")
                }
            }
        }
    }
}
