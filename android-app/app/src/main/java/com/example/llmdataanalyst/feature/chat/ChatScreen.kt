package com.example.llmdataanalyst.feature.chat

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import coil.request.ImageRequest
import okhttp3.Headers
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForward
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import com.example.llmdataanalyst.R
import com.example.llmdataanalyst.core.repository.ChatExecutionMode

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
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { datasetMenuOpen = true }) {
                Text(
                    text = (state.selectedDatasetName ?: "Датасет не выбран"),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(" ▼", fontWeight = FontWeight.Bold)
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
                DropdownMenuItem(
                    text = { Text("Добавить датасет") },
                    onClick = {
                        datasetMenuOpen = false
                        onOpenDatasets()
                    }
                )
            }
        }
        LazyColumn(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.messages, key = { it.id }) { msg ->
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = if (msg.role == "user") MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface
                    )
                ) {
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
                                        val vs = rememberScrollState()
                                        Card(modifier = Modifier.fillMaxWidth()) {
                                            Text(
                                                block.text,
                                                modifier = Modifier
                                                    .padding(8.dp)
                                                    .heightIn(max = 180.dp)
                                                    .horizontalScroll(hs)
                                                    .verticalScroll(vs),
                                                fontFamily = FontFamily.Monospace,
                                                style = MaterialTheme.typography.bodySmall
                                            )
                                        }
                                    } else {
                                        Text(viewModel.renderMarkdownLikeText(block.text))
                                    }
                                }
                                is ChatContentBlock.WarningBlock -> {
                                    var open by remember { mutableStateOf(false) }
                                    Text(
                                        text = block.errorType?.let { "Предупреждение ($it)" } ?: "Предупреждение",
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.SemiBold
                                    )
                                    Text(block.text, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                                    if (!block.details.isNullOrBlank()) {
                                        Text(
                                            text = if (open) "Скрыть детали" else "Показать детали",
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.primary,
                                            modifier = Modifier.clickable { open = !open }
                                        )
                                        if (open) {
                                            val hs = rememberScrollState()
                                            val vs = rememberScrollState()
                                            Card(modifier = Modifier.fillMaxWidth()) {
                                                Text(
                                                    text = block.details,
                                                    modifier = Modifier
                                                        .padding(8.dp)
                                                        .heightIn(max = 180.dp)
                                                        .horizontalScroll(hs)
                                                        .verticalScroll(vs),
                                                    fontFamily = FontFamily.Monospace,
                                                    style = MaterialTheme.typography.bodySmall
                                                )
                                            }
                                        }
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
                                        modifier = Modifier.fillMaxWidth().height(160.dp)
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
            enabled = !state.loading,
            trailingIcon = {
                if (state.loading) {
                    IconButton(onClick = viewModel::stopStreaming) {
                        Icon(Icons.Default.Stop, contentDescription = stringResource(R.string.chat_stop))
                    }
                } else {
                    IconButton(onClick = viewModel::sendMessage, enabled = state.input.isNotBlank()) {
                        Icon(Icons.Default.ArrowForward, contentDescription = "Отправить")
                    }
                }
            }
        )
        if (state.loading) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(modifier = Modifier.padding(start = 8.dp))
            }
        }
    }
}
