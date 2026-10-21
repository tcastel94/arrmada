package fr.arrmada.app.update

import android.app.PendingIntent
import android.content.ActivityNotFoundException
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.core.content.IntentCompat
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.BuildConfig
import fr.arrmada.app.data.Fr
import fr.arrmada.app.data.UpdateOffer
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.Request
import java.io.File
import java.io.IOException
import java.security.MessageDigest

/**
 * Mises à jour de l'appli (ADR-009), sans adb : le serveur ArrMada garde la
 * dernière APK signée (rapatriée de la CI) ; l'appli la lui demande au
 * lancement, la télécharge sur le réseau local, vérifie son empreinte
 * SHA-256, puis la confie à l'installeur d'Android. Android affiche toujours
 * sa propre confirmation : on ne peut pas (et on ne veut pas) l'éviter.
 *
 * Comme `dnf check-update` puis `dnf upgrade` : [check] regarde, [install] applique.
 */
class UpdateCenter(private val app: ArrMadaApplication) {

    private val _offer = MutableStateFlow<UpdateOffer?>(null)

    /** Version proposée (null : rien à proposer, ou « Plus tard » choisi pour ce lancement). */
    val offer: StateFlow<UpdateOffer?> = _offer

    private var checked = false

    /** Une fois par lancement (accueil). Silencieux : serveur ancien ou injoignable = rien. */
    suspend fun checkOnce() {
        if (checked) return
        checked = true
        _offer.value = fetch().getOrNull()
    }

    /** « Rechercher une mise à jour » (Réglages) : message à afficher si rien de neuf. */
    suspend fun checkNow(): String? {
        val result = fetch()
        _offer.value = result.getOrNull()
        return when {
            result.isFailure -> "Vérification impossible : ${result.exceptionOrNull()?.message ?: "serveur injoignable"}"
            result.getOrNull() == null -> "ArrMada est à jour (${BuildConfig.VERSION_NAME})"
            else -> null
        }
    }

    fun later() {
        _offer.value = null
    }

    private suspend fun fetch(): Result<UpdateOffer?> = runCatching {
        app.repository.updateOffer(BuildConfig.VERSION_CODE, BuildConfig.BUILD_TYPE).takeIf { it.available && it.url.isNotBlank() }
    }

    /**
     * Télécharge l'APK dans le cache de l'appli ([progress] de 0 à 1), refuse
     * un fichier dont l'empreinte ne correspond pas, puis lance l'installation.
     */
    suspend fun install(offer: UpdateOffer, progress: (Float) -> Unit) {
        val file = download(offer, progress)
        withContext(Dispatchers.IO) { commit(app, file) }
    }

    private suspend fun download(offer: UpdateOffer, progress: (Float) -> Unit): File = withContext(Dispatchers.IO) {
        val dir = File(app.cacheDir, "updates").apply { mkdirs() }
        dir.listFiles()?.forEach { it.delete() } // une seule APK à la fois dans le cache
        val file = File(dir, "arrmada-${offer.versionCode}.apk")
        val url = app.api.absolute(offer.url) ?: throw IOException("Adresse de l'APK invalide")
        val digest = MessageDigest.getInstance("SHA-256")
        app.api.http.newCall(Request.Builder().url(url).build()).execute().use { response ->
            if (!response.isSuccessful) throw IOException("Téléchargement refusé (HTTP ${response.code})")
            val body = response.body ?: throw IOException("Réponse vide")
            val total = body.contentLength().takeIf { it > 0 } ?: offer.size
            var done = 0L
            body.byteStream().use { input ->
                file.outputStream().use { out ->
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        val read = input.read(buffer)
                        if (read < 0) break
                        out.write(buffer, 0, read)
                        digest.update(buffer, 0, read)
                        done += read
                        if (total > 0) progress((done.toFloat() / total).coerceIn(0f, 1f))
                    }
                }
            }
        }
        val sha = digest.digest().joinToString("") { "%02x".format(it) }
        if (offer.sha256.isNotBlank() && !sha.equals(offer.sha256, ignoreCase = true)) {
            file.delete()
            throw IOException("APK abîmée pendant le téléchargement (empreinte différente) : réessaie")
        }
        file
    }

    companion object {
        /**
         * Autorisation « Installer des applis inconnues » pour ArrMada (Android
         * la demande une fois). Faux : on ouvre l'écran des réglages qui l'accorde.
         */
        fun canInstall(context: Context): Boolean = context.packageManager.canRequestPackageInstalls()

        fun openInstallPermission(context: Context) {
            val intents = listOf(
                Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}")),
                Intent(Settings.ACTION_SECURITY_SETTINGS), // certaines TV n'ont pas l'écran par appli
            )
            for (intent in intents) {
                try {
                    context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    return
                } catch (_: ActivityNotFoundException) {
                    // essai suivant
                }
            }
            Toast.makeText(context, "Autorise « sources inconnues » pour ArrMada dans les réglages d’Android", Toast.LENGTH_LONG).show()
        }

        /** Confie l'APK à l'installeur d'Android (session : pas de fichier à partager avec une autre appli). */
        private fun commit(context: Context, apk: File) {
            val installer = context.packageManager.packageInstaller
            val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
                setAppPackageName(context.packageName)
                setSize(apk.length())
            }
            val sessionId = installer.createSession(params)
            installer.openSession(sessionId).use { session ->
                session.openWrite("arrmada.apk", 0, apk.length()).use { out ->
                    apk.inputStream().use { it.copyTo(out) }
                    session.fsync(out)
                }
                // Résultat (confirmation à afficher, succès, échec) renvoyé à UpdateReceiver
                val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_MUTABLE else 0
                val callback = PendingIntent.getBroadcast(context, sessionId, Intent(context, UpdateReceiver::class.java), flags)
                session.commit(callback.intentSender)
            }
        }
    }
}

