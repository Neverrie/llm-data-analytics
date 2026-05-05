package com.example.llmdataanalyst

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.LaunchedEffect
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.rememberNavController
import com.example.llmdataanalyst.core.ui.theme.LlmDataAnalystTheme
import com.example.llmdataanalyst.navigation.AppNavHost
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private lateinit var appContainer: AppContainer

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        appContainer = AppContainer(applicationContext)

        lifecycleScope.launch {
            appContainer.authRepository.tokenFlow.collectLatest {
                appContainer.authStateHolder.updateToken(it)
            }
        }
        lifecycleScope.launch {
            appContainer.unauthorizedEventBus.events.collectLatest {
                appContainer.authRepository.logout()
            }
        }

        setContent {
            LlmDataAnalystTheme {
                val navController = rememberNavController()
                LaunchedEffect(Unit) {
                    // Placeholder for future startup checks.
                }
                AppNavHost(navController = navController, appContainer = appContainer)
            }
        }
    }
}
