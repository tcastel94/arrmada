package fr.arrmada.app.ui.player

import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.core.view.WindowInsetsControllerCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowCompat
import android.content.pm.ActivityInfo
import fr.arrmada.app.ui.components.LocalScreen
import androidx.compose.foundation.layout.widthIn
import fr.arrmada.app.ui.components.gutter
import android.view.KeyEvent as AndroidKeyEvent
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.annotation.OptIn
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.nativeKeyCode
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
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
import fr.arrmada.app.data.AmpDevice
import fr.arrmada.app.data.SoundAdvisor
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.LocalSeriesDetail
import fr.arrmada.app.data.LocalSeriesLogic
import fr.arrmada.app.data.PlaybackLogic
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.SeriesDetail
import fr.arrmada.app.data.SeriesLogic
import fr.arrmada.app.data.WatchStateUpdate
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive

/** Ce qu'il faut lancer : un film (TMDB) ou un épisode (TVDB + numéros). */
data class PlayRequest(
    val kind: String, // « movie » ou « episode »
    val id: Long, // TMDB du film, ou TVDB de la série
    val season: Int = 0,
    val episode: Int = 0,
    val radarrId: String? = null, // film : fiche Radarr (logo, distribution) pour le menu pause
    val sonarrId: String? = null, // épisode : fiche Sonarr (logo, épisode suivant)
    val startSeconds: Int = 0,
    val file: String? = null, // « file » : jeton de la vidéo (écran Vidéos)
    val localSeries: Int = 0, // « file » d'une série maison : titre, épisode suivant
)

/** Un titre est « vu » passé 90 % (le générique de fin ne compte pas). */
private const val WATCHED_RATIO = 0.90

/** Épisode à enchaîner, avec ce qu'en montre la carte « Épisode suivant ». */
data class UpNext(val request: PlayRequest, val code: String, val title: String, val image: String?)

/**
 * Lecteur vidéo plein écran (Media3 ExoPlayer).
 *
 * Le fichier d'origine est lu sans transcodage, relayé par le serveur
 * ArrMada depuis Jellyfin. ExoPlayer choisit seul : passthrough du son vers
 * l'ampli quand la sortie HDMI le permet (TrueHD, DTS-HD…), décodeurs
 * matériels pour la 4K / HDR / Dolby Vision.
 *
 * Formats qu'ExoPlayer n'ouvre pas (.m2ts de Blu-ray, .iso…) : Jellyfin
 * change le conteneur à la volée (« remux » HLS, image intacte). Le serveur
 * le choisit d'office pour ces extensions ; si un fichier « normal » se
 * révèle illisible, le lecteur y bascule seul, une fois, à la même position.
 *
 * Télécommande :
 *  - OK, Lecture/Pause ou Retour : pause et menu pause (façon Apple TV) ;
 *  - gauche / droite : −10 s / +30 s ;
 *  - bouton « Passer l'intro » affiché : OK saute le passage ;
 *  - carte « Épisode suivant » affichée : OK lance tout de suite, Retour l'écarte ;
 *  - dans le menu pause, Retour quitte la lecture (position enregistrée).
 *
 * [onPlayNext] remplace l'écran par celui de l'épisode suivant.
 */
