package com.example.llmdataanalyst.feature.chat

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.example.llmdataanalyst.core.repository.ChatRepository

@Composable
fun ArtifactDetailScreen(
    artifactId: String,
    chatRepository: ChatRepository
) {
    var loading by remember { mutableStateOf(true) }
    var title by remember { mutableStateOf<String?>(null) }
    var mimeType by remember { mutableStateOf<String?>(null) }
    var previewRaw by remember { mutableStateOf<String?>(null) }
    var previewUrl by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(artifactId) {
        loading = true
        runCatching {
            val art = chatRepository.getArtifact(artifactId)
            title = art.title ?: art.filename
            mimeType = art.mimeType
            previewUrl = chatRepository.buildPreviewUrl(artifactId)
            if (!(mimeType.orEmpty().contains("image/"))) {
                previewRaw = chatRepository.getArtifactPreviewRaw(artifactId).second
            }
        }
        loading = false
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(title ?: "Артефакт", style = MaterialTheme.typography.titleLarge)
        Text(mimeType ?: "", style = MaterialTheme.typography.bodySmall)
        if (loading) {
            CircularProgressIndicator()
        } else if (mimeType.orEmpty().contains("image/") && !previewUrl.isNullOrBlank()) {
            AsyncImage(
                model = previewUrl,
                contentDescription = title,
                modifier = Modifier.fillMaxWidth()
            )
        } else {
            Text(previewRaw ?: "Нет предпросмотра")
        }
    }
}

