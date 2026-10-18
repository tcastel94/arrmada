// Versions des outils de build, figées volontairement : une montée de version
// se fait à la main (et se teste), jamais en douce au prochain build.
plugins {
    id("com.android.application") version "8.7.3" apply false
    id("org.jetbrains.kotlin.android") version "2.1.0" apply false
}
