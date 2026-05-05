package com.example.llmdataanalyst.feature.chat

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import coil.request.ImageRequest
import okhttp3.Headers
import com.example.llmdataanalyst.R

@Composable
fun ChatScreen(
    viewModel: ChatViewModel,
    onOpenDatasets: () -> Unit,
    onOpenArtifact: (String) -> Unit
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current
    var datasetMenuOpen by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        viewModel.events.collect { msg -> snackbarHostState.showSnackbar(msg) }
    }

    Column(modifier = Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SnackbarHost(hostState = snackbarHostState)
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    if (!state.selectedDatasetId.isNullOrBlank()) "Режим: агент анализа данных" else "Режим: обычный чат",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary
                )
                if (!state.selectedDatasetName.isNullOrBlank() || !state.selectedDatasetId.isNullOrBlank()) {
                    Text("Выбран датасет", style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
                    Text(
                        state.selectedDatasetName
                            ?: "Датасет выбран: ${state.selectedDatasetId}",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = onOpenDatasets) { Text("Сменить") }
                        TextButton(onClick = viewModel::clearSelectedDataset) { Text("Убрать") }
                        Button(onClick = { datasetMenuOpen = true }) { Text("Быстрый выбор") }
                    }
                    DropdownMenu(expanded = datasetMenuOpen, onDismissRequest = { datasetMenuOpen = false }) {
                        state.datasets.forEach { ds ->
                            DropdownMenuItem(
                                text = { Text(ds.name) },
                                onClick = {
                                    viewModel.selectDataset(ds.id, ds.name)
                                    datasetMenuOpen = false
                                }
                            )
                        }
                    }
                } else {
                    Text("Датасет не выбран", style = MaterialTheme.typography.labelLarge)
                    Text(
                        "Можно общаться без датасета или выбрать CSV/XLSX для анализа",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Button(onClick = onOpenDatasets) { Text("Выбрать датасет") }
                }
            }
        }
        LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.messages, key = { it.id }) { msg ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            if (msg.role == "user") stringResource(R.string.chat_you) else stringResource(R.string.chat_assistant),
                            style = MaterialTheme.typography.labelMedium
                        )
                        val blocks = if (msg.blocks.isEmpty()) listOf(ChatContentBlock.TextBlock(msg.content)) else msg.blocks
                        blocks.forEach { block ->
                            when (block) {
                                is ChatContentBlock.TextBlock -> {
                                    if (block.text.isNotBlank()) Text(block.text)
                                }
                                is ChatContentBlock.MarkdownBlock -> {
                                    if (block.text.contains("```")) {
                                        val hs = rememberScrollState()
                                        Card(modifier = Modifier.fillMaxWidth()) {
                                            Text(
                                                block.text,
                                                modifier = Modifier
                                                    .padding(8.dp)
                                                    .horizontalScroll(hs),
                                                fontFamily = FontFamily.Monospace,
                                                style = MaterialTheme.typography.bodySmall
                                            )
                                        }
                                    } else {
                                        Text(block.text)
                                    }
                                }
                                is ChatContentBlock.ImageArtifactBlock -> {
                                    Text(block.title ?: stringResource(R.string.chat_image), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
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
                                    Button(onClick = { onOpenArtifact(block.artifactId) }) { Text(stringResource(R.string.chat_open_artifact)) }
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
                                                    Text(text = cell.ifBlank { stringResource(R.string.chat_dash) }, modifier = Modifier.padding(6.dp))
                                                }
                                            }
                                        }
                                    }
                                    if (block.truncated) {
                                        Text(stringResource(R.string.chat_first_rows), style = MaterialTheme.typography.bodySmall)
                                    }
                                    block.sourceArtifactId?.let { artifactId ->
                                        Button(onClick = { onOpenArtifact(artifactId) }) { Text(stringResource(R.string.chat_open_artifact)) }
                                    }
                                }
                                is ChatContentBlock.JsonBlock -> {
                                    Text(block.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
                                    block.sourceArtifactId?.let { artifactId ->
                                        Button(onClick = { onOpenArtifact(artifactId) }) { Text(stringResource(R.string.chat_open_artifact)) }
                                    }
                                }
                                is ChatContentBlock.UnsupportedArtifactBlock -> {
                                    Text(block.title ?: stringResource(R.string.chat_artifact), style = MaterialTheme.typography.bodySmall)
                                    Button(onClick = { onOpenArtifact(block.artifactId) }) { Text(stringResource(R.string.chat_open)) }
                                }
                            }
                        }

                        msg.toolProgress.takeLast(8).forEach {
                            val isActive = it.startsWith("▶")
                            val isDone = it.startsWith("✓")
                            val isError = it.contains("error", ignoreCase = true) || it.contains("ошиб", ignoreCase = true)
                            val prefix = when {
                                isActive -> "⏳ "
                                isDone -> "✅ "
                                isError -> "⚠ "
                                else -> "• "
                            }
                            Text("$prefix$it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
            label = { Text(stringResource(R.string.chat_message)) },
            enabled = !state.loading
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = viewModel::sendMessage, enabled = !state.loading) { Text(stringResource(R.string.chat_send)) }
            Button(onClick = viewModel::stopStreaming, enabled = state.loading) { Text(stringResource(R.string.chat_stop)) }
            if (state.loading) CircularProgressIndicator(modifier = Modifier.padding(start = 8.dp))
        }
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Button(onClick = { viewModel.sendPreset("Сделай обзор датасета: строки, колонки, типы данных, пропуски и 3 главных наблюдения.") }, enabled = !state.loading) { Text("Обзор") }
            Button(onClick = { viewModel.sendPreset("Построй графики распределения для числовых признаков и сохрани их как артефакты.") }, enabled = !state.loading) { Text("Графики") }
            Button(onClick = { viewModel.sendPreset("Построй простую регрессионную модель на подходящей целевой переменной, выполни её на backend и покажи метрики.") }, enabled = !state.loading) { Text("Регрессия") }
        }
    }
}
