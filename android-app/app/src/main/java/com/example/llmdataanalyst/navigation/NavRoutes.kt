package com.example.llmdataanalyst.navigation

sealed class NavRoute(val route: String) {
    data object Login : NavRoute("login")
    data object Dashboard : NavRoute("dashboard")
    data object Chat : NavRoute("chat?datasetName={datasetName}") {
        fun withDataset(datasetName: String?): String {
            if (datasetName.isNullOrBlank()) return "chat"
            return "chat?datasetName=${java.net.URLEncoder.encode(datasetName, Charsets.UTF_8.name())}"
        }
    }
    data object Datasets : NavRoute("datasets")
    data object DatasetDetail : NavRoute("datasets/{datasetId}")
    data object ArtifactDetail : NavRoute("artifact/{artifactId}")
    data object Settings : NavRoute("settings")
}
