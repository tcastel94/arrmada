// ArrMada Android : déclaration du projet Gradle.
// Gradle est à Android ce que make + un gestionnaire de paquets sont à un
// projet C : il télécharge les dépendances et produit l'APK.

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    // Les dépôts sont définis ici et nulle part ailleurs (un seul endroit à auditer).
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "ArrMada"
include(":app")
