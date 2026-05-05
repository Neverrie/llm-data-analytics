package com.example.llmdataanalyst.navigation

sealed class NavRoute(val route: String) {
    data object Login : NavRoute("login")
    data object Dashboard : NavRoute("dashboard")
    data object Chat : NavRoute("chat")
    data object Settings : NavRoute("settings")
}
