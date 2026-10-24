// Versions des outils de build, figées volontairement : une montée de version
// se fait à la main (et se teste), jamais en douce au prochain build.
plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.1.0" apply false
    // Compilateur Compose (l'interface est décrite en Kotlin, sans XML)
    id("org.jetbrains.kotlin.plugin.compose") version "2.1.0" apply false
    // Lecture du JSON de l'API dans des classes Kotlin
    id("org.jetbrains.kotlin.plugin.serialization") version "2.1.0" apply false
}
