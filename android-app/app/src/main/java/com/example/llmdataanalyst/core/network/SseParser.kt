package com.example.llmdataanalyst.core.network

import com.example.llmdataanalyst.core.model.ChatStreamEvent
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

class SseParser(
    private val json: Json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        explicitNulls = false
    }
) {
    private var currentEvent: String = "message"
    private val dataLines = mutableListOf<String>()

    fun consumeLine(line: String): ChatStreamEvent? {
        if (line.startsWith(":")) return null
        if (line.isBlank()) {
            if (dataLines.isEmpty()) {
                currentEvent = "message"
                return null
            }
            val payload = dataLines.joinToString("\n")
            val event = parseFrame(currentEvent, payload)
            currentEvent = "message"
            dataLines.clear()
            return event
        }
        if (line.startsWith("event:")) {
            currentEvent = line.removePrefix("event:").trim()
            return null
        }
        if (line.startsWith("data:")) {
            dataLines.add(line.removePrefix("data:").trimStart())
        }
        return null
    }

    fun flush(): ChatStreamEvent? {
        if (dataLines.isEmpty()) return null
        val payload = dataLines.joinToString("\n")
        val event = parseFrame(currentEvent, payload)
        currentEvent = "message"
        dataLines.clear()
        return event
    }

    fun parseFrame(event: String, rawData: String): ChatStreamEvent {
        return try {
            val obj = json.parseToJsonElement(rawData).jsonObject
            when (event) {
                "message_start" -> ChatStreamEvent.MessageStart(
                    chatId = obj["chat_id"]?.jsonPrimitive?.contentOrNull,
                    role = obj["role"]?.jsonPrimitive?.contentOrNull
                )

                "message_delta" -> ChatStreamEvent.MessageDelta(
                    content = obj["content"]?.jsonPrimitive?.contentOrNull.orEmpty()
                )

                "tool_start" -> ChatStreamEvent.ToolStart(
                    name = obj["name"]?.jsonPrimitive?.contentOrNull,
                    title = obj["title"]?.jsonPrimitive?.contentOrNull
                )

                "tool_log" -> ChatStreamEvent.ToolLog(
                    content = obj["content"]?.jsonPrimitive?.contentOrNull.orEmpty()
                )

                "tool_end" -> ChatStreamEvent.ToolEnd(
                    name = obj["name"]?.jsonPrimitive?.contentOrNull,
                    status = obj["status"]?.jsonPrimitive?.contentOrNull
                )

                "artifact_created" -> ChatStreamEvent.ArtifactCreated(
                    artifactId = obj["artifact_id"]?.jsonPrimitive?.contentOrNull.orEmpty(),
                    title = obj["title"]?.jsonPrimitive?.contentOrNull,
                    mimeType = obj["mime_type"]?.jsonPrimitive?.contentOrNull,
                    previewUrl = obj["preview_url"]?.jsonPrimitive?.contentOrNull
                )

                "error" -> ChatStreamEvent.Error(
                    message = obj["message"]?.jsonPrimitive?.contentOrNull ?: "Ошибка стриминга"
                )

                "done" -> ChatStreamEvent.Done(
                    status = obj["status"]?.jsonPrimitive?.contentOrNull,
                    messageId = obj["message_id"]?.jsonPrimitive?.contentOrNull
                )

                else -> ChatStreamEvent.Unknown(event, rawData)
            }
        } catch (_: Exception) {
            ChatStreamEvent.Unknown(event, rawData)
        }
    }
}
