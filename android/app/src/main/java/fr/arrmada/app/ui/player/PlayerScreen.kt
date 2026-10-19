package fr.arrmada.app.ui.player

import android.view.KeyEvent as AndroidKeyEvent
import androidx.activity.compose.BackHandler
import androidx.annotation.OptIn
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.nativeKeyCode
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector
import androidx.media3.ui.PlayerView
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.data.MovieDetail
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.WatchStateUpdate
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Ce qu'il faut lancer : un film (TMDB) ou un épisode (TVDB + numéros). */
data class PlayRequest(
    val kind: String, // « movie » ou « episode »
    val id: Long, // TMDB du film, ou TVDB de la série
    val season: Int = 0,
    val episode: Int = 0,
    val radarrId: String? = null, // pour la fiche (logo, distribution) du menu pause
    val startSeconds: Int = 0,
)

/** Un film est « vu » passé 90 % (le générique de fin ne compte pas). */
private const val WATCHED_RATIO = 0.90

/**
 * Lecteur vidéo plein écran (Media3 ExoPlayer).
 *
 * Le fichier d'origine est lu sans transcodage, relayé par le serveur
 * ArrMada depuis Jellyfin. ExoPlayer choisit seul : passthrough du son vers
 * l'ampli quand la sortie HDMI le permet (TrueHD, DTS-HD…), décodeurs
 * matériels pour la 4K / HDR / Dolby Vision.
 *
 * Télécommande :
 *  - OK, Lecture/Pause ou Retour : pause et menu pause (façon Apple TV) ;
 *  - gauche / droite : −10 s / +30 s ;
 *  - dans le menu pause, Retour quitte la lecture (position enregistrée).
 */