@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(request: PlayRequest, app: ArrMadaApplication, onExit: () -> Unit, onPlayNext: (PlayRequest) -> Unit) {
    val repository = app.repository
    var info by remember { mutableStateOf<PlayInfo?>(null) }
    var meta by remember { mutableStateOf<PlaybackMeta?>(null) }
    var series by remember { mutableStateOf<SeriesDetail?>(null) }
    var local by remember { mutableStateOf<LocalSeriesDetail?>(null) } // série maison
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(request) {
        try {
            val play = when (request.kind) {
                "movie" -> repository.playMovie(request.id)
                "file" -> repository.playFile(request.file.orEmpty()) // vidéo hors médiathèque
                else -> repository.playEpisode(request.id, request.season, request.episode)
            }
            if (play.status != "ok") {
                error = play.reason ?: "Titre introuvable dans Jellyfin"
                return@LaunchedEffect
            }
            info = play
            // Fiche du titre pour le menu pause (et l'épisode suivant) : en
            // arrière-plan, la lecture n'attend pas
            if (request.kind == "movie") {
                request.radarrId?.let { id -> runCatching { repository.movie(id) }.getOrNull()?.let { meta = it.toMeta() } }
            } else if (request.kind == "file") {
                // Série maison : « Naruto Kai · S02E15 · L'examen commence », épisode suivant
                if (request.localSeries > 0) {
                    runCatching { repository.localSeriesDetail(request.localSeries) }.getOrNull()?.let {
                        local = it
                        meta = LocalSeriesLogic.toDetail(it).toMeta(request.season, request.episode, play)
                    }
                }
            } else {
                request.sonarrId?.let { id ->
                    runCatching { repository.series(id) }.getOrNull()?.takeIf { it.error == null }?.let {
                        series = it
                        meta = it.toMeta(request.season, request.episode, play)
                    }
                }
            }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    // Pendant la lecture, les bulles attendent la fin (« Pendant ta séance »)
    // et une détection de caméra s'affiche en petit en haut à gauche
    DisposableEffect(Unit) {
        app.events.setPlaying(true)
        onDispose { app.events.setPlaying(false) }
    }

    // Préréglage de l'ampli de la pièce (comme l'add-on), sans attendre
    // Fin du préréglage (ou échec) : le décodage auto attend ce signal pour
    // ne pas être écrasé par le programme du préréglage
    val presetDone = remember(request) { CompletableDeferred<Unit>() }
    val touch = LocalScreen.current.isTouch
    LaunchedEffect(request) {
        app.appScope.launch {
            try {
                // Téléphone / tablette : jamais l'ampli de la pièce (on regarde au casque, ailleurs…)
                if (!touch) runCatching {
                    val device = repository.me()
                    repository.applyAmpPreset(device, if (request.kind == "movie") "movie" else "series", null, null)
                }
            } finally {
                presetDone.complete(Unit)
            }
        }
    }

    // Épisode suivant (fiche Sonarr) : disponible sur le disque, dans l'ordre
    val seriesUpNext = series?.let { s ->
        SeriesLogic.following(s, request.season, request.episode)?.let { ep ->
            UpNext(
                request = request.copy(season = ep.seasonNumber, episode = ep.episodeNumber, startSeconds = 0),
                code = "S%02dE%02d".format(ep.seasonNumber, ep.episodeNumber),
                title = ep.title ?: "Épisode ${ep.episodeNumber}",
                image = s.images.fanart ?: s.images.landscape,
            )
        }
    }
    // Série maison : vidéo suivante de la série (dans l'arc, sinon l'arc suivant)
    val upNext = seriesUpNext ?: local?.let { d ->
        LocalSeriesLogic.next(d, request.file.orEmpty())?.let { ep ->
            UpNext(
                request = request.copy(file = ep.token, season = ep.seasonNumber, episode = ep.episodeNumber, startSeconds = 0),
                code = "S%02dE%02d".format(ep.seasonNumber, ep.episodeNumber),
                title = ep.title,
                image = ep.image ?: d.fanartUrl,
            )
        }
    }

    val play = info
    when {
        error != null -> return MessageScreen("Lecture impossible", error, "Retour", onExit)
        play == null -> return MessageScreen("Préparation de la lecture…")
    }
    PlayerSurface(request, play!!, meta, upNext, app, presetDone, onExit, onPlayNext)
}

@OptIn(UnstableApi::class)
@Composable
private fun PlayerSurface(
    request: PlayRequest,
    info: PlayInfo,
    meta: PlaybackMeta?,
    upNext: UpNext?,
    app: ArrMadaApplication,
    presetDone: CompletableDeferred<Unit>,
    onExit: () -> Unit,
    onPlayNext: (PlayRequest) -> Unit,
) {
    val context = LocalContext.current
    val repository = app.repository
    val uiScope = rememberCoroutineScope()
    val touch = LocalScreen.current.isTouch

    // Téléphone / tablette : plein écran, à l'horizontale, pendant la lecture
    DisposableEffect(touch) {
        val activity = context.findActivity()
        if (!touch || activity == null) return@DisposableEffect onDispose {}
        val previous = activity.requestedOrientation
        activity.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        val bars = WindowCompat.getInsetsController(activity.window, activity.window.decorView)
        bars.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        bars.hide(WindowInsetsCompat.Type.systemBars())
        onDispose {
            bars.show(WindowInsetsCompat.Type.systemBars())
            activity.requestedOrientation = previous
        }
    }

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
                setMediaItem(mediaItem(app.api.baseUrl + info.stream, hls = info.mode == "remux", sideSubtitles(info, app.api.baseUrl)))
                prepare()
                if (request.startSeconds > 0) seekTo(request.startSeconds * 1000L)
                playWhenReady = true
            }
    }

    var showMenu by remember { mutableStateOf(false) }
    // Ampli de la pièce (onglet « Ampli » du menu pause) : relu à l'ouverture du menu
    var amp by remember { mutableStateOf<AmpDevice?>(null) }
    var ampRead by remember { mutableIntStateOf(0) }
    LaunchedEffect(showMenu, ampRead) {
        if (!showMenu && ampRead == 0) return@LaunchedEffect
        val me = runCatching { repository.device() }.getOrNull()
        amp = if (me?.hasAmp == true) runCatching { repository.ampState().devices.firstOrNull() }.getOrNull() else null
    }

    // ── Son conseillé : enceintes de la pièce × son de la piste en cours ──
    var hasAmp by remember { mutableStateOf(false) }
    var layout by remember { mutableStateOf<SoundAdvisor.Layout?>(null) }
    var room by remember { mutableStateOf("") }
    var autoSound by remember { mutableStateOf(app.prefs.autoSound) }
    var appliedProgram by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        val me = runCatching { repository.device() }.getOrNull() ?: return@LaunchedEffect
        hasAmp = me.hasAmp && !touch // l'ampli de la pièce ne concerne pas le téléphone
        if (!me.hasAmp) {
            room = if (touch) "Téléphone / tablette : son de l’appareil" else "Pas d’ampli dans cette pièce : son de la TV"
            return@LaunchedEffect
        }
        val profiles = runCatching { repository.roomProfiles() }.getOrDefault(emptyMap())
        val profile = profiles[me.room] ?: profiles[if ("cin" in me.room.lowercase()) "cinema" else "salon"]
        // Enceintes non renseignées : on suppose un 5.1, le cas le plus courant
        layout = SoundAdvisor.layout(profile?.speakers) ?: SoundAdvisor.layout("5.1")
        room = listOfNotNull(
            profile?.name?.ifBlank { null } ?: me.room.replaceFirstChar { it.uppercase() },
            layout?.let { "enceintes ${it.label}" },
        ).joinToString(" · ")
    }

    /** Commande à l'ampli, puis relecture de son état (le réglage choisi s'entoure). */
    fun ampCommand(action: String, value: JsonPrimitive) {
        uiScope.launch {
            runCatching { repository.ampControl(action, value) }
                .onSuccess { if (!it.ok) Toast.makeText(context, it.message ?: "L’ampli a refusé le réglage", Toast.LENGTH_SHORT).show() }
                .onFailure { Toast.makeText(context, it.message ?: "Ampli injoignable", Toast.LENGTH_SHORT).show() }
            ampRead++
        }
    }
    var osdUntil by remember { mutableLongStateOf(0L) }
    var position by remember { mutableLongStateOf(request.startSeconds * 1000L) }
    var duration by remember { mutableLongStateOf(info.duration * 1000L) }
    var tracks by remember { mutableStateOf(Tracks.EMPTY) }
    var playbackError by remember { mutableStateOf<String?>(null) }
    var remuxed by remember { mutableStateOf(info.mode == "remux") } // flux converti par Jellyfin
    var finished by remember { mutableStateOf(false) } // fin enregistrée (vu)
    var upNextDismissed by remember { mutableStateOf(false) }
    var countdown by remember { mutableIntStateOf(PlaybackLogic.UP_NEXT_SECONDS) }
    val keyFocus = remember { FocusRequester() }

    val sound = remember(tracks, meta) { selectedSound(tracks, meta?.file?.audioCodec) }
    val advice = SoundAdvisor.advise(if (hasAmp) layout else null, sound, screenName = if (touch) "l’appareil" else "la TV")

    // Décodage auto : dès que le son du film est connu (ou change de piste),
    // l'ampli prend le programme conseillé, une fois le préréglage terminé
    LaunchedEffect(advice.program, autoSound, hasAmp) {
        val program = advice.program ?: return@LaunchedEffect
        if (!autoSound || !hasAmp || program == appliedProgram) return@LaunchedEffect
        withTimeoutOrNull(10_000) { presetDone.await() }
        delay(800) // l'ampli finit d'appliquer le préréglage
        runCatching { repository.ampControl("sound_program", JsonPrimitive(program)) }.onSuccess {
            if (it.ok) {
                appliedProgram = program
                Toast.makeText(context, "Son : ${advice.headline}", Toast.LENGTH_SHORT).show()
            }
        }
        ampRead++
    }

    val durationSeconds = (duration / 1000.0).takeIf { it > 0 } ?: info.duration.toDouble()
    val skips = remember(info, durationSeconds) { PlaybackLogic.skippable(info, durationSeconds) }
    val activeSkip = PlaybackLogic.activeSkip(skips, position / 1000.0)
    val upNextAt = remember(info, durationSeconds) { PlaybackLogic.upNextAt(info, durationSeconds) }
    val showUpNext = upNext != null && !upNextDismissed && !showMenu && durationSeconds > 0 &&
        position / 1000.0 >= upNextAt

    /** Enregistre la position sur le serveur (partagée avec les TV sous Kodi). */
    fun saveProgress(done: Boolean = false) {
        if (finished) return
        val pos = (player.currentPosition / 1000).toInt()
        val total = (player.duration.takeIf { it > 0 } ?: duration).div(1000).toInt()
        if (pos < 5 && !done) return // rien de commencé
        val watched = done || (total > 0 && pos >= total * WATCHED_RATIO)
        if (watched) finished = true
        // Vidéo de l'écran Vidéos : repérée par l'empreinte de son chemin (fournie par le serveur)
        val file = request.kind == "file"
        if (file && info.watchId.isBlank()) return
        val update = WatchStateUpdate(
            mediaType = when { file -> "file"; request.kind == "movie" -> "movie"; else -> "episode" },
            idType = when { file -> "sha1"; request.kind == "movie" -> "tmdb"; else -> "tvdb" },
            id = if (file) info.watchId else request.id.toString(),
            season = request.season.takeIf { request.kind == "episode" },
            episode = request.episode.takeIf { request.kind == "episode" },
            title = meta?.subtitle?.substringAfter(" · ", "") ?: meta?.title ?: info.title.orEmpty(),
            watched = watched,
            position = if (watched) 0 else pos,
            total = total,
            lastPlayed = Repository.nowLastPlayed(),
        )
        app.appScope.launch { runCatching { repository.saveWatchState(update) } }
    }

    fun playNext() {
        val next = upNext ?: return
        saveProgress(done = true)
        onPlayNext(next.request)
    }

    // Le lecteur et ses écouteurs sont créés une seule fois : ils appellent
    // toujours la DERNIÈRE version de ces actions (la fiche et l'épisode
    // suivant arrivent après le démarrage de la lecture).
    val save by rememberUpdatedState<(Boolean) -> Unit> { done -> saveProgress(done) }
    val onEnded by rememberUpdatedState {
        saveProgress(done = true)
        val next = upNext
        if (next != null && !upNextDismissed) onPlayNext(next.request) else onExit()
    }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onTracksChanged(newTracks: Tracks) {
                tracks = newTracks
            }

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY && player.duration > 0) duration = player.duration
                if (state == Player.STATE_ENDED) onEnded()
            }

            override fun onPlayerError(e: PlaybackException) {
                // Fichier illisible en direct : on retente une fois en remux,
                // là où on en était
                if (!remuxed && info.remuxStream.isNotBlank() && e.errorCode in REMUX_RETRY) {
                    remuxed = true
                    val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
                    player.setMediaItem(mediaItem(app.api.baseUrl + info.remuxStream, hls = true), at)
                    player.prepare()
                    player.play()
                    Toast.makeText(context, "Format ${info.container.ifBlank { "inconnu" }} : conversion par Jellyfin…", Toast.LENGTH_LONG).show()
                    return
                }
                playbackError = describe(e, info.container, remuxed)
            }
        }
        player.addListener(listener)
        onDispose {
            save(false)
            player.removeListener(listener)
            player.release()
            // Remux : Jellyfin arrête la conversion (sinon elle tourne à vide)
            if (remuxed) app.appScope.launch { runCatching { repository.stopRemux(info.itemId) } }
        }
    }

    // Position affichée + sauvegarde toutes les 30 s pendant la lecture
    LaunchedEffect(player) {
        var lastSave = System.currentTimeMillis()
        while (true) {
            position = player.currentPosition
            if (player.isPlaying && System.currentTimeMillis() - lastSave > 30_000) {
                save(false)
                lastSave = System.currentTimeMillis()
            }
            delay(500)
        }
    }

    // Compte à rebours de la carte « Épisode suivant »
    LaunchedEffect(showUpNext) {
        if (!showUpNext) {
            countdown = PlaybackLogic.UP_NEXT_SECONDS
            return@LaunchedEffect
        }
        while (countdown > 0) {
            delay(1000)
            if (player.isPlaying) countdown--
        }
        playNext()
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

    // Retour : carte « Épisode suivant » → l'écarter ; pendant la lecture →
    // pause et menu ; dans le menu → quitter
    BackHandler {
        when {
            showUpNext -> upNextDismissed = true
            showMenu -> onExit()
            else -> pause()
        }
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(Color.Black)
            .focusRequester(keyFocus)
            .focusable()
            // Au doigt : un tap met en pause (menu), deux taps à gauche / à droite : −10 s / +30 s
            .then(
                if (touch) {
                    Modifier.pointerInput(Unit) {
                        detectTapGestures(
                            onTap = { if (!showMenu && playbackError == null) pause() },
                            onDoubleTap = { offset ->
                                if (!showMenu) {
                                    if (offset.x < size.width / 2) player.seekBack() else player.seekForward()
                                    osdUntil = System.currentTimeMillis() + 3000
                                }
                            },
                        )
                    }
                } else {
                    Modifier
                },
            )
            .onPreviewKeyEvent { event ->
                if (showMenu || playbackError != null || event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                val code = event.key.nativeKeyCode
                val ok = code == AndroidKeyEvent.KEYCODE_DPAD_CENTER || code == AndroidKeyEvent.KEYCODE_ENTER
                when {
                    ok && showUpNext -> { playNext(); true }
                    ok && activeSkip != null -> { player.seekTo((activeSkip.end * 1000).toLong()); true }
                    else -> when (code) {
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
                        AndroidKeyEvent.KEYCODE_MEDIA_NEXT -> { if (upNext != null) playNext(); upNext != null }
                        AndroidKeyEvent.KEYCODE_MEDIA_STOP -> { onExit(); true }
                        else -> false
                    }
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
                    .padding(horizontal = gutter, vertical = 24.dp)
            ) {
                ProgressBar(if (duration > 0) position.toFloat() / duration else 0f, Modifier.fillMaxWidth(), height = 4.dp)
                Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
                    Text(formatClock(position / 1000), style = MaterialTheme.typography.labelLarge)
                    Text(" / " + formatClock(duration / 1000), style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
                }
            }
        }

        // « Passer l'intro » (en bas à droite, comme dans l'add-on)
        AnimatedVisibility(
            visible = activeSkip != null && !showMenu && !showUpNext,
            enter = fadeIn() + slideInHorizontally { it / 2 },
            exit = fadeOut(),
            modifier = Modifier.align(Alignment.BottomEnd).padding(end = gutter, bottom = 48.dp),
        ) {
            SkipButton(activeSkip?.let { PlaybackLogic.skipLabel(it) } ?: "")
        }

        // Carte « Épisode suivant »
        AnimatedVisibility(
            visible = showUpNext,
            enter = fadeIn() + slideInHorizontally { it },
            exit = fadeOut() + slideOutHorizontally { it },
            modifier = Modifier.align(Alignment.BottomEnd).padding(end = gutter, bottom = 48.dp),
        ) {
            upNext?.let { UpNextCard(it, countdown, app.api::absolute) }
        }

        // Menu pause façon Apple TV
        AnimatedVisibility(visible = showMenu, enter = fadeIn(), exit = fadeOut()) {
            PauseMenu(
                info = info,
                meta = meta,
                position = position,
                duration = duration,
                tracks = tracks,
                absolute = app.api::absolute,
                onResume = ::resume,
                onSeek = { seconds ->
                    player.seekTo((seconds * 1000).toLong())
                    resume()
                },
                onSelectTrack = { type, choice -> selectTrack(player, type, choice) },
                onQuit = onExit,
                onSkip = { seconds -> player.seekTo((player.currentPosition + seconds * 1000L).coerceAtLeast(0)) },
                audio = AudioContext(room, hasAmp, advice, autoSound),
                amp = amp,
                onAmp = ::ampCommand,
                onAuto = { on ->
                    autoSound = on
                    app.prefs.autoSound = on
                },
                onApplyAdvice = { advice.program?.let { ampCommand("sound_program", JsonPrimitive(it)) } },
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

/** Bouton « Passer l'intro » : bleu plein, OK pour sauter. */
@Composable
fun SkipButton(label: String) {
    Row(
        Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(ArrColors.Accent)
            .padding(horizontal = 22.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text(label, style = MaterialTheme.typography.titleMedium, color = ArrColors.Night)
        Text("OK", style = MaterialTheme.typography.labelSmall, color = ArrColors.Night.copy(alpha = 0.7f))
    }
}

/** Carte « Épisode suivant dans N s » (OK : maintenant ; Retour : non merci). */
@Composable
fun UpNextCard(next: UpNext, countdown: Int, absolute: (String?) -> String?) {
    Row(
        Modifier
            .widthIn(max = 420.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(ArrColors.CardDeep.copy(alpha = 0.96f))
            .padding(12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        ArtImage(absolute(next.image), next.title, Modifier.width(150.dp).height(84.dp).clip(RoundedCornerShape(8.dp)))
        Column(Modifier.weight(1f)) {
            Text("Épisode suivant dans $countdown s", style = MaterialTheme.typography.labelLarge, color = ArrColors.AccentText)
            Text("${next.code} · ${next.title}", style = MaterialTheme.typography.titleMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            ProgressBar(
                1f - countdown.toFloat() / PlaybackLogic.UP_NEXT_SECONDS,
                Modifier.fillMaxWidth().padding(top = 6.dp),
            )
            Text("OK : maintenant  ·  Retour : non merci", style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 4.dp))
        }
    }
}

/** Erreurs de lecture directe qui justifient de retenter en remux. */
private val REMUX_RETRY = setOf(
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_UNSUPPORTED,
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_MALFORMED,
    PlaybackException.ERROR_CODE_DECODING_FORMAT_UNSUPPORTED,
    PlaybackException.ERROR_CODE_AUDIO_TRACK_INIT_FAILED,
)

/** Élément à lire : fichier d'origine, ou liste HLS du remux. */
private fun mediaItem(url: String, hls: Boolean, subtitles: List<MediaItem.SubtitleConfiguration> = emptyList()): MediaItem =
    MediaItem.Builder()
        .setUri(url)
        .apply { if (hls) setMimeType(MimeTypes.APPLICATION_M3U8) }
        .setSubtitleConfigurations(subtitles)
        .build()

/**
 * Sous-titres posés à côté de la vidéo (écran Vidéos) : ajoutés aux pistes du
 * fichier, choisis dans l'onglet Sous-titres du menu pause. Téléchargés par
 * le même client HTTP que la vidéo (jeton d'appareil), en UTF-8.
 */
private fun sideSubtitles(info: PlayInfo, baseUrl: String): List<MediaItem.SubtitleConfiguration> =
    info.subtitles.map { sub ->
        MediaItem.SubtitleConfiguration.Builder(android.net.Uri.parse(baseUrl + sub.url))
            .setMimeType(sub.mime)
            .setLanguage(sub.language.ifBlank { null })
            .setLabel(sub.label)
            .setSelectionFlags(if ("forcés" in sub.label) C.SELECTION_FLAG_FORCED else 0)
            .build()
    }

/**
 * Message lisible, suivi du détail technique (code ExoPlayer, format du
 * fichier, direct ou remux) : utile pour comprendre ce qui coince.
 */
private fun describe(e: PlaybackException, container: String, remuxed: Boolean): String {
    val detail = listOfNotNull(
        e.errorCodeName,
        container.takeIf { it.isNotBlank() }?.let { "fichier .$it" },
        if (remuxed) "converti par Jellyfin" else "lecture directe",
    ).joinToString(" · ")
    return describe(e) + "\n\n" + detail
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

/** L'activité qui porte cet écran (le Context de Compose peut être une enveloppe). */
private tailrec fun android.content.Context.findActivity(): android.app.Activity? = when (this) {
    is android.app.Activity -> this
    is android.content.ContextWrapper -> baseContext.findActivity()
    else -> null
}
