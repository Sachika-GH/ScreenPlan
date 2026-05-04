package com.screenplan.agent.ui.theme

import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF238636),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD2F4D2),
    secondary = Color(0xFF1F6FEB),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFDDEBFF),
    background = Color(0xFFF6F8FA),
    surface = Color.White,
    surfaceVariant = Color(0xFFF0F0F0),
    error = Color(0xFFDA3633),
    onBackground = Color(0xFF1B1F24),
    onSurface = Color(0xFF1B1F24),
    onSurfaceVariant = Color(0xFF656D76)
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF3FB950),
    onPrimary = Color.White,
    primaryContainer = Color(0xFF1A4D2E),
    secondary = Color(0xFF58A6FF),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFF0D419D),
    background = Color(0xFF0D1117),
    surface = Color(0xFF161B22),
    surfaceVariant = Color(0xFF21262D),
    error = Color(0xFFF85149),
    onBackground = Color(0xFFC9D1D9),
    onSurface = Color(0xFFC9D1D9),
    onSurfaceVariant = Color(0xFF8B949E)
)

@Composable
fun ScreenPlanTheme(
    darkTheme: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColors else LightColors

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography(),
        content = content
    )
}
