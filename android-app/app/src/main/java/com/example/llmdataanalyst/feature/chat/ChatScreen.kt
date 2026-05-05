package com.example.llmdataanalyst.feature.chat

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage

@Composable
fun ChatScreen(viewModel: ChatViewModel) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    LaunchedEffect(Unit) {
        viewModel.events.collect { msg -> snackbarHostState.showSnackbar(msg) }
    }

    Column(modifier = Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SnackbarHost(hostState = snackbarHostState)
        LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.messages, key = { it.id }) { msg ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(if (msg.role == "user") "Вы" else "Ассистент", style = MaterialTheme.typography.labelMedium)
                        Text(msg.content.ifBlank { if (msg.isLoading) "Генерация..." else "" })
                        msg.toolProgress.takeLast(8).forEach {
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        msg.error?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                        }
                        msg.artifacts.forEach { art ->
                            val previewUrl = "${state.baseUrl.trimEnd('/')}/api/artifacts/${art.id}/preview"
                            Card(modifier = Modifier.fillMaxWidth()) {
                                Column(modifier = Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text(art.title ?: art.id, style = MaterialTheme.typography.bodyMedium)
                                    Text(art.mimeType ?: "", style = MaterialTheme.typography.bodySmall)
                                    val isImage = (art.mimeType ?: "").contains("image/png") || (art.title ?: "").endsWith(".png", ignoreCase = true)
                                    if (isImage) {
                                        AsyncImage(
                                            model = previewUrl,
                                            contentDescription = art.title,
                                            modifier = Modifier.fillMaxWidth().height(180.dp)
                                        )
                                    }
                                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        Button(onClick = {
                                            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(previewUrl))
                                            context.startActivity(intent)
                                        }) { Text("Открыть") }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        OutlinedTextField(
            modifier = Modifier.fillMaxWidth(),
            value = state.input,
            onValueChange = viewModel::updateInput,
            label = { Text("Сообщение") },
            enabled = !state.loading
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = viewModel::sendMessage, enabled = !state.loading) { Text("Отправить") }
            Button(onClick = viewModel::stopStreaming, enabled = state.loading) { Text("Остановить") }
            if (state.loading) CircularProgressIndicator(modifier = Modifier.padding(start = 8.dp))
        }
    }
}
