// Module « app » : l'appli ArrMada native (ADR-007).

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

// ─── Version ─────────────────────────────────────────────────────────────────
// versionName vient de gradle.properties ; versionCode est passé par
// build-apk.sh (-Parrmada.versionCode=<nombre de commits>), 1 par défaut.
val appVersionName = providers.gradleProperty("arrmada.versionName").getOrElse("2.0.0")
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
        // Android 8.0 : couvre la Shield (Android 11) et tout boîtier récent.
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
            // Pas d'obfuscation : un plantage reste lisible dans les journaux.
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
        compose = true
        buildConfig = true // BuildConfig.VERSION_NAME, affiché dans les réglages
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    testOptions {
        // Tests d'écrans sur la machine de build (Robolectric) : ressources Android incluses
        unitTests.isIncludeAndroidResources = true
        unitTests.all {
            // Captures d'écran (Roborazzi) écrites dans build/outputs/roborazzi/
            it.systemProperty("roborazzi.test.record", "true")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    // ── Interface : Jetpack Compose + Compose for TV ──
    // La « BOM » fixe d'un coup des versions compatibles entre elles pour
    // toutes les bibliothèques Compose (comme un fichier de verrouillage).
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.tv:tv-material:1.0.0") // composants TV (focus, cartes, boutons)
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.13.1") // plein écran du lecteur (téléphone, tablette)
    implementation("androidx.tvprovider:tvprovider:1.0.0") // rangées sur l'accueil Android TV (À suivre, chaîne)
    implementation("androidx.work:work-runtime-ktx:2.9.1") // mise à jour de ces rangées en tâche de fond
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")

    // ── Lecteur vidéo : Media3 ExoPlayer ──
    val media3 = "1.5.1"
    implementation("androidx.media3:media3-exoplayer:$media3")
    implementation("androidx.media3:media3-ui:$media3") // surface vidéo + sous-titres
    implementation("androidx.media3:media3-datasource-okhttp:$media3") // jeton d'appareil sur le flux
    implementation("androidx.media3:media3-exoplayer-hls:$media3") // remux Jellyfin (.m2ts, .iso…)
    // Décodeur audio FFmpeg (build Jellyfin de l'extension Media3, LGPL) : secours
    // quand le décodeur d'Android refuse un son (MP3 d'un vieil .avi, DTS / TrueHD
    // sur un téléphone sans passthrough). Construit pour Media3 1.5.0, compatible 1.5.x.
    implementation("org.jellyfin.media3:media3-ffmpeg-decoder:1.5.0+1")

    // ── Réseau, JSON, images ──
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")
    implementation("io.coil-kt:coil-compose:2.7.0")

    // ── Tests ──
    testImplementation("junit:junit:4.13.2")
    // Captures d'écran sans appareil : Robolectric simule Android sur la
    // machine de build, Roborazzi enregistre l'image de chaque écran.
    testImplementation("org.robolectric:robolectric:4.13")
    testImplementation("io.github.takahirom.roborazzi:roborazzi:1.26.0")
    testImplementation("io.github.takahirom.roborazzi:roborazzi-compose:1.26.0")
    testImplementation(composeBom)
    testImplementation("androidx.compose.ui:ui-test-junit4")
    testImplementation("androidx.compose.ui:ui-test-manifest")
}
