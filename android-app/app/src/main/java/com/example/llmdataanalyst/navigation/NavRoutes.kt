package com.example.llmdataanalyst.navigation

sealed class NavRoute(val route: String) {
    data object Login : NavRoute("login")
    data object Dashboard : NavRoute("dashboard")
    data object Chat : NavRoute("chat?chatId={chatId}&datasetId={datasetId}&datasetName={datasetName}") {
        fun withDataset(datasetId: String?, datasetName: String?, chatId: String? = null): String {
            if (datasetId.isNullOrBlank() && datasetName.isNullOrBlank() && chatId.isNullOrBlank()) return "chat"
            val chatPart = java.net.URLEncoder.encode(chatId.orEmpty(), Charsets.UTF_8.name())
            val idPart = java.net.URLEncoder.encode(datasetId.orEmpty(), Charsets.UTF_8.name())
            val namePart = java.net.URLEncoder.encode(datasetName.orEmpty(), Charsets.UTF_8.name())
            return "chat?chatId=$chatPart&datasetId=$idPart&datasetName=$namePart"
        }
    }
    data object Datasets : NavRoute("datasets")
    data object DatasetPicker : NavRoute("dataset_picker")
    data object Artifacts : NavRoute("artifacts")
    data object Lab2 : NavRoute("lab2")
    data object DatasetDetail : NavRoute("datasets/{datasetId}")
    data object ArtifactDetail : NavRoute("artifact/{artifactId}")
    data object Settings : NavRoute("settings")
}
