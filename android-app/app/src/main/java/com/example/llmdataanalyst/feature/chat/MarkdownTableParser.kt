package com.example.llmdataanalyst.feature.chat

object MarkdownTableParser {
    private val separatorRegex = Regex("""^\s*\|?(\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$""")

    fun parseToBlocks(text: String): List<ChatContentBlock> {
        if (!text.contains("|")) return listOf(ChatContentBlock.TextBlock(text))
        val lines = text.lines()
        val blocks = mutableListOf<ChatContentBlock>()
        val buffer = mutableListOf<String>()
        var i = 0

        fun flushText() {
            val t = buffer.joinToString("\n").trim()
            if (t.isNotBlank()) blocks += ChatContentBlock.TextBlock(t)
            buffer.clear()
        }

        while (i < lines.size) {
            val line = lines[i]
            val next = lines.getOrNull(i + 1)
            if (line.contains("|") && next != null && separatorRegex.matches(next)) {
                flushText()
                val header = splitRow(line)
                if (header.isEmpty()) {
                    buffer += line
                    i += 1
                    continue
                }
                i += 2
                val rows = mutableListOf<List<String>>()
                while (i < lines.size && lines[i].contains("|")) {
                    val row = splitRow(lines[i])
                    if (row.isNotEmpty()) rows += alignRow(row, header.size)
                    i += 1
                }
                if (rows.isNotEmpty()) {
                    blocks += ChatContentBlock.TableBlock(
                        title = null,
                        columns = header,
                        rows = rows
                    )
                }
                continue
            }
            buffer += line
            i += 1
        }
        flushText()
        return if (blocks.isEmpty()) listOf(ChatContentBlock.TextBlock(text)) else blocks
    }

    private fun splitRow(row: String): List<String> {
        return row.trim().trim('|').split('|').map { it.trim() }.filter { it.isNotEmpty() }
    }

    private fun alignRow(row: List<String>, size: Int): List<String> {
        if (row.size == size) return row
        if (row.size > size) return row.take(size)
        return row + List(size - row.size) { "—" }
    }
}

