package com.example.llmdataanalyst.feature.chat

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MarkdownTableParserTest {
    @Test
    fun parsesMarkdownTable() {
        val text = """
            Сводка:
            | Column | Mean |
            |---|---|
            | Sales | 123 |
            | Profit | 45 |
        """.trimIndent()

        val blocks = MarkdownTableParser.parseToBlocks(text)
        assertTrue(blocks.any { it is ChatContentBlock.TableBlock })
        val table = blocks.first { it is ChatContentBlock.TableBlock } as ChatContentBlock.TableBlock
        assertEquals(listOf("Column", "Mean"), table.columns)
        assertEquals(2, table.rows.size)
    }
}

