package com.example.llmdataanalyst.core.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF5E7A7A),
    onPrimary = Color(0xFFFFFFFF),
    secondary = Color(0xFF7A8A8A),
    background = Color(0xFFF1F0EC),
    surface = Color(0xFFFCFCFA),
    onSurface = Color(0xFF1E2324)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF8CB1B1),
    background = Color(0xFF121515),
    surface = Color(0xFF1C2222)
)

@Composable
fun LlmDataAnalystTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content
    )
}
