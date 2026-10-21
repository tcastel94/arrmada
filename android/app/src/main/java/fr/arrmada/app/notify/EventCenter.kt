package fr.arrmada.app.notify

import android.graphics.BitmapFactory
import android.util.Base64
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import fr.arrmada.app.data.CameraEvent
import fr.arrmada.app.data.EventLogic
import fr.arrmada.app.data.PlayAnnounce
import fr.arrmada.app.data.Prefs
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.ServerEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import java.time.LocalDateTime

/** Une bulle prête à afficher (photo de caméra décodée, le cas échéant). */
data class Toast(val bubble: EventLogic.Bubble, val photo: ImageBitmap? = null, val millis: Long = 7_000)

/** Alerte caméra pendant un film : petite fenêtre en haut à gauche. */
data class CameraAlert(val event: CameraEvent, val photo: ImageBitmap?)

/**
 * Écoute les événements du serveur, comme le service de l'add-on : toutes
 * les 5 s, `GET /api/events/recent?since_id=N` (un `tail -f` par relevés,
 * pas de connexion ouverte en permanence). En cas d'échec, l'intervalle
 * double jusqu'à 2 min, puis revient à 5 s dès que le serveur répond.
 *
 * Ce qu'il en sort, observé par l'écran :
 *  - [toasts] : bulles en bas à droite (import, téléchargement lancé…) ;
 *    pendant un film, elles attendent la fin et sortent en un résumé
 *    « Pendant ta séance » ;
 *  - [ready] : pop-up « Prêt à regarder » (demande faite depuis cette TV) ;
 *  - [camera] : détection d'une caméra pendant un film (sinon une bulle) ;
 *  - [playRequests] : « Lire sur la TV » envoyé depuis la web app.
 *
 * Tourne tant que l'appli est à l'écran ([start] / [stop] suivent l'activité).
 */
class EventCenter(
    private val repository: Repository,
    private val prefs: Prefs,
    private val scope: CoroutineScope,
    private val json: Json,
) {
    private val _toasts = MutableStateFlow<List<Toast>>(emptyList())
    val toasts: StateFlow<List<Toast>> = _toasts.asStateFlow()

    private val _ready = MutableStateFlow<PlayAnnounce?>(null)
    val ready: StateFlow<PlayAnnounce?> = _ready.asStateFlow()

    private val _camera = MutableStateFlow<CameraAlert?>(null)
    val camera: StateFlow<CameraAlert?> = _camera.asStateFlow()

    private val _playRequests = MutableSharedFlow<PlayAnnounce>(extraBufferCapacity = 4)
    val playRequests: SharedFlow<PlayAnnounce> = _playRequests.asSharedFlow()

    /** Vrai pendant la lecture d'un film ou d'un épisode (posé par le lecteur). */
    private val _playing = MutableStateFlow(false)
    val playing: StateFlow<Boolean> = _playing.asStateFlow()

    private val cursor = EventLogic.Cursor()
    private val held = mutableListOf<EventLogic.Bubble>() // bulles retenues pendant un film
    private var heldReady: PlayAnnounce? = null
    private var job: Job? = null

    fun start() {
        if (job?.isActive == true) return
        job = scope.launch {
            var wait = EVERY_MS
            while (isActive) {
                if (prefs.paired.value) {
                    wait = runCatching { poll() }.fold({ EVERY_MS }, { (wait * 2).coerceAtMost(MAX_WAIT_MS) })
                }
                delay(wait)
            }
        }
    }

    fun stop() {
        job?.cancel()
        job = null
    }

    /** Le lecteur démarre / s'arrête. À l'arrêt : ce qui a été retenu sort. */
    fun setPlaying(value: Boolean) {
        // Le lecteur (fil de l'écran) et le relevé (fil réseau) touchent les
        // mêmes listes : un verrou, comme un `flock` autour d'un fichier partagé
        synchronized(held) {
            _playing.value = value
            if (value) return
            if (held.isNotEmpty()) {
                EventLogic.merge(held.toList(), "Pendant ta séance").forEach { push(Toast(it)) }
                held.clear()
            }
            heldReady?.let { _ready.value = it }
            heldReady = null
        }
    }

    fun dismissToast(toast: Toast) = _toasts.update { list -> list.filterNot { it === toast } }

    fun dismissReady() {
        _ready.value = null
    }

    fun dismissCamera() {
        _camera.value = null
    }

    private fun push(toast: Toast) = _toasts.update { (it + toast).takeLast(MAX_QUEUE) }

    private suspend fun poll() {
        val page = repository.events(cursor.sinceId)
        val fresh = cursor.accept(page)
        if (fresh.isEmpty()) return
        val bubbles = mutableListOf<EventLogic.Bubble>()
        for (event in fresh) {
            when (event.type) {
                "tv_ready" -> announce(event)?.let { onReady(it) }
                "play_request" -> announce(event)?.let { _playRequests.tryEmit(it) }
                "camera" -> onCamera(event)
                else -> EventLogic.bubble(event)?.let { bubbles += it }
            }
        }
        if (bubbles.isEmpty()) return
        synchronized(held) {
            if (_playing.value) {
                held.addAll(bubbles)
            } else {
                EventLogic.merge(bubbles).forEach { push(Toast(it)) }
            }
        }
    }

    /** L'annonce, si elle vise cette TV et date de moins de 2 min. */
    private suspend fun announce(event: ServerEvent): PlayAnnounce? {
        val data = runCatching { json.decodeFromJsonElement(PlayAnnounce.serializer(), event.data) }.getOrNull() ?: return null
        val me = runCatching { repository.device() }.getOrNull() ?: return null
        return data.takeIf { EventLogic.forMe(it.deviceId, me.id, it.at, LocalDateTime.now()) }
    }

    private fun onReady(ready: PlayAnnounce) {
        // Pendant un film : la pop-up attend la fin (seule la plus récente compte)
        synchronized(held) {
            if (_playing.value) {
                heldReady = ready
            } else {
                _ready.value = ready
            }
        }
    }

    private suspend fun onCamera(event: ServerEvent) {
        val cam = runCatching { json.decodeFromJsonElement(CameraEvent.serializer(), event.data) }.getOrNull() ?: return
        val photo = cam.snapshotId?.let { id ->
            runCatching {
                val snap = repository.cameraSnapshot(id)
                val bytes = Base64.decode(snap.image, Base64.DEFAULT)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
            }.getOrNull()
        }
        if (_playing.value) {
            _camera.value = CameraAlert(cam, photo)
        } else {
            val bubble = EventLogic.Bubble(EventLogic.cameraLabel(cam), EventLogic.cameraSubtitle(cam, LocalDateTime.now()))
            push(Toast(bubble, photo, millis = 10_000))
        }
    }

    companion object {
        private const val EVERY_MS = 5_000L
        private const val MAX_WAIT_MS = 120_000L
        private const val MAX_QUEUE = 4
    }
}
