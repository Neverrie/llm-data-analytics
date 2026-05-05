package com.example.llmdataanalyst.feature.artifacts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.example.llmdataanalyst.core.model.ArtifactItem

@Composable
fun ArtifactsScreen(
    viewModel: ArtifactsViewModel,
    onOpenArtifact: (String) -> Unit
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { viewModel.load() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Button(onClick = viewModel::load, modifier = Modifier.fillMaxWidth()) {
            Text("Обновить")
        }

        when {
            state.loading -> CircularProgressIndicator()
            state.error != null -> {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(state.error ?: "Ошибка", color = MaterialTheme.colorScheme.error)
                        Button(onClick = viewModel::load) { Text("Повторить") }
                    }
                }
            }
            state.items.isEmpty() -> {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Артефактов пока нет")
                        Text("Они появятся после анализа данных или построения графиков")
                    }
                }
            }
            else -> {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(state.items, key = { it.id }) { item ->
                        ArtifactCard(item = item, onOpen = { onOpenArtifact(item.id) })
                    }
                }
            }
        }
    }
}

@Composable
private fun ArtifactCard(
    item: ArtifactItem,
    onOpen: () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(item.title ?: item.filename ?: item.id, style = MaterialTheme.typography.titleMedium)
            Text(item.mimeType ?: item.kind ?: "—", style = MaterialTheme.typography.bodySmall)
            item.createdAt?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            item.path?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
            if (isImage(item)) {
                AsyncImage(
                    model = item.previewUrl ?: item.path ?: item.filename,
                    contentDescription = item.title,
                    modifier = Modifier.fillMaxWidth().height(140.dp)
                )
            }
            Button(onClick = onOpen) { Text("Открыть") }
        }
    }
}

private fun isImage(item: ArtifactItem): Boolean {
    val mime = item.mimeType.orEmpty().lowercase()
    val title = (item.title ?: item.filename).orEmpty().lowercase()
    return mime.contains("image/png") || mime.contains("image/jpeg") || mime.contains("image/webp") ||
        title.endsWith(".png") || title.endsWith(".jpg") || title.endsWith(".jpeg") || title.endsWith(".webp")
}
