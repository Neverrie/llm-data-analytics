package com.example.llmdataanalyst.navigation

sealed class NavRoute(val route: String) {
    data object Login : NavRoute("login")
    data object Dashboard : NavRoute("dashboard")
    data object Chat : NavRoute("chat?datasetId={datasetId}&datasetName={datasetName}") {
        fun withDataset(datasetId: String?, datasetName: String?): String {
            if (datasetId.isNullOrBlank() && datasetName.isNullOrBlank()) return "chat"
            val idPart = java.net.URLEncoder.encode(datasetId.orEmpty(), Charsets.UTF_8.name())
            val namePart = java.net.URLEncoder.encode(datasetName.orEmpty(), Charsets.UTF_8.name())
            return "chat?datasetId=$idPart&datasetName=$namePart"
        }
    }
    data object Datasets : NavRoute("datasets")
    data object DatasetDetail : NavRoute("datasets/{datasetId}")
    data object ArtifactDetail : NavRoute("artifact/{artifactId}")
    data object Settings : NavRoute("settings")
}
