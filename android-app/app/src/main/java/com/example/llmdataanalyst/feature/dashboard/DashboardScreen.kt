package com.example.llmdataanalyst.feature.dashboard

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.model.ChatItem
import com.example.llmdataanalyst.core.model.DatasetItem

@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel,
    onOpenChat: () -> Unit,
    onOpenSettings: () -> Unit,
    onOpenDatasets: () -> Unit,
    onOpenArtifacts: () -> Unit,
    onOpenLab2: () -> Unit,
    onOpenDatasetDetail: (String) -> Unit,
    onUseDatasetInChat: (DatasetItem) -> Unit,
    onOpenArtifactDetail: (String) -> Unit,
    onOpenChatDetail: (String) -> Unit
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { viewModel.load() }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(shape = RoundedCornerShape(24.dp), modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("LLM Data Analyst", style = MaterialTheme.typography.headlineSmall)
                    Text("Анализируйте CSV/XLSX, стройте графики и работайте с LLM-агентом")
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Быстрые действия", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onOpenChat) { Text("Новый чат") }
                        Button(onClick = onOpenDatasets) { Text("Загрузить датасет") }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onOpenArtifacts) { Text("Артефакты") }
                        Button(onClick = onOpenLab2) { Text("Lab 2 Pipeline") }
                    }
                }
            }
        }

        item {
            if (state.loading) {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        CircularProgressIndicator()
                        Text("Загружаю данные workspace...")
                    }
                }
            }
            if (state.error != null) {
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Backend недоступен", color = MaterialTheme.colorScheme.error)
                        Text("Проверьте адрес сервера в настройках")
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = onOpenSettings) { Text("Открыть настройки") }
                            Button(onClick = viewModel::load) { Text("Повторить") }
                        }
                    }
                }
            }
        }

        item {
            Card(modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.padding(16.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text("Чаты: ${state.chatsCount}")
                    Text("Датасеты: ${state.datasetsCount}")
                    Text("Артефакты: ${state.artifactsCount}")
                }
            }
        }

        item { Text("Последние чаты", style = MaterialTheme.typography.titleMedium) }
        if (state.chats.isEmpty()) item { Text("Пока нет чатов") }
        items(state.chats.take(5), key = { it.id }) { chat ->
            ChatRow(chat = chat, onOpen = { onOpenChatDetail(chat.id) })
        }

        item { Text("Последние датасеты", style = MaterialTheme.typography.titleMedium) }
        if (state.datasets.isEmpty()) item { Text("Пока нет датасетов") }
        items(state.datasets.take(5), key = { it.id }) { ds ->
            DatasetRow(
                dataset = ds,
                onOpen = { onOpenDatasetDetail(ds.id) },
                onUse = { onUseDatasetInChat(ds) }
            )
        }

        item { Text("Последние артефакты", style = MaterialTheme.typography.titleMedium) }
        if (state.artifacts.isEmpty()) item { Text("Пока нет артефактов") }
        items(state.artifacts.take(5), key = { it.id }) { art ->
            ArtifactRow(artifact = art, onOpen = { onOpenArtifactDetail(art.id) })
        }
    }
}

@Composable
private fun ChatRow(chat: ChatItem, onOpen: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(chat.title)
            Text(chat.kind, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun DatasetRow(dataset: DatasetItem, onOpen: () -> Unit, onUse: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(dataset.name)
            Text("${dataset.rowsCount ?: "-"} строк", style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onOpen) { Text("Открыть") }
                Button(onClick = onUse) { Text("Использовать в чате") }
            }
        }
    }
}

@Composable
private fun ArtifactRow(artifact: ArtifactItem, onOpen: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(artifact.title ?: artifact.filename ?: artifact.id)
            Text(artifact.mimeType ?: artifact.kind ?: "—", style = MaterialTheme.typography.bodySmall)
        }
    }
}