/**
 * Réponse de l'installeur d'Android : il faut la confirmation de
 * l'utilisateur (on affiche son écran), ou l'installation a échoué (message).
 * En cas de succès, Android redémarre l'appli dans sa nouvelle version.
 */
class UpdateReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirm = IntentCompat.getParcelableExtra(intent, Intent.EXTRA_INTENT, Intent::class.java) ?: return
                context.startActivity(confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            }
            PackageInstaller.STATUS_SUCCESS -> Unit
            else -> {
                val detail = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE).orEmpty()
                Toast.makeText(context, UpdateMessages.failure(status, detail), Toast.LENGTH_LONG).show()
            }
        }
    }
}

/** Messages d'échec de l'installeur, en clair. */
object UpdateMessages {
    fun failure(status: Int, detail: String): String = when (status) {
        PackageInstaller.STATUS_FAILURE_ABORTED -> "Mise à jour annulée"
        PackageInstaller.STATUS_FAILURE_STORAGE -> "Mise à jour impossible : plus assez de place sur l’appareil"
        PackageInstaller.STATUS_FAILURE_CONFLICT, PackageInstaller.STATUS_FAILURE_INCOMPATIBLE ->
            "Mise à jour refusée : APK signée par une autre clé (désinstalle ArrMada une fois, puis installe-la)"
        PackageInstaller.STATUS_FAILURE_BLOCKED -> "Mise à jour bloquée par Android (sources inconnues ?)"
        else -> "Mise à jour impossible" + if (detail.isNotBlank()) " : $detail" else ""
    }
}

/**
 * « ArrMada 2.8.0 est disponible » : Mettre à jour (téléchargement avec
 * progression, puis écran d'installation d'Android) ou Plus tard (proposé à
 * nouveau au prochain lancement).
 */
@Composable
fun UpdateDialog(center: UpdateCenter, offer: UpdateOffer) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val focus = remember { FocusRequester() }
    var progress by remember { mutableStateOf<Float?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val working = progress != null && error == null

    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }

    fun start() {
        if (!UpdateCenter.canInstall(context)) {
            error = "Android doit d’abord autoriser ArrMada à installer des applis : active-la dans l’écran qui s’ouvre, puis reviens ici."
            UpdateCenter.openInstallPermission(context)
            return
        }
        error = null
        progress = 0f
        scope.launch {
            runCatching { center.install(offer) { progress = it } }
                .onSuccess { center.later() } // l'écran d'Android prend le relais
                .onFailure { error = it.message ?: "Téléchargement impossible" }
        }
    }

    Dialog(onDismissRequest = { if (!working) center.later() }) {
        Column(
            Modifier.widthIn(max = 520.dp).fillMaxWidth().background(ArrColors.CardDeep, RoundedCornerShape(16.dp)).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("ArrMada ${offer.versionName} est disponible", style = MaterialTheme.typography.titleLarge)
            Text(
                "Installée : ${BuildConfig.VERSION_NAME}" + if (offer.size > 0) " · ${Fr.bytes(offer.size.toDouble())} à télécharger depuis le serveur" else "",
                style = MaterialTheme.typography.bodyMedium,
                color = ArrColors.TextSecondary,
            )
            val p = progress
            if (p != null && error == null) {
                ProgressBar(p, Modifier.fillMaxWidth().padding(top = 6.dp), height = 6.dp)
                Text(
                    if (p < 1f) "Téléchargement… ${(p * 100).toInt()} %" else "Vérification, puis installation par Android…",
                    style = MaterialTheme.typography.labelLarge,
                    color = ArrColors.TextSecondary,
                )
            }
            error?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = ArrColors.Warning) }
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (!working) {
                    ArrButton(if (error != null) "Réessayer" else "Mettre à jour", ::start, primary = true, leading = "⬇", modifier = Modifier.focusRequester(focus))
                    ArrButton("Plus tard", center::later)
                }
            }
            Text(
                "Android affichera sa propre confirmation ; tes réglages et l’appairage sont conservés.",
                style = MaterialTheme.typography.labelSmall,
                color = ArrColors.TextSecondary,
            )
        }
    }
}
