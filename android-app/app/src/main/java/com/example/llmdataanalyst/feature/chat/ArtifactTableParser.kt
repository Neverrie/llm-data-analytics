package com.example.llmdataanalyst.feature.chat

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

object ArtifactTableParser {
    private const val LIMIT_ROWS = 20

    data class ParseResult(
        val table: ChatContentBlock.TableBlock? = null,
        val jsonFallback: ChatContentBlock.JsonBlock? = null
    )

    fun parse(raw: String, title: String?, artifactId: String?): ParseResult {
        val json = Json { ignoreUnknownKeys = true; isLenient = true; prettyPrint = true }
        val element = try {
            json.parseToJsonElement(raw)
        } catch (_: Exception) {
            return ParseResult(jsonFallback = ChatContentBlock.JsonBlock(raw.take(4000), artifactId))
        }
        parseElement(element, title, artifactId)?.let { return ParseResult(table = it) }
        return ParseResult(jsonFallback = ChatContentBlock.JsonBlock(json.encodeToString(JsonElement.serializer(), element), artifactId))
    }

    private fun parseElement(element: JsonElement, title: String?, artifactId: String?): ChatContentBlock.TableBlock? {
        return when (element) {
            is JsonObject -> parseObject(element, title, artifactId)
            is JsonArray -> parseArray(element, title, artifactId)
            else -> null
        }
    }

    private fun parseObject(obj: JsonObject, title: String?, artifactId: String?): ChatContentBlock.TableBlock? {
        val columnsEl = obj["columns"] as? JsonArray
        val rowsEl = obj["rows"] as? JsonArray
        if (columnsEl != null && rowsEl != null) {
            val columns = columnsEl.map { it.asCell() }
            if (columns.isEmpty()) return null
            val rows = rowsEl.mapNotNull { row ->
                when (row) {
                    is JsonArray -> alignRow(row.map { it.asCell() }, columns.size)
                    is JsonObject -> columns.map { c -> row[c]?.asCell() ?: "—" }
                    else -> null
                }
            }
            val limited = rows.take(LIMIT_ROWS)
            return ChatContentBlock.TableBlock(title, columns, limited, artifactId, rows.size > LIMIT_ROWS)
        }

        val kvRows = obj.entries.map { listOf(it.key, it.value.asCell()) }
        if (kvRows.isNotEmpty()) {
            val limited = kvRows.take(LIMIT_ROWS)
            return ChatContentBlock.TableBlock(
                title = title,
                columns = listOf("Параметр", "Значение"),
                rows = limited,
                sourceArtifactId = artifactId,
                truncated = kvRows.size > LIMIT_ROWS
            )
        }
        return null
    }

    private fun parseArray(array: JsonArray, title: String?, artifactId: String?): ChatContentBlock.TableBlock? {
        if (array.isEmpty()) return null
        val first = array.first()
        return when (first) {
            is JsonObject -> {
                val columns = first.keys.toList()
                val rows = array.mapNotNull { item ->
                    (item as? JsonObject)?.let { obj -> columns.map { c -> obj[c]?.asCell() ?: "—" } }
                }
                ChatContentBlock.TableBlock(title, columns, rows.take(LIMIT_ROWS), artifactId, rows.size > LIMIT_ROWS)
            }
            is JsonArray -> {
                val maxCols = array.mapNotNull { (it as? JsonArray)?.size }.maxOrNull() ?: 0
                if (maxCols == 0) return null
                val columns = (1..maxCols).map { "Column $it" }
                val rows = array.mapNotNull { row ->
                    (row as? JsonArray)?.let { alignRow(it.map { cell -> cell.asCell() }, maxCols) }
                }
                ChatContentBlock.TableBlock(title, columns, rows.take(LIMIT_ROWS), artifactId, rows.size > LIMIT_ROWS)
            }
            else -> null
        }
    }

    private fun alignRow(row: List<String>, size: Int): List<String> {
        if (row.size == size) return row
        if (row.size > size) return row.take(size)
        return row + List(size - row.size) { "—" }
    }

    private fun JsonElement.asCell(): String {
        return when (this) {
            is JsonPrimitive -> {
                this.contentOrNull
                    ?: this.intOrNull?.toString()
                    ?: this.doubleOrNull?.toString()
                    ?: this.booleanOrNull?.toString()
                    ?: "—"
            }
            else -> toString()
        }.ifBlank { "—" }
    }
}
