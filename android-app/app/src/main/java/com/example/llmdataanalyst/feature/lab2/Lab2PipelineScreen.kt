package com.example.llmdataanalyst.feature.lab2

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.llmdataanalyst.core.repository.Lab2Repository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun Lab2PipelineScreen(
    viewModel: Lab2ViewModel,
    lab2Repository: Lab2Repository
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    LaunchedEffect(Unit) { viewModel.load() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Lab 2 Pipeline", style = MaterialTheme.typography.titleLarge)
                Text("Классификация отзывов через backend API")
            }
        }

        if (state.loading) CircularProgressIndicator()

        state.error?.let {
            Card(modifier = Modifier.fillMaxWidth()) {
                Text(it, modifier = Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error)
            }
        }

        state.status?.let {
            JsonCard("Статус", lab2Repository.pretty(it))
        }

        state.sampleData?.let {
            JsonCard("Sample data", lab2Repository.pretty(it))
        }

        RowButtons(
            onRun = viewModel::runPipeline,
            onRefresh = viewModel::load,
            onDownload = {
                scope.launch {
                    when (val dl = lab2Repository.download()) {
                        is AppResult.Success -> {
                            val body = dl.data.body() ?: return@launch
                            val file = File(context.cacheDir, "lab2_result.zip")
                            file.outputStream().use { out -> body.byteStream().copyTo(out) }
                            val uri = FileProvider.getUriForFile(
                                context,
                                "${context.packageName}.fileprovider",
                                file
                            )
                            val intent = Intent(Intent.ACTION_VIEW).apply {
                                setDataAndType(uri, "application/zip")
                                flags = Intent.FLAG_GRANT_READ_URI_PERMISSION
                            }
                            context.startActivity(Intent.createChooser(intent, "Открыть результат"))
                        }
                        is AppResult.Error -> Unit
                    }
                }
            },
            running = state.running
        )

        state.info?.let { Text(it, color = MaterialTheme.colorScheme.primary) }

        state.result?.let {
            JsonCard("Результат", lab2Repository.pretty(it))
        }
    }
}

@Composable
private fun RowButtons(
    onRun: () -> Unit,
    onRefresh: () -> Unit,
    onDownload: () -> Unit,
    running: Boolean
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(onClick = onRun, enabled = !running, modifier = Modifier.fillMaxWidth()) { Text("Запустить классификацию") }
        Button(onClick = onRefresh, modifier = Modifier.fillMaxWidth()) { Text("Обновить результат") }
        Button(onClick = onDownload, modifier = Modifier.fillMaxWidth()) { Text("Скачать результат") }
    }
}

@Composable
private fun JsonCard(title: String, json: String) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(json, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
        }
    }
}