@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(request: PlayRequest, app: ArrMadaApplication, onExit: () -> Unit) {
    val repository = app.repository
    var info by remember { mutableStateOf<PlayInfo?>(null) }
    var detail by remember { mutableStateOf<MovieDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(request) {
        try {
            val play = if (request.kind == "movie") repository.playMovie(request.id)
            else repository.playEpisode(request.id, request.season, request.episode)
            if (play.status != "ok") {
                error = play.reason ?: "Titre introuvable dans Jellyfin"
                return@LaunchedEffect
            }
            info = play
            request.radarrId?.let { id -> detail = runCatching { repository.movie(id) }.getOrNull() }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    // Préréglage de l'ampli de la pièce (comme l'add-on), sans attendre
    LaunchedEffect(request) {
        app.appScope.launch {
            runCatching {
                val device = repository.me()
                val file = detail?.file
                repository.applyAmpPreset(
                    device,
                    if (request.kind == "movie") "movie" else "series",
                    file?.audioCodec,
                    file?.audioChannels,
                )
            }
        }
    }

    val play = info
    when {
        error != null -> return MessageScreen("Lecture impossible", error, "Retour", onExit)
        play == null -> return MessageScreen("Préparation de la lecture…")
    }
    PlayerSurface(request, play!!, detail, app, onExit)
}

@OptIn(UnstableApi::class)
@Composable
private fun PlayerSurface(
    request: PlayRequest,
    info: PlayInfo,
    detail: MovieDetail?,
    app: ArrMadaApplication,
    onExit: () -> Unit,
) {
    val context = LocalContext.current
    val repository = app.repository

    // ── Création du lecteur (une fois) ──
    val player = remember {
        val trackSelector = DefaultTrackSelector(context).apply {
            setParameters(
                buildUponParameters()
                    // Français d'abord, sinon la piste par défaut du fichier.
                    // Pas de langue de sous-titres préférée : seuls les sous-titres
                    // « forcés » (passages en langue étrangère) s'affichent d'office ;
                    // les autres se choisissent dans le menu pause.
                    .setPreferredAudioLanguages("fr", "en")
            )
        }
        ExoPlayer.Builder(context, DefaultRenderersFactory(context))
            .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(app.api.http)))
            .setTrackSelector(trackSelector)
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(),
                true,
            )
            .setSeekBackIncrementMs(10_000)
            .setSeekForwardIncrementMs(30_000)
            .build()
            .apply {
                setMediaItem(MediaItem.fromUri(app.api.baseUrl + info.stream))
                prepare()
                if (request.startSeconds > 0) seekTo(request.startSeconds * 1000L)
                playWhenReady = true
            }
    }

    var isPlaying by remember { mutableStateOf(true) }
    var showMenu by remember { mutableStateOf(false) }
    var osdUntil by remember { mutableLongStateOf(0L) }
    var position by remember { mutableLongStateOf(request.startSeconds * 1000L) }
    var duration by remember { mutableLongStateOf(info.duration * 1000L) }
    var tracks by remember { mutableStateOf(Tracks.EMPTY) }
    var playbackError by remember { mutableStateOf<String?>(null) }
    var ended by remember { mutableStateOf(false) }
    val keyFocus = remember { FocusRequester() }

    /** Enregistre la position sur le serveur (partagée avec les TV sous Kodi). */
    fun saveProgress(finished: Boolean = false) {
        val pos = (player.currentPosition / 1000).toInt()
        val total = (player.duration.takeIf { it > 0 } ?: duration).div(1000).toInt()
        if (pos < 5 && !finished) return // rien de commencé
        val watched = finished || (total > 0 && pos >= total * WATCHED_RATIO)
        val update = WatchStateUpdate(
            mediaType = if (request.kind == "movie") "movie" else "episode",
            idType = if (request.kind == "movie") "tmdb" else "tvdb",
            id = request.id.toString(),
            season = request.season.takeIf { request.kind == "episode" },
            episode = request.episode.takeIf { request.kind == "episode" },
            title = detail?.title ?: info.title.orEmpty(),
            watched = watched,
            position = if (watched) 0 else pos,
            total = total,
            lastPlayed = Repository.nowLastPlayed(),
        )
        app.appScope.launch { runCatching { repository.saveWatchState(update) } }
    }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onIsPlayingChanged(playing: Boolean) {
                isPlaying = playing
            }

            override fun onTracksChanged(newTracks: Tracks) {
                tracks = newTracks
            }

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY && player.duration > 0) duration = player.duration
                if (state == Player.STATE_ENDED) {
                    ended = true
                    saveProgress(finished = true)
                    onExit()
                }
            }

            override fun onPlayerError(e: PlaybackException) {
                playbackError = describe(e)
            }
        }
        player.addListener(listener)
        onDispose {
            if (!ended) saveProgress()
            player.removeListener(listener)
            player.release()
        }
    }

    // Position affichée + sauvegarde toutes les 30 s pendant la lecture
    LaunchedEffect(player) {
        var lastSave = System.currentTimeMillis()
        while (true) {
            position = player.currentPosition
            if (player.isPlaying && System.currentTimeMillis() - lastSave > 30_000) {
                saveProgress()
                lastSave = System.currentTimeMillis()
            }
            delay(500)
        }
    }

    fun pause() {
        player.pause()
        showMenu = true
        saveProgress()
    }

    fun resume() {
        showMenu = false
        player.play()
        runCatching { keyFocus.requestFocus() }
    }

    // Retour : pendant la lecture → pause et menu ; dans le menu → quitter
    BackHandler {
        if (showMenu) onExit() else pause()
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(Color.Black)
            .focusRequester(keyFocus)
            .focusable()
            .onPreviewKeyEvent { event ->
                if (showMenu || playbackError != null || event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                when (event.key.nativeKeyCode) {
                    AndroidKeyEvent.KEYCODE_DPAD_CENTER, AndroidKeyEvent.KEYCODE_ENTER,
                    AndroidKeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, AndroidKeyEvent.KEYCODE_MEDIA_PAUSE,
                    AndroidKeyEvent.KEYCODE_SPACE -> { pause(); true }
                    AndroidKeyEvent.KEYCODE_MEDIA_PLAY -> { player.play(); true }
                    AndroidKeyEvent.KEYCODE_DPAD_LEFT, AndroidKeyEvent.KEYCODE_MEDIA_REWIND -> {
                        player.seekBack(); osdUntil = System.currentTimeMillis() + 3000; true
                    }
                    AndroidKeyEvent.KEYCODE_DPAD_RIGHT, AndroidKeyEvent.KEYCODE_MEDIA_FAST_FORWARD -> {
                        player.seekForward(); osdUntil = System.currentTimeMillis() + 3000; true
                    }
                    AndroidKeyEvent.KEYCODE_DPAD_UP, AndroidKeyEvent.KEYCODE_DPAD_DOWN -> {
                        osdUntil = System.currentTimeMillis() + 3000; true
                    }
                    AndroidKeyEvent.KEYCODE_MEDIA_STOP -> { onExit(); true }
                    else -> false
                }
            },
    ) {
        // Image + sous-titres (vue Media3, sans ses propres commandes)
        AndroidView(
            factory = { ctx ->
                PlayerView(ctx).apply {
                    useController = false
                    keepScreenOn = true
                    setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING)
                    this.player = player
                }
            },
            modifier = Modifier.fillMaxSize(),
        )

        // Barre discrète après une avance / un retour rapide
        AnimatedVisibility(
            visible = !showMenu && System.currentTimeMillis() < osdUntil,
            enter = fadeIn(),
            exit = fadeOut(),
            modifier = Modifier.align(Alignment.BottomCenter),
        ) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .background(Brush.verticalGradient(listOf(Color.Transparent, Color(0xCC000000))))
                    .padding(horizontal = 48.dp, vertical = 24.dp)
            ) {
                ProgressBar(if (duration > 0) position.toFloat() / duration else 0f, Modifier.fillMaxWidth(), height = 4.dp)
                Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
                    Text(formatClock(position / 1000), style = MaterialTheme.typography.labelLarge)
                    Text(
                        " / " + formatClock(duration / 1000),
                        style = MaterialTheme.typography.labelLarge,
                        color = ArrColors.TextSecondary,
                    )
                }
            }
        }

        // Menu pause façon Apple TV
        AnimatedVisibility(visible = showMenu, enter = fadeIn(), exit = fadeOut()) {
            PauseMenu(
                info = info,
                detail = detail,
                player = player,
                position = position,
                duration = duration,
                tracks = tracks,
                absolute = app.api::absolute,
                onResume = ::resume,
                onSeek = { seconds ->
                    player.seekTo((seconds * 1000).toLong())
                    resume()
                },
                onQuit = onExit,
            )
        }

        playbackError?.let { message ->
            MessageScreen("Lecture interrompue", message, "Retour", onExit)
        }
    }

    // Rafraîchit la barre d'avance rapide jusqu'à ce qu'elle s'efface
    LaunchedEffect(osdUntil) {
        while (System.currentTimeMillis() < osdUntil) delay(250)
        osdUntil = 0
    }
    LaunchedEffect(Unit) { runCatching { keyFocus.requestFocus() } }
}

/** Message lisible pour les erreurs de lecture les plus courantes. */
private fun describe(e: PlaybackException): String = when (e.errorCode) {
    PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED,
    PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_TIMEOUT -> "Connexion au serveur perdue."
    PlaybackException.ERROR_CODE_IO_BAD_HTTP_STATUS -> "Le serveur a refusé le fichier (Jellyfin joignable ?)."
    PlaybackException.ERROR_CODE_DECODER_INIT_FAILED,
    PlaybackException.ERROR_CODE_DECODER_QUERY_FAILED,
    PlaybackException.ERROR_CODE_DECODING_FORMAT_UNSUPPORTED,
    PlaybackException.ERROR_CODE_DECODING_FORMAT_EXCEEDS_CAPABILITIES -> "Format vidéo non pris en charge par cet appareil."
    PlaybackException.ERROR_CODE_AUDIO_TRACK_INIT_FAILED,
    PlaybackException.ERROR_CODE_AUDIO_TRACK_WRITE_FAILED -> "Sortie audio impossible (format non accepté par l’ampli ou la TV)."
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_UNSUPPORTED,
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_MALFORMED -> "Fichier illisible ou format de conteneur non pris en charge."
    else -> "${e.errorCodeName} : ${e.message.orEmpty()}"
}
