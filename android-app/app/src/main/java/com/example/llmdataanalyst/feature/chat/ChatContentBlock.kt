package com.example.llmdataanalyst.feature.chat

sealed interface ChatContentBlock {
    data class TextBlock(val text: String) : ChatContentBlock
    data class ImageArtifactBlock(
        val artifactId: String,
        val title: String?,
        val mimeType: String?,
        val previewUrl: String
    ) : ChatContentBlock

    data class TableBlock(
        val title: String? = null,
        val columns: List<String>,
        val rows: List<List<String>>,
        val sourceArtifactId: String? = null,
        val truncated: Boolean = false
    ) : ChatContentBlock

    data class MarkdownBlock(val text: String) : ChatContentBlock
    data class JsonBlock(val text: String, val sourceArtifactId: String? = null) : ChatContentBlock
    data class UnsupportedArtifactBlock(
        val artifactId: String,
        val title: String?,
        val mimeType: String?
    ) : ChatContentBlock
}

