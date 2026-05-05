package com.example.llmdataanalyst.feature.datasets

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

@Composable
fun DatasetDetailScreen(
    datasetId: String,
    viewModel: DatasetsViewModel
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var tab by remember { mutableStateOf(0) }

    LaunchedEffect(datasetId) { viewModel.loadDetail(datasetId) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        TabRow(selectedTabIndex = tab) {
            Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Preview") })
            Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Profile") })
            Tab(selected = tab == 2, onClick = { tab = 2 }, text = { Text("Columns") })
        }

        when (tab) {
            0 -> PreviewTable(state.preview?.columns.orEmpty(), state.preview?.rows.orEmpty())
            1 -> {
                Text("Строк: ${state.profile?.rowsCount ?: "-"}")
                Text("Колонок: ${state.profile?.columnsCount ?: "-"}")
            }
            2 -> {
                state.profile?.columns?.forEach { col ->
                    Text(
                        "${col.name}: ${col.dtype} (missing: ${col.missingCount ?: 0}, unique: ${col.uniqueCount ?: 0})"
                    )
                }
            }
        }
    }
}

@Composable
private fun PreviewTable(columns: List<String>, rows: List<JsonElement>) {
    if (columns.isEmpty() && rows.isEmpty()) {
        Text("Нет данных для preview", style = MaterialTheme.typography.bodyMedium)
        return
    }

    val horizontal = rememberScrollState()
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(horizontal)
                .padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Row {
                columns.forEach { col ->
                    Text(
                        text = col,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp),
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            rows.take(30).forEach { row ->
                Row {
                    toRowCells(row, columns).forEach { cell ->
                        Text(
                            text = cell,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 6.dp)
                        )
                    }
                }
            }
        }
    }

    if (rows.size > 30) {
        Text("Показаны первые 30 строк", style = MaterialTheme.typography.bodySmall)
    }
}

private fun toRowCells(row: JsonElement, columns: List<String>): List<String> {
    val expected = columns.size.coerceAtLeast(1)
    return when (row) {
        is JsonArray -> row.map { toCellString(it) }.pad(expected)
        is JsonObject -> {
            if (columns.isNotEmpty()) {
                columns.map { columnName -> toCellString(row[columnName]) }
            } else {
                row.values.map { toCellString(it) }.pad(expected)
            }
        }
        else -> listOf(toCellString(row)).pad(expected)
    }
}

private fun toCellString(el: JsonElement?): String {
    if (el == null) return "—"
    val value = when (el) {
        is JsonPrimitive -> el.contentOrNull ?: "—"
        else -> el.toString()
    }
    return value.ifBlank { "—" }
}

private fun List<String>.pad(expected: Int): List<String> {
    if (size >= expected) return this.take(expected)
    return this + List(expected - size) { "—" }
}
