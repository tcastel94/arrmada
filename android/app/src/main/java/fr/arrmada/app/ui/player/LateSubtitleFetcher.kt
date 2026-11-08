package fr.arrmada.app.ui.player

import android.net.Uri
import androidx.compose.runtime.Stable
import fr.arrmada.app.data.LateSubtitleLogic
import fr.arrmada.app.data.LateSubtitleLogic.Failure
import fr.arrmada.app.data.LateSubtitleLogic.Next
import fr.arrmada.app.data.SideSubtitle
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import java.io.File
import java.io.IOException
import java.io.InterruptedIOException
import kotlin.coroutines.resume

/**
 * Va chercher, en arrière-plan et avec patience, les pistes de sous-titres
 * que Jellyfin extrait (voir LateSubtitleLogic), et garde chacune dans un
 * fichier de l'appli : le lecteur la lit ensuite en local, sans redemander
 * au serveur, et ne peut plus bloquer dessus.
 *
 * Les pistes se demandent une par une : Jellyfin extrait toutes les pistes
 * texte d'un fichier en une seule passe, quand la première répond les autres
 * suivent aussitôt ; et une seule demande à la fois reste en attente côté
 * serveur. Chaque demande passe par le client patient de l'API (45 s) ;
 * une coupure n'annule rien chez Jellyfin, la demande suivante rejoint
 * l'extraction en cours (LateSubtitleLogic.afterFailure).
 *
 * Une instance par lecture (créée avec `remember` dans PlayerSurface). Ses
 * champs se lisent et s'écrivent sur le fil de l'écran ([scope]) ; seul le
 * téléchargement lui-même tourne sur les fils d'OkHttp.
 */
@Stable
internal class LateSubtitleFetcher(
    private val http: OkHttpClient,
    private val baseUrl: String,
    private val scope: CoroutineScope,
    cacheDir: File,
) {
    private val dir = File(cacheDir, "sous-titres")
    private val files = HashMap<String, File>() // adresse → fichier reçu
    private val failedUrls = HashSet<String>()
    private var job: Job? = null

    /** Adresses déjà reçues (fichier local). */
    val ready: Set<String> get() = files.keys

    /** Adresses abandonnées pour la séance (piste inconnue du serveur). */
    val failed: Set<String> get() = failedUrls

    /** Pistes encore attendues par la demande en cours (vide : rien en attente). */
    var pending: List<SideSubtitle> = emptyList()
        private set

    /** La dernière demande s'est arrêtée faute de temps (extraction toujours en cours). */
    var outOfTime: Boolean = false
        private set

    /** Fichier local d'une piste déjà reçue, pour le lecteur ; null : à demander au serveur. */
    fun localUri(sub: SideSubtitle): Uri? = files[sub.url]?.let(Uri::fromFile)

    /** Interrompt la demande en cours (changement de flux, sortie du lecteur). */
    fun cancel() {
        job?.cancel()
        job = null
        pending = emptyList()
    }

    /**
     * Demande les pistes [later] l'une après l'autre ; renvoie la tâche, à
     * attendre avec `join`. Les pistes reçues s'ajoutent à [ready], celles
     * refusées par le serveur à [failed] ; [outOfTime] dit si le temps a
     * manqué pour le reste.
     */
    fun fetch(later: List<SideSubtitle>): Job {
        cancel()
        pending = later
        outOfTime = false
        val started = System.currentTimeMillis()
        val task = scope.launch {
            for (sub in later) {
                if (!fetchOne(sub, started)) {
                    outOfTime = true
                    break
                }
                pending = pending.filterNot { it.url == sub.url }
            }
            pending = emptyList()
        }
        job = task
        return task
    }

    /** Message à afficher une fois la demande des pistes [later] finie ; null si tout est arrivé. */
    fun outcomeMessage(later: List<SideSubtitle>): String? =
        LateSubtitleLogic.outcomeMessage(later.filter { it.url in failedUrls }, outOfTime)

    /** Efface les fichiers reçus (fin de la lecture). */
    fun clear() {
        cancel()
        files.values.forEach { it.delete() }
        files.clear()
    }

    /** Demande [sub] jusqu'à la recevoir ou y renoncer ; false : plus de temps, on arrête tout. */
    private suspend fun fetchOne(sub: SideSubtitle, started: Long): Boolean {
        while (true) {
            val attemptStart = System.currentTimeMillis()
            when (val outcome = download(sub)) {
                is Outcome.Received -> {
                    files[sub.url] = outcome.file
                    return true
                }
                is Outcome.Failed -> {
                    val now = System.currentTimeMillis()
                    when (LateSubtitleLogic.afterFailure(outcome.failure, now - attemptStart, now - started)) {
                        Next.RETRY_NOW -> Unit
                        Next.RETRY_AFTER_PAUSE -> delay(LateSubtitleLogic.PAUSE_MS)
                        Next.GIVE_UP -> {
                            failedUrls += sub.url
                            return true
                        }
                        Next.OUT_OF_TIME -> return false
                    }
                }
            }
        }
    }

    private sealed class Outcome {
        data class Received(val file: File) : Outcome()
        data class Failed(val failure: Failure) : Outcome()
    }

    /**
     * Une tentative : la piste écrite dans son fichier, ou la raison de
     * l'échec. Annuler la coroutine annule la requête HTTP.
     */
    private suspend fun download(sub: SideSubtitle): Outcome {
        val call = http.newCall(Request.Builder().url(baseUrl + sub.url).get().build())
        return suspendCancellableCoroutine { continuation ->
            continuation.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    if (!continuation.isActive) return
                    // SocketTimeoutException : pas de réponse dans le délai du client
                    continuation.resume(Outcome.Failed(if (e is InterruptedIOException) Failure.Timeout else Failure.Unreachable))
                }

                override fun onResponse(call: Call, response: Response) {
                    val outcome = response.use { r -> if (r.isSuccessful) save(sub, r) else Outcome.Failed(Failure.Http(r.code)) }
                    if (continuation.isActive) continuation.resume(outcome)
                }
            })
        }
    }

    /** Écrit le corps de [response] dans le fichier de la piste (fichier partiel renommé à la fin). */
    private fun save(sub: SideSubtitle, response: Response): Outcome = runCatching {
        dir.mkdirs()
        val target = File(dir, LateSubtitleLogic.fileName(sub.url))
        val partial = File(dir, target.name + ".part")
        partial.outputStream().use { out -> response.body?.byteStream()?.copyTo(out) }
        if (!partial.renameTo(target)) {
            partial.copyTo(target, overwrite = true)
            partial.delete()
        }
        Outcome.Received(target) as Outcome
    }.getOrElse { Outcome.Failed(Failure.Unreachable) }
}
