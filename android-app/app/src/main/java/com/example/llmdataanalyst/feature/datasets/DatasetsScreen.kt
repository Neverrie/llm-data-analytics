package com.example.llmdataanalyst.feature.datasets

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.example.llmdataanalyst.core.model.DatasetItem
import java.io.File

@Composable
fun DatasetsScreen(
    viewModel: DatasetsViewModel,
    onOpenDataset: (String) -> Unit,
    onUseInChat: (DatasetItem) -> Unit
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    LaunchedEffect(Unit) { viewModel.loadDatasets() }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri: Uri? ->
        if (uri != null) {
            val file = copyToCacheFile(context, uri)
            if (file != null) viewModel.uploadDataset(file)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Text("Датасеты", style = MaterialTheme.typography.headlineSmall)
        Button(onClick = {
            picker.launch(
                arrayOf(
                    "text/csv",
                    "application/vnd.ms-excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/octet-stream"
                )
            )
        }) {
            Text("Загрузить CSV/XLSX")
        }

        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(state.items, key = { it.id }) { ds ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        Text(ds.name)
                        Text(
                            "${ds.rowsCount ?: "-"} строк, ${ds.columnsCount ?: "-"} колонок",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Button(onClick = { onOpenDataset(ds.id) }) { Text("Открыть") }
                        Button(onClick = { onUseInChat(ds) }) { Text("Использовать в чате") }
                    }
                }
            }
        }
    }
}

private fun copyToCacheFile(context: Context, uri: Uri): File? {
    return runCatching {
        val name = context.contentResolver.query(uri, null, null, null, null)?.use { c ->
            val idx = c.getColumnIndex("_display_name")
            if (idx >= 0 && c.moveToFirst()) c.getString(idx) else "upload_file"
        } ?: "upload_file"

        val out = File(context.cacheDir, name)
        context.contentResolver.openInputStream(uri).use { input ->
            out.outputStream().use { output ->
                input?.copyTo(output)
            }
        }
        out
    }.getOrNull()
}
