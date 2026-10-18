// Module « app » : l'appli ArrMada elle-même.

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// ─── Version ─────────────────────────────────────────────────────────────────
// versionName vient de gradle.properties ; versionCode est passé par
// build-apk.sh (-Parrmada.versionCode=<nombre de commits>), 1 par défaut.
val appVersionName = providers.gradleProperty("arrmada.versionName").getOrElse("1.0.0")
val appVersionCode = providers.gradleProperty("arrmada.versionCode").getOrElse("1").toInt()

// ─── Signature ───────────────────────────────────────────────────────────────
// Android refuse d'installer un APK non signé, et refuse une mise à jour signée
// par une autre clé. La clé « release » est donc unique et conservée HORS du
// dépôt ; son chemin et ses mots de passe arrivent par variables d'environnement
// (posées par build-apk.sh en local, par les secrets GitHub en CI).
val releaseKeystore: String? = System.getenv("ARRMADA_KEYSTORE")?.takeIf { it.isNotBlank() }

android {
    namespace = "fr.arrmada.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "fr.arrmada.app"
        // Android 8.0 : couvre la Shield (Android 11) et tout téléphone récent.
        minSdk = 26
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersionName
    }

    signingConfigs {
        if (releaseKeystore != null) {
            create("release") {
                storeFile = file(releaseKeystore)
                storePassword = System.getenv("ARRMADA_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ARRMADA_KEY_ALIAS")?.takeIf { it.isNotBlank() } ?: "arrmada"
                keyPassword = System.getenv("ARRMADA_KEY_PASSWORD")?.takeIf { it.isNotBlank() }
                    ?: System.getenv("ARRMADA_KEYSTORE_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            // Pas d'obfuscation : l'appli est petite, et un plantage reste lisible.
            isMinifyEnabled = false
            signingConfig = signingConfigs.findByName("release")
        }
        debug {
            // L'APK de test s'installe À CÔTÉ de la version normale.
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
    }

    buildFeatures {
        buildConfig = true // BuildConfig.VERSION_NAME, affiché dans l'écran de connexion
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    // Trois bibliothèques AndroidX seulement (pas de framework) :
    implementation("androidx.core:core-ktx:1.13.1") // marges des barres système
    implementation("androidx.activity:activity-ktx:1.9.3") // touche Retour moderne
    implementation("androidx.webkit:webkit:1.12.1") // script injecté avant la page

    testImplementation("junit:junit:4.13.2")
}
