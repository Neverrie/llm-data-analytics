package com.example.llmdataanalyst.feature.chat

import android.content.Intent
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import com.example.llmdataanalyst.core.model.ArtifactItem
import com.example.llmdataanalyst.core.repository.ArtifactRepository
import com.example.llmdataanalyst.core.util.AppResult
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun ArtifactDetailScreen(
    artifactId: String,
    artifactRepository: ArtifactRepository
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var artifact by remember { mutableStateOf<ArtifactItem?>(null) }
    var previewBlock by remember { mutableStateOf<ChatContentBlock?>(null) }
    var previewRaw by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(artifactId) {
        loading = true
        error = null
        previewRaw = null
        previewBlock = null

        when (val meta = artifactRepository.getArtifact(artifactId)) {
            is AppResult.Success -> artifact = meta.data
            is AppResult.Error -> error = meta.message
        }

        val current = artifact
        if (current != null) {
            if (isImage(current)) {
                val previewUrl = artifactRepository.buildPreviewUrl(artifactId)
                previewBlock = ChatContentBlock.ImageArtifactBlock(
                    artifactId = artifactId,
                    title = current.title ?: current.filename,
                    mimeType = current.mimeType,
                    previewUrl = previewUrl
                )
            } else {
                when (val preview = artifactRepository.getPreview(artifactId)) {
                    is AppResult.Success -> {
                        val contentType = preview.data.headers()["Content-Type"].orEmpty().lowercase()
                        val raw = preview.data.body()?.string().orEmpty()
                        previewRaw = raw
                        if (raw.isNotBlank() && (contentType.contains("json") || raw.trim().startsWith("{") || raw.trim().startsWith("["))) {
                            val parsed = ArtifactTableParser.parse(raw, current.title ?: current.filename, artifactId)
                            previewBlock = parsed.table ?: parsed.jsonFallback
                        }
                    }
                    is AppResult.Error -> error = error ?: preview.message
                }
            }
        }
        loading = false
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Text(artifact?.title ?: artifact?.filename ?: "Артефакт", style = MaterialTheme.typography.titleLarge)
        Text(artifact?.mimeType ?: artifact?.kind ?: "—", style = MaterialTheme.typography.bodySmall)

        if (loading) {
            CircularProgressIndicator()
        }

        error?.let {
            Card(modifier = Modifier.fillMaxWidth()) {
                Text(it, modifier = Modifier.padding(12.dp), color = MaterialTheme.colorScheme.error)
            }
        }

        when (val block = previewBlock) {
            is ChatContentBlock.ImageArtifactBlock -> {
                AsyncImage(
                    model = block.previewUrl,
                    contentDescription = block.title,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(max = 420.dp)
                )
            }
            is ChatContentBlock.TableBlock -> {
                val hs = rememberScrollState()
                Column(modifier = Modifier.fillMaxWidth().horizontalScroll(hs)) {
                    Row {
                        block.columns.forEach { col ->
                            Text(col, modifier = Modifier.padding(6.dp), fontWeight = FontWeight.Bold)
                        }
                    }
                    block.rows.forEach { row ->
                        Row {
                            row.forEach { cell ->
                                Text(cell.ifBlank { "—" }, modifier = Modifier.padding(6.dp))
                            }
                        }
                    }
                }
            }
            is ChatContentBlock.JsonBlock -> {
                Text(block.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
            }
            else -> {
                previewRaw?.let {
                    if (it.startsWith("#") || it.contains("```")) {
                        Text(it)
                    } else if (it.isNotBlank()) {
                        Text(it.take(6000), fontFamily = FontFamily.Monospace)
                    } else {
                        Text("Предпросмотр недоступен")
                    }
                }
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                scope.launch {
                    val downloaded = runCatching {
                        when (val response = artifactRepository.download(artifactId)) {
                            is AppResult.Success -> {
                                val body = response.data.body() ?: return@runCatching null
                                val name = artifact?.filename ?: artifact?.title ?: "artifact_$artifactId"
                                val ext = guessExtension(artifact?.mimeType)
                                val file = File(context.cacheDir, if (name.contains(".")) name else "$name$ext")
                                file.outputStream().use { out -> body.byteStream().copyTo(out) }
                                file
                            }
                            is AppResult.Error -> null
                        }
                    }.getOrNull()

                    if (downloaded != null) {
                        val uri = FileProvider.getUriForFile(
                            context,
                            "${context.packageName}.fileprovider",
                            downloaded
                        )
                        val openIntent = Intent(Intent.ACTION_VIEW).apply {
                            setDataAndType(uri, artifact?.mimeType ?: "*/*")
                            flags = Intent.FLAG_GRANT_READ_URI_PERMISSION
                        }
                        val chooser = Intent.createChooser(openIntent, "Открыть артефакт")
                        context.startActivity(chooser)
                    }
                }
            }) {
                Text("Скачать/Открыть")
            }
        }
    }
}

private fun isImage(item: ArtifactItem): Boolean {
    val mime = item.mimeType.orEmpty().lowercase()
    val title = (item.title ?: item.filename).orEmpty().lowercase()
    return mime.contains("image/png") || mime.contains("image/jpeg") || mime.contains("image/webp") ||
        title.endsWith(".png") || title.endsWith(".jpg") || title.endsWith(".jpeg") || title.endsWith(".webp")
}

private fun guessExtension(mimeType: String?): String {
    val mime = mimeType.orEmpty().lowercase()
    return when {
        mime.contains("png") -> ".png"
        mime.contains("jpeg") || mime.contains("jpg") -> ".jpg"
        mime.contains("webp") -> ".webp"
        mime.contains("json") -> ".json"
        mime.contains("markdown") || mime.contains("md") -> ".md"
        else -> ".bin"
    }
}
