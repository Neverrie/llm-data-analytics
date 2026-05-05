package com.example.llmdataanalyst.feature.chat

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import coil.request.ImageRequest
import okhttp3.Headers

@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    onOpenArtifact: (String) -> Unit
) {
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
                        val blocks = if (msg.blocks.isEmpty()) listOf(ChatContentBlock.TextBlock(msg.content)) else msg.blocks
                        blocks.forEach { block ->
                            when (block) {
                                is ChatContentBlock.TextBlock -> {
                                    if (block.text.isNotBlank()) Text(block.text)
                                }
                                is ChatContentBlock.MarkdownBlock -> {
                                    Text(block.text)
                                }
                                is ChatContentBlock.ImageArtifactBlock -> {
                                    Text(block.title ?: "Изображение", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                                    val request = ImageRequest.Builder(context)
                                        .data(block.previewUrl)
                                        .apply {
                                            val token = state.token
                                            if (!token.isNullOrBlank()) {
                                                headers(Headers.headersOf("Authorization", "Bearer $token"))
                                            }
                                        }
                                        .crossfade(true)
                                        .build()
                                    AsyncImage(
                                        model = request,
                                        contentDescription = block.title,
                                        modifier = Modifier.fillMaxWidth().height(220.dp)
                                    )
                                    Button(onClick = { onOpenArtifact(block.artifactId) }) { Text("Открыть артефакт") }
                                }
                                is ChatContentBlock.TableBlock -> {
                                    if (!block.title.isNullOrBlank()) {
                                        Text(block.title, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
                                    }
                                    val hs = rememberScrollState()
                                    Column(modifier = Modifier.fillMaxWidth().horizontalScroll(hs)) {
                                        Row {
                                            block.columns.forEach { col ->
                                                Text(
                                                    text = col,
                                                    modifier = Modifier.padding(6.dp),
                                                    fontWeight = FontWeight.Bold
                                                )
                                            }
                                        }
                                        block.rows.take(20).forEach { row ->
                                            Row {
                                                row.forEach { cell ->
                                                    Text(text = cell.ifBlank { "—" }, modifier = Modifier.padding(6.dp))
                                                }
                                            }
                                        }
                                    }
                                    if (block.truncated) {
                                        Text("Показаны первые 20 строк", style = MaterialTheme.typography.bodySmall)
                                    }
                                    block.sourceArtifactId?.let { artifactId ->
                                        Button(onClick = { onOpenArtifact(artifactId) }) { Text("Открыть артефакт") }
                                    }
                                }
                                is ChatContentBlock.JsonBlock -> {
                                    Text(block.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
                                    block.sourceArtifactId?.let { artifactId ->
                                        Button(onClick = { onOpenArtifact(artifactId) }) { Text("Открыть артефакт") }
                                    }
                                }
                                is ChatContentBlock.UnsupportedArtifactBlock -> {
                                    Text(block.title ?: "Артефакт", style = MaterialTheme.typography.bodySmall)
                                    Button(onClick = { onOpenArtifact(block.artifactId) }) { Text("Открыть") }
                                }
                            }
                        }

                        msg.toolProgress.takeLast(8).forEach {
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        msg.error?.let {
                            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
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
