package com.example.llmdataanalyst.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.SpaceDashboard
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.NavType
import androidx.navigation.navArgument
import androidx.navigation.compose.composable
import com.example.llmdataanalyst.AppContainer
import com.example.llmdataanalyst.feature.auth.AuthViewModel
import com.example.llmdataanalyst.feature.auth.AuthViewModelFactory
import com.example.llmdataanalyst.feature.auth.LoginScreen
import com.example.llmdataanalyst.feature.chat.ChatScreen
import com.example.llmdataanalyst.feature.chat.ChatViewModel
import com.example.llmdataanalyst.feature.chat.ChatViewModelFactory
import com.example.llmdataanalyst.feature.chat.ArtifactDetailScreen
import com.example.llmdataanalyst.feature.dashboard.DashboardScreen
import com.example.llmdataanalyst.feature.dashboard.DashboardViewModel
import com.example.llmdataanalyst.feature.dashboard.DashboardViewModelFactory
import com.example.llmdataanalyst.feature.datasets.DatasetDetailScreen
import com.example.llmdataanalyst.feature.datasets.DatasetsScreen
import com.example.llmdataanalyst.feature.datasets.DatasetsViewModel
import com.example.llmdataanalyst.feature.datasets.DatasetsViewModelFactory
import com.example.llmdataanalyst.feature.artifacts.ArtifactsScreen
import com.example.llmdataanalyst.feature.artifacts.ArtifactsViewModel
import com.example.llmdataanalyst.feature.artifacts.ArtifactsViewModelFactory
import com.example.llmdataanalyst.feature.settings.SettingsScreen
import com.example.llmdataanalyst.feature.settings.SettingsViewModel
import com.example.llmdataanalyst.feature.settings.SettingsViewModelFactory
import com.example.llmdataanalyst.feature.lab2.Lab2PipelineScreen
import com.example.llmdataanalyst.feature.lab2.Lab2ViewModel
import com.example.llmdataanalyst.feature.lab2.Lab2ViewModelFactory
import kotlinx.coroutines.launch

