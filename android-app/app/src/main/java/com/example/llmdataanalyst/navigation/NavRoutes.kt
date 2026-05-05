package com.example.llmdataanalyst.navigation

sealed class NavRoute(val route: String) {
    data object Login : NavRoute("login")
    data object Dashboard : NavRoute("dashboard")
    data object Chat : NavRoute("chat")
    data object Datasets : NavRoute("datasets")
    data object DatasetDetail : NavRoute("datasets/{datasetId}")
    data object ArtifactDetail : NavRoute("artifact/{artifactId}")
    data object Settings : NavRoute("settings")
}
