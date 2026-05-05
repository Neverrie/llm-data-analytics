package com.example.llmdataanalyst.core.network

import com.example.llmdataanalyst.core.model.ChatStreamEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SseParserTest {
    private val parser = SseParser()

    @Test
    fun parsesMessageDeltaWithCyrillic() {
        val event = parser.parseFrame("message_delta", """{"content":"привет мир"}""")
        assertTrue(event is ChatStreamEvent.MessageDelta)
        assertEquals("привет мир", (event as ChatStreamEvent.MessageDelta).content)
    }

    @Test
    fun parsesMultilineData() {
        val local = SseParser()
        assertEquals(null, local.consumeLine("event: tool_log"))
        assertEquals(null, local.consumeLine("data: {\"content\":\"line1"))
        assertEquals(null, local.consumeLine("data: line2\"}"))
        val event = local.consumeLine("")
        assertTrue(event is ChatStreamEvent.ToolLog)
    }

    @Test
    fun unknownEventDoesNotCrash() {
        val event = parser.parseFrame("custom_event", """{"foo":"bar"}""")
        assertTrue(event is ChatStreamEvent.Unknown)
    }

    @Test
    fun parsesDoneEvent() {
        val event = parser.parseFrame("done", """{"status":"ok","message_id":"456"}""")
        assertTrue(event is ChatStreamEvent.Done)
        assertEquals("456", (event as ChatStreamEvent.Done).messageId)
    }

    @Test
    fun malformedJsonReturnsUnknown() {
        val event = parser.parseFrame("message_delta", """{"content":"abc"""")
        assertTrue(event is ChatStreamEvent.Unknown)
    }

    @Test
    fun eventWithoutDataIsIgnored() {
        val local = SseParser()
        assertEquals(null, local.consumeLine("event: message_delta"))
        assertEquals(null, local.consumeLine(""))
    }

    @Test
    fun parsesMultipleEventsSequentially() {
        val local = SseParser()
        val results = mutableListOf<ChatStreamEvent>()
        val lines = listOf(
            "event: message_delta",
            "data: {\"content\":\"a\"}",
            "",
            "event: done",
            "data: {\"status\":\"ok\",\"message_id\":\"m1\"}",
            ""
        )
        lines.forEach { line -> local.consumeLine(line)?.let(results::add) }
        assertEquals(2, results.size)
        assertTrue(results[0] is ChatStreamEvent.MessageDelta)
        assertTrue(results[1] is ChatStreamEvent.Done)
    }
}