private data class DrawerItem(val label: String, val icon: ImageVector, val route: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppNavHost(
    navController: NavHostController,
    appContainer: AppContainer
) {
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val drawerItems = listOf(
        DrawerItem("Главная", Icons.Default.SpaceDashboard, NavRoute.Dashboard.route),
        DrawerItem("Чат", Icons.Default.Chat, NavRoute.Chat.withDataset(null, null)),
        DrawerItem("Датасеты", Icons.Default.Storage, NavRoute.Datasets.route),
        DrawerItem("Артефакты", Icons.Default.Image, NavRoute.Artifacts.route),
        DrawerItem("Lab2 Pipeline", Icons.Default.SpaceDashboard, NavRoute.Lab2.route),
        DrawerItem("Настройки", Icons.Default.Settings, NavRoute.Settings.route)
    )

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet {
                drawerItems.forEach { item ->
                    NavigationDrawerItem(
                        label = { Text(item.label) },
                        selected = false,
                        onClick = {
                            navController.navigate(item.route)
                            scope.launch { drawerState.close() }
                        },
                        icon = { Icon(item.icon, contentDescription = item.label) }
                    )
                }
            }
        }
    ) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Text("LLM Data Analyst") },
                    navigationIcon = {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) {
                            Icon(Icons.Default.Menu, contentDescription = "menu")
                        }
                    }
                )
            }
        ) { padding ->
            NavHost(
                navController = navController,
                startDestination = NavRoute.Login.route,
                modifier = Modifier.padding(padding)
            ) {
                composable(NavRoute.Login.route) {
                    val vm: AuthViewModel = viewModel(factory = AuthViewModelFactory(appContainer.authRepository))
                    LoginScreen(
                        viewModel = vm,
                        onOpenDashboard = {
                            navController.navigate(NavRoute.Dashboard.route) {
                                popUpTo(NavRoute.Login.route) { inclusive = true }
                            }
                        }
                    )
                }
                composable(NavRoute.Dashboard.route) {
                    val vm: DashboardViewModel = viewModel(factory = DashboardViewModelFactory(appContainer.workspaceRepository))
                    DashboardScreen(
                        viewModel = vm,
                        onOpenChat = { navController.navigate(NavRoute.Chat.withDataset(null, null)) },
                        onOpenSettings = { navController.navigate(NavRoute.Settings.route) },
                        onOpenDatasets = { navController.navigate(NavRoute.Datasets.route) },
                        onOpenArtifacts = { navController.navigate(NavRoute.Artifacts.route) },
                        onOpenLab2 = { navController.navigate(NavRoute.Lab2.route) },
                        onOpenDatasetDetail = { datasetId -> navController.navigate("datasets/$datasetId") },
                        onUseDatasetInChat = { dataset -> navController.navigate(NavRoute.Chat.withDataset(dataset.id, dataset.name)) },
                        onOpenArtifactDetail = { artifactId -> navController.navigate("artifact/$artifactId") },
                        onOpenChatDetail = { chatId -> navController.navigate(NavRoute.Chat.withDataset(null, null, chatId)) }
                    )
                }
                composable(
                    route = NavRoute.Chat.route,
                    arguments = listOf(
                        navArgument("chatId") {
                            type = NavType.StringType
                            defaultValue = ""
                            nullable = true
                        },
                        navArgument("datasetId") {
                            type = NavType.StringType
                            defaultValue = ""
                            nullable = true
                        },
                        navArgument("datasetName") {
                            type = NavType.StringType
                            defaultValue = ""
                            nullable = true
                        }
                    )
                ) { backStackEntry ->
                    val vm: ChatViewModel = viewModel(
                        factory = ChatViewModelFactory(
                            appContainer.chatRepository,
                            appContainer.datasetRepository,
                            appContainer.settingsRepository
                        )
                    )
                    val chatId = backStackEntry.arguments?.getString("chatId")
                    val preselectedDatasetId = backStackEntry.arguments?.getString("datasetId")
                    val preselectedDataset = backStackEntry.arguments?.getString("datasetName")
                    LaunchedEffect(chatId, preselectedDatasetId, preselectedDataset) {
                        if (!chatId.isNullOrBlank()) {
                            vm.openChat(chatId)
                        }
                        if (!preselectedDatasetId.isNullOrBlank() || !preselectedDataset.isNullOrBlank()) {
                            vm.selectDataset(
                                datasetId = preselectedDatasetId?.takeIf { it.isNotBlank() },
                                datasetName = preselectedDataset?.takeIf { it.isNotBlank() }
                            )
                        }
                    }
                    ChatScreen(
                        viewModel = vm,
                        onOpenDatasets = { navController.navigate(NavRoute.DatasetPicker.route) },
                        onOpenArtifact = { artifactId ->
                            navController.navigate("artifact/$artifactId")
                        }
                    )
                }
                composable(NavRoute.Datasets.route) {
                    val vm: DatasetsViewModel = viewModel(factory = DatasetsViewModelFactory(appContainer.datasetRepository))
                    DatasetsScreen(
                        viewModel = vm,
                        onOpenDataset = { datasetId -> navController.navigate("datasets/$datasetId") },
                        onUseInChat = { dataset ->
                            navController.navigate(NavRoute.Chat.withDataset(dataset.id, dataset.name))
                        },
                        selectMode = false
                    )
                }
                composable(NavRoute.DatasetPicker.route) {
                    val vm: DatasetsViewModel = viewModel(factory = DatasetsViewModelFactory(appContainer.datasetRepository))
                    DatasetsScreen(
                        viewModel = vm,
                        onOpenDataset = { datasetId -> navController.navigate("datasets/$datasetId") },
                        onUseInChat = { dataset ->
                            navController.navigate(NavRoute.Chat.withDataset(dataset.id, dataset.name)) {
                                popUpTo(NavRoute.DatasetPicker.route) { inclusive = true }
                            }
                        },
                        selectMode = true
                    )
                }
                composable(NavRoute.Artifacts.route) {
                    val vm: ArtifactsViewModel = viewModel(factory = ArtifactsViewModelFactory(appContainer.artifactRepository))
                    ArtifactsScreen(
                        viewModel = vm,
                        onOpenArtifact = { artifactId -> navController.navigate("artifact/$artifactId") }
                    )
                }
                composable(NavRoute.Lab2.route) {
                    val vm: Lab2ViewModel = viewModel(factory = Lab2ViewModelFactory(appContainer.lab2Repository))
                    Lab2PipelineScreen(viewModel = vm, lab2Repository = appContainer.lab2Repository)
                }
                composable(
                    route = NavRoute.DatasetDetail.route,
                    arguments = listOf(navArgument("datasetId") { type = NavType.StringType })
                ) { backStackEntry ->
                    val vm: DatasetsViewModel = viewModel(factory = DatasetsViewModelFactory(appContainer.datasetRepository))
                    val datasetId = backStackEntry.arguments?.getString("datasetId").orEmpty()
                    DatasetDetailScreen(datasetId = datasetId, viewModel = vm)
                }
                composable(
                    route = NavRoute.ArtifactDetail.route,
                    arguments = listOf(navArgument("artifactId") { type = NavType.StringType })
                ) { backStackEntry ->
                    val artifactId = backStackEntry.arguments?.getString("artifactId").orEmpty()
                    ArtifactDetailScreen(artifactId = artifactId, artifactRepository = appContainer.artifactRepository)
                }
                composable(NavRoute.Settings.route) {
                    val vm: SettingsViewModel = viewModel(
                        factory = SettingsViewModelFactory(appContainer.authRepository, appContainer.settingsRepository)
                    )
                    SettingsScreen(viewModel = vm)
                }
            }
        }
    }
}
