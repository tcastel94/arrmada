package fr.arrmada.app.ui.player

import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.core.view.WindowInsetsControllerCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowCompat
import android.content.pm.ActivityInfo
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.data.TrackLanguageLogic
import fr.arrmada.app.data.TrackPreference
import fr.arrmada.app.data.TrickplayLogic
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.offset
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
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
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
import fr.arrmada.app.data.DolbyVisionLogic
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.DefaultQuality
import fr.arrmada.app.data.Quality
import fr.arrmada.app.data.QualityLogic
import fr.arrmada.app.data.RemoteCommand
import fr.arrmada.app.data.ScrobbleCast
import fr.arrmada.app.data.ScrobbleLogic
import fr.arrmada.app.data.ScrobbleSkip
import fr.arrmada.app.data.ScrobbleTrack
import fr.arrmada.app.ui.detail.techBadges
import fr.arrmada.app.data.SubtitleRequest
import fr.arrmada.app.data.SubtitleShiftLogic
import fr.arrmada.app.data.SubtitleResult
import fr.arrmada.app.data.PlaybackLogic
import fr.arrmada.app.data.PlayerKeyLogic
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.WatchStateUpdate
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive

// Lecteur en cours : ExoPlayer, pistes, sous-titres, qualité, ampli, télécommande
// (l'écran PlayerScreen, dans PlayerScreen.kt, prépare la lecture puis l'affiche).

@OptIn(UnstableApi::class)
@Composable
internal fun PlayerSurface(
    request: PlayRequest,
    info: PlayInfo,
    meta: PlaybackMeta?,
    trackPreference: TrackPreference?, // dernier choix du profil, null : règle automatique
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

    // Dolby Vision profil 5 sur un écran sans Dolby Vision : image violette en
    // lecture directe. On part alors d'emblée sur la conversion SDR de Jellyfin.
    val screenDolbyVision = remember { ScreenCapabilities.dolbyVision(context) }
    val sdrAtStart = remember { DolbyVisionLogic.startWithSdr(info, screenDolbyVision) }
    // Qualité de départ (ADR-012) : le Dolby Vision profil 5 d'abord, puis le
    // réglage de la TV (« 1080p » : Wi-Fi, câble lent…)
    val screenHdr10 = remember { ScreenCapabilities.hdr10(context) }
    val startQuality = remember { QualityLogic.initial(info, screenHdr10, screenDolbyVision, app.prefs.defaultQuality) }
    val reducedQuality = remember { QualityLogic.reduced(info, screenHdr10) } // le « 1080p » proposé ici
    // Flux lu (adresse, HLS ?) : change si l'on bascule en remux, en SDR ou en 1080p
    val initialSource = QualityLogic.source(info, startQuality)

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
        // Décodeurs d'Android d'abord (passthrough vers l'ampli intact), FFmpeg
        // ensuite : il ne sert que pour un son qu'Android ne sait pas décoder,
        // ou en secours quand son décodeur plante (voir onPlayerError).
        val renderers = DefaultRenderersFactory(context)
            .setExtensionRendererMode(DefaultRenderersFactory.EXTENSION_RENDERER_MODE_ON)
            .setEnableDecoderFallback(true) // autre décodeur Android si le premier ne démarre pas
        ExoPlayer.Builder(context, renderers)
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
                setMediaItem(mediaItem(app.api.baseUrl + initialSource.first, initialSource.second, sideSubtitles(info.subtitles, app.api.baseUrl)))
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
    // Aperçu en image (trickplay) : ←/→ déplacent une position visée, vignette
    // à l'appui ; la lecture ne saute qu'une fois, quand on lâche la touche
    var scrubTarget by remember { mutableStateOf<Long?>(null) }
    var duration by remember { mutableLongStateOf(info.duration * 1000L) }
    var tracks by remember { mutableStateOf(Tracks.EMPTY) }
    var playbackError by remember { mutableStateOf<String?>(null) }
    var remuxed by remember { mutableStateOf(info.mode == "remux" || startQuality != Quality.ORIGINAL) } // flux converti par Jellyfin
    var toneMapped by remember { mutableStateOf(startQuality == Quality.HD_SDR) } // image convertie en SDR (DV profil 5, 1080p SDR)
    // Qualité lue (menu pause › Qualité) ; « Original » : le direct, ou le remux
    // si le direct a échoué ; le DV profil 5 a-t-il imposé le SDR sur cet écran ?
    var quality by remember { mutableStateOf(startQuality) }
    var originalSource by remember { mutableStateOf(QualityLogic.source(info, Quality.ORIGINAL)) }
    var doviForcedSdr by remember { mutableStateOf(sdrAtStart) }
    // Coupures en pleine lecture (ADR-012) : 3 en 5 min → proposer le 1080p
    var readyOnce by remember { mutableStateOf(false) } // première image du flux en cours affichée
    var lastSeekAt by remember { mutableLongStateOf(0L) } // dernier saut ou changement de flux
    var rebuffers by remember { mutableStateOf(emptyList<Long>()) }
    var qualityDeclined by remember { mutableStateOf(false) } // « Non merci » : plus de proposition
    var qualityCard by remember { mutableStateOf<QualityCardKind?>(null) }
    var dolbyVisionWarned by remember { mutableStateOf(false) }
    var source by remember { mutableStateOf(initialSource) }
    // Sous-titres posés à côté du fichier (Bazarr…), complétés depuis le menu pause
    var sideSubs by remember { mutableStateOf(info.subtitles) }
    var subtitleBusy by remember { mutableStateOf(false) }
    var subtitleNote by remember { mutableStateOf<String?>(null) }
    // Décalage manuel des sous-titres, et piste à choisir une fois le flux rechargé
    var subtitleShiftMs by remember { mutableIntStateOf(0) }
    var pendingSubtitleLabel by remember { mutableStateOf<String?>(null) }
    // Pistes choisies d'office (VO + sous-titres FR, ou VF + forcés) : une
    // fois, au premier jeu de pistes ; ensuite, c'est le choix de l'utilisateur
    var autoTracksDone by remember { mutableStateOf(false) }
    val currentMeta by rememberUpdatedState(meta) // la fiche peut arriver après le lecteur
    val currentPreference by rememberUpdatedState(trackPreference)
    // Titre sous lequel ranger le choix de pistes (série entière, film, série maison)
    val trackScope = remember { TrackLanguageLogic.scope(request.kind, request.id, request.localSeries) }
    // Piste changée par l'utilisateur : à ranger dès que le lecteur l'a appliquée
    var saveTracksPending by remember { mutableStateOf(false) }
    // Le bouton central ouvre le menu à l'appui : son relâchement est avalé
    // (sinon il « clique » sur « Reprendre », qui a le focus, et relance aussitôt)
    var swallowOkUp by remember { mutableStateOf(false) }
    var softwareAudio by remember { mutableStateOf(false) } // son décodé par FFmpeg (secours)
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

    // Fin du défilement : un seul saut, 0,8 s après le dernier appui
    LaunchedEffect(scrubTarget) {
        val target = scrubTarget ?: return@LaunchedEffect
        delay(800)
        player.seekTo(target)
        position = target
        scrubTarget = null
    }

    /** ← / → : saut direct, ou défilement avec vignettes si Jellyfin en a généré. */
    fun seekBy(forward: Boolean, repeat: Int) {
        osdUntil = System.currentTimeMillis() + 3000
        if (TrickplayLogic.frame(info.trickplay, 0.0) == null) {
            if (forward) player.seekForward() else player.seekBack()
            return
        }
        scrubTarget = TrickplayLogic.scrub(scrubTarget ?: player.currentPosition, TrickplayLogic.step(forward, repeat), duration)
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

    /** Recharge le flux [url] (remux, SDR, nouveaux sous-titres) à la position [at]. */
    fun load(url: String, hls: Boolean, at: Long) {
        source = url to hls
        // Le nouveau flux remplit sa mémoire tampon : ce n'est pas une coupure
        readyOnce = false
        lastSeekAt = System.currentTimeMillis()
        player.setMediaItem(mediaItem(app.api.baseUrl + url, hls, sideSubtitles(sideSubs, app.api.baseUrl)), at)
        player.prepare()
    }

    /**
     * Menu pause › Qualité, ou carte « Passer en 1080p ? » : même position,
     * même état lecture / pause. Une conversion Jellyfin en cours est arrêtée
     * AVANT de lancer le nouveau flux : remux, SDR et 1080p partagent la même
     * session chez Jellyfin, l'arrêt après coup couperait aussi le nouveau.
     */
    fun setQuality(target: Quality) {
        if (target == quality) return
        val (url, hls) = if (target == Quality.ORIGINAL) originalSource else QualityLogic.source(info, target)
        if (url.isBlank()) return
        val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
        val wasPlaying = player.playWhenReady
        val stopFirst = remuxed && info.itemId.isNotBlank()
        quality = target
        toneMapped = target == Quality.HD_SDR
        remuxed = target != Quality.ORIGINAL || hls
        rebuffers = emptyList()
        Toast.makeText(context, QualityLogic.switchMessage(target), Toast.LENGTH_SHORT).show()
        if (!stopFirst) {
            load(url, hls, at)
            player.playWhenReady = wasPlaying
            return
        }
        player.stop() // plus aucune requête vers la conversion qu'on arrête
        uiScope.launch {
            runCatching { repository.stopRemux(info.itemId) }
            load(url, hls, at)
            player.playWhenReady = wasPlaying
        }
    }

    /** Carte de qualité : OK / « Passer en 1080p » (ou « Oui » à la seconde question). */
    fun acceptQualityCard() {
        when (qualityCard) {
            QualityCardKind.SUGGEST -> {
                reducedQuality?.let(::setQuality)
                // Une seule fois par TV : en faire le réglage par défaut ?
                val ask = app.prefs.defaultQuality == DefaultQuality.ORIGINAL && !app.prefs.qualityAsked
                qualityCard = if (ask) QualityCardKind.ALWAYS else null
            }
            QualityCardKind.ALWAYS -> {
                app.prefs.defaultQuality = DefaultQuality.HD_1080
                app.prefs.qualityAsked = true
                qualityCard = null
                Toast.makeText(context, "Cette TV lira en 1080p (modifiable dans Réglages)", Toast.LENGTH_LONG).show()
            }
            null -> Unit
        }
    }

    /** Carte de qualité : Retour / « Non merci » (la proposition ne revient plus de la séance). */
    fun declineQualityCard() {
        when (qualityCard) {
            QualityCardKind.SUGGEST -> qualityDeclined = true
            QualityCardKind.ALWAYS -> app.prefs.qualityAsked = true
            null -> Unit
        }
        qualityCard = null
    }

    // Menu pause → « Sous-titres FR » : film ou épisode de la médiathèque
    // seulement (Bazarr ne connaît pas les vidéos de l'écran Vidéos)
    val subtitleRequest = remember(request) {
        when (request.kind) {
            "movie" -> SubtitleRequest("movie", tmdbId = request.id)
            "episode" -> SubtitleRequest("episode", tvdbId = request.id, season = request.season, episode = request.episode)
            else -> null
        }?.takeIf { info.itemId.isNotBlank() }
    }

    fun downloadSubtitles() {
        val body = subtitleRequest ?: return
        if (subtitleBusy) return
        subtitleBusy = true
        subtitleNote = null
        uiScope.launch {
            val result = runCatching { repository.downloadSubtitles(info.itemId, body) }
                .getOrElse { SubtitleResult(message = subtitleError(it)) }
            subtitleBusy = false
            subtitleNote = result.message
            result.message?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
            if (result.subtitles.isNotEmpty() && result.subtitles.map { it.url } != sideSubs.map { it.url }) {
                sideSubs = result.subtitles
                // Même flux, sous-titres en plus ; la lecture reste en pause, le
                // français est choisi d'office
                load(source.first, source.second, player.currentPosition)
                (player.trackSelector as? DefaultTrackSelector)?.let {
                    // Réactivés : ils ont pu être coupés au lancement (VF sans forcés)
                    it.setParameters(
                        it.buildUponParameters()
                            .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                            .setPreferredTextLanguage("fr")
                    )
                }
            }
        }
    }

    // Menu pause › Sous-titres › « Resynchro auto » : Bazarr recale le .srt sur le son
    fun syncSubtitles() {
        val body = subtitleRequest ?: return
        if (subtitleBusy) return
        subtitleBusy = true
        subtitleNote = null
        uiScope.launch {
            val result = runCatching { repository.syncSubtitles(info.itemId, body) }
                .getOrElse { SubtitleResult(message = subtitleError(it)) }
            subtitleBusy = false
            subtitleNote = result.message
            result.message?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
            if (result.status == "ok" && result.subtitles.isNotEmpty()) {
                // Même adresse, fichier réécrit par Bazarr : « ?v= » force le lecteur à le relire
                val version = System.currentTimeMillis() / 1000
                sideSubs = result.subtitles.map { it.copy(url = it.url + "?v=$version") }
                subtitleShiftMs = 0
                pendingSubtitleLabel = sideSubs.firstOrNull { it.language == "fr" }?.label
                load(source.first, source.second, player.currentPosition)
            }
        }
    }

    // Menu pause › Sous-titres › −/+ 0,5 s : copie décalée servie par le serveur
    fun shiftSubtitles(deltaMs: Int) {
        val choice = trackChoices(tracks, C.TRACK_TYPE_TEXT).firstOrNull { it.selected }
        val format = choice?.group?.getTrackFormat(choice.index)
        if (format == null) {
            Toast.makeText(context, "Choisis d’abord une piste de sous-titres", Toast.LENGTH_SHORT).show()
            return
        }
        val forced = (format.selectionFlags and C.SELECTION_FLAG_FORCED) != 0
        val src = SubtitleShiftLogic.source(format.label.orEmpty(), format.language, forced, sideSubs, info.embeddedSubtitles)
        if (src == null) {
            Toast.makeText(context, "Cette piste (image) ne peut pas être décalée", Toast.LENGTH_LONG).show()
            return
        }
        val ms = (subtitleShiftMs + deltaMs).coerceIn(-600_000, 600_000)
        subtitleShiftMs = ms
        val shifted = if (ms == 0) {
            null
        } else {
            src.copy(url = SubtitleShiftLogic.shiftedUrl(src.url, ms), label = SubtitleShiftLogic.shiftedLabel(src.label, ms))
        }
        sideSubs = sideSubs.filterNot { SubtitleShiftLogic.baseLabel(it.label) != it.label } + listOfNotNull(shifted)
        // Après rechargement : la copie décalée, ou (retour à zéro) la piste d'origine
        pendingSubtitleLabel = shifted?.label ?: src.label.takeIf { s -> sideSubs.any { it.label == s } }
        if (pendingSubtitleLabel == null) {
            (player.trackSelector as? DefaultTrackSelector)?.let {
                it.setParameters(it.buildUponParameters().setPreferredTextLanguage(format.language))
            }
        }
        load(source.first, source.second, player.currentPosition)
        Toast.makeText(context, if (ms == 0) "Sous-titres d’origine" else "Sous-titres décalés de ${SubtitleShiftLogic.format(ms)}", Toast.LENGTH_SHORT).show()
    }

    LaunchedEffect(Unit) {
        if (sdrAtStart) {
            Toast.makeText(context, DV_SDR_MESSAGE, Toast.LENGTH_LONG).show()
        } else if (startQuality != Quality.ORIGINAL) {
            // Réglage « 1080p » de la TV : on le dit, l'original reste au menu pause
            Toast.makeText(context, QualityLogic.switchMessage(startQuality), Toast.LENGTH_SHORT).show()
        }
    }

    // Carte de qualité : non bloquante, elle s'efface seule après 20 s (sans
    // réponse : pas un refus, mais le compte des coupures repart de zéro)
    LaunchedEffect(qualityCard) {
        if (qualityCard == null) return@LaunchedEffect
        delay(QUALITY_CARD_MS)
        if (qualityCard == QualityCardKind.ALWAYS) app.prefs.qualityAsked = true
        qualityCard = null
        rebuffers = emptyList()
    }

    // Écran d'appoint (tablette sous la TV) : « lecture en cours » envoyée au
    // serveur, comme le faisait l'add-on Kodi (affiche, heure de fin, mode
    // séance de Fully Kiosk). Pas depuis un téléphone : la tablette du salon
    // afficherait ce qu'on regarde ailleurs.
    var scrobbleStarted by remember { mutableStateOf(false) }
    val sendScrobble by rememberUpdatedState<(String, Boolean) -> Unit> { event, ended ->
        if (!touch) {
            val what = ScrobbleLogic.identity(
                request.kind, request.id, request.season, request.episode,
                title = meta?.title ?: info.title.orEmpty(),
                subtitle = meta?.subtitle,
                localSeries = request.localSeries > 0,
            )
            val total = (player.duration.takeIf { it > 0 } ?: duration) / 1000.0
            val positionS = player.currentPosition / 1000.0
            val audioChoices = trackChoices(tracks, C.TRACK_TYPE_AUDIO)
            val textChoices = trackChoices(tracks, C.TRACK_TYPE_TEXT)
            // Ce que la tablette affiche en plus pendant la séance
            val rich = what.copy(
                video = ScrobbleLogic.videoLabel(selectedVideoFormat(tracks)?.height, techBadges(meta?.file), info.videoRange, toneMapped),
                audio = audioChoices.firstOrNull { it.selected }
                    ?.let { listOf(it.label, it.detail).filter { part -> part.isNotBlank() }.joinToString(" · ") }.orEmpty(),
                subtitleTrack = textChoices.firstOrNull { it.selected }?.label.orEmpty(),
                chapter = ScrobbleLogic.chapterAt(info.chapters, positionS),
                creditsAt = if (total > 0) PlaybackLogic.creditsStart(info, total) ?: 0.0 else 0.0,
                nextUp = upNext?.let { "${it.code} · ${it.title}" }.orEmpty(),
                skips = skips.map { ScrobbleSkip(it.kind, PlaybackLogic.skipLabel(it), it.start, it.end) },
                overview = meta?.overview ?: info.overview.orEmpty(),
                metaLine = meta?.metaLine.orEmpty(),
                cast = meta?.cast.orEmpty().take(8).map { ScrobbleCast(it.name, it.character, it.photo.orEmpty(), it.tmdbId) },
                subtitleTracks = textChoices.mapIndexed { i, c -> ScrobbleTrack(i, c.label, c.detail, c.selected) },
                audioTracks = audioChoices.mapIndexed { i, c -> ScrobbleTrack(i, c.label, c.detail, c.selected) },
                remote = true,
                subtitleTools = subtitleRequest != null,
                subtitleBusy = subtitleBusy,
                subtitleNote = subtitleNote.orEmpty(),
                subtitleShiftMs = subtitleShiftMs,
            )
            val payload = ScrobbleLogic.payload(
                event, rich, positionS, total, paused = !player.playWhenReady, ended = ended,
            )
            app.appScope.launch { runCatching { repository.scrobble(payload) } }
        }
    }

    /**
     * Langues au lancement (TrackLanguageLogic) : titre étranger avec
     * sous-titres français → VO + sous-titres FR complets ; film français
     * (ou pas de sous-titres FR) → piste française + sous-titres « forcés »
     * français s'il y en a. Les préférences du lecteur suivent le même choix,
     * pour qu'un rechargement du flux (qualité, remux) le garde.
     */
    fun applyLanguagePlan(newTracks: Tracks) {
        val audios = trackChoices(newTracks, C.TRACK_TYPE_AUDIO)
        val texts = trackChoices(newTracks, C.TRACK_TYPE_TEXT)
        val remembered = currentPreference?.let {
            TrackLanguageLogic.Remembered(
                audio = it.audioLanguage.ifBlank { null },
                subtitle = it.subtitleLanguage.ifBlank { null },
                subtitleForced = it.subtitleForced,
            )
        }
        val plan = TrackLanguageLogic.plan(
            currentMeta?.originalLanguage,
            audios.map { TrackLanguageLogic.Audio(it.group?.getTrackFormat(it.index)?.language, it.supported) },
            texts.map { choice ->
                val format = choice.group?.getTrackFormat(choice.index)
                TrackLanguageLogic.Text(
                    language = format?.language,
                    forced = format != null && (format.selectionFlags and C.SELECTION_FLAG_FORCED) != 0,
                    supported = choice.supported,
                    isDefault = format != null && (format.selectionFlags and C.SELECTION_FLAG_DEFAULT) != 0,
                    label = format?.label,
                )
            },
            remembered,
        )
        player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
            .setPreferredAudioLanguages(*TrackLanguageLogic.preferredAudioLanguages(plan).toTypedArray())
            // Sous-titres complets : leur langue préférée (Media3 écarte alors les forcés) ;
            // sinon aucune préférence : seuls les forcés de la langue entendue s'affichent
            .setPreferredTextLanguage(plan.textLanguage)
            .build()
        plan.audio?.let { audios.getOrNull(it) }?.let { selectTrack(player, C.TRACK_TYPE_AUDIO, it) }
        // Pas de sous-titre voulu : coupés (pas de piste « par défaut » en anglais sur la VF)
        selectTrack(player, C.TRACK_TYPE_TEXT, plan.text?.let { texts.getOrNull(it) })
    }

    /** Piste choisie par l'utilisateur (menu pause, tablette) : appliquée, puis rangée pour ce profil. */
    fun userSelectTrack(type: Int, choice: TrackChoice?) {
        selectTrack(player, type, choice)
        saveTracksPending = trackScope != null
    }

    /** Range ce qui est lu (audio, sous-titres ou « coupés ») : l'épisode suivant le reprendra. */
    fun saveTrackChoice(newTracks: Tracks) {
        val scope = trackScope ?: return
        val audio = trackChoices(newTracks, C.TRACK_TYPE_AUDIO).firstOrNull { it.selected }
            ?.let { it.group?.getTrackFormat(it.index) }
        val text = trackChoices(newTracks, C.TRACK_TYPE_TEXT).firstOrNull { it.selected }
            ?.let { it.group?.getTrackFormat(it.index) }
        val remembered = TrackLanguageLogic.remember(
            audioLanguage = audio?.language,
            subtitlesOn = text != null,
            subtitleLanguage = text?.language,
            subtitleForced = text != null &&
                TrackLanguageLogic.isForced((text.selectionFlags and C.SELECTION_FLAG_FORCED) != 0, text.label),
        )
        val preference = TrackPreference(
            found = true,
            audioLanguage = remembered.audio.orEmpty(),
            subtitleLanguage = remembered.subtitle.orEmpty(),
            subtitleForced = remembered.subtitleForced,
        )
        // En tâche de fond (survit à la sortie du lecteur) ; un échec ne gêne pas la lecture
        app.appScope.launch { runCatching { repository.saveTrackPreference(scope, preference) } }
    }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onTracksChanged(newTracks: Tracks) {
                tracks = newTracks
                // Premier jeu de pistes du fichier : langues choisies d'office
                if (!autoTracksDone && pendingSubtitleLabel == null && newTracks.groups.any { it.type == C.TRACK_TYPE_AUDIO }) {
                    autoTracksDone = true
                    applyLanguagePlan(newTracks)
                }
                // Choix de l'utilisateur appliqué par le lecteur : on le range
                if (saveTracksPending) {
                    saveTracksPending = false
                    saveTrackChoice(newTracks)
                }
                // Flux rechargé (décalage, resynchro) : la piste voulue, dès qu'elle apparaît
                pendingSubtitleLabel?.let { wanted ->
                    trackChoices(newTracks, C.TRACK_TYPE_TEXT)
                        .firstOrNull { it.group?.getTrackFormat(it.index)?.label == wanted }
                        ?.let {
                            pendingSubtitleLabel = null
                            selectTrack(player, C.TRACK_TYPE_TEXT, it)
                        }
                }
                // Piste changée (menu pause ou tablette) : la tablette suit aussitôt
                if (scrobbleStarted) sendScrobble("progress", false)
                // Filet de sécurité : la piste vidéo se révèle Dolby Vision profil 5
                // alors que l'écran ne le gère pas (serveur Jellyfin trop ancien
                // pour l'annoncer, ou remux) → conversion SDR là où on en était.
                val video = selectedVideoFormat(newTracks) ?: return
                if (toneMapped || screenDolbyVision || !DolbyVisionLogic.withoutFallback(video.sampleMimeType, video.codecs)) return
                if (info.sdrStream.isNotBlank()) {
                    toneMapped = true
                    remuxed = true
                    quality = Quality.HD_SDR
                    doviForcedSdr = true
                    val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
                    load(info.sdrStream, hls = true, at = at)
                    player.play()
                    Toast.makeText(context, DV_SDR_MESSAGE, Toast.LENGTH_LONG).show()
                } else if (!dolbyVisionWarned) {
                    // Fichier de l'écran Vidéos : pas de Jellyfin pour le convertir
                    dolbyVisionWarned = true
                    Toast.makeText(
                        context,
                        "Dolby Vision profil 5 : couleurs fausses sur cet écran",
                        Toast.LENGTH_LONG,
                    ).show()
                }
            }

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY && player.duration > 0) duration = player.duration
                if (state == Player.STATE_READY) readyOnce = true
                // Attente de chargement en pleine lecture : le réseau suit-il le fichier ?
                if (state == Player.STATE_BUFFERING) {
                    val now = System.currentTimeMillis()
                    if (QualityLogic.isRebuffer(player.playWhenReady, readyOnce, now, lastSeekAt)) {
                        rebuffers = QualityLogic.record(rebuffers, now)
                        if (qualityCard == null &&
                            QualityLogic.shouldSuggest(rebuffers, now, quality, reducedQuality, qualityDeclined, info.bitrate)
                        ) {
                            qualityCard = QualityCardKind.SUGGEST
                        }
                    }
                }
                // Première image prête : la séance commence (une seule fois, même
                // si l'on bascule ensuite en remux ou en SDR)
                if (state == Player.STATE_READY && !scrobbleStarted) {
                    scrobbleStarted = true
                    sendScrobble("play", false)
                }
                if (state == Player.STATE_ENDED) onEnded()
            }

            // Saut (avance rapide, chapitre, intro passée…) : l'attente qui suit n'est pas une coupure
            override fun onPositionDiscontinuity(oldPosition: Player.PositionInfo, newPosition: Player.PositionInfo, reason: Int) {
                if (reason == Player.DISCONTINUITY_REASON_SEEK || reason == Player.DISCONTINUITY_REASON_SEEK_ADJUSTMENT) {
                    lastSeekAt = System.currentTimeMillis()
                }
            }

            // Pause / reprise demandées (et non les attentes de chargement)
            override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
                if (scrobbleStarted) sendScrobble(if (playWhenReady) "resume" else "pause", false)
            }

            override fun onPlayerError(e: PlaybackException) {
                // Décodeur audio d'Android en échec (ex. MP3 d'un vieil .avi, dont
                // les blocs ne tombent pas sur les trames) : on le met de côté et
                // FFmpeg, plus tolérant, reprend le son là où on en était.
                if (!softwareAudio && audioDecoderFailed(e)) {
                    val audio = (0 until player.rendererCount).filter { player.getRendererType(it) == C.TRACK_TYPE_AUDIO }
                    val selector = player.trackSelector as? DefaultTrackSelector
                    if (audio.size > 1 && selector != null) {
                        softwareAudio = true
                        val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
                        selector.setParameters(selector.buildUponParameters().setRendererDisabled(audio.first(), true))
                        player.prepare()
                        player.seekTo(at)
                        player.play()
                        Toast.makeText(context, "Son décodé par l’appli (format audio mal géré par Android)", Toast.LENGTH_LONG).show()
                        return
                    }
                }
                // Fichier illisible en direct : on retente une fois en remux,
                // là où on en était
                if (!remuxed && info.remuxStream.isNotBlank() && e.errorCode in REMUX_RETRY) {
                    remuxed = true
                    originalSource = info.remuxStream to true // « Original » = ce remux désormais
                    val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
                    load(info.remuxStream, hls = true, at = at)
                    player.play()
                    Toast.makeText(context, "Format ${info.container.ifBlank { "inconnu" }} : conversion par Jellyfin…", Toast.LENGTH_LONG).show()
                    return
                }
                playbackError = describe(
                    e,
                    info.container,
                    when {
                        toneMapped -> "converti en SDR par Jellyfin"
                        remuxed -> "converti par Jellyfin"
                        else -> "lecture directe"
                    },
                )
            }
        }
        player.addListener(listener)
        onDispose {
            save(false)
            if (scrobbleStarted) sendScrobble("stop", finished)
            player.removeListener(listener)
            player.release()
            // Remux : Jellyfin arrête la conversion (sinon elle tourne à vide)
            if (remuxed) app.appScope.launch { runCatching { repository.stopRemux(info.itemId) } }
        }
    }

    // Position affichée + sauvegarde toutes les 30 s pendant la lecture
    LaunchedEffect(player) {
        var lastSave = System.currentTimeMillis()
        var lastScrobble = System.currentTimeMillis()
        while (true) {
            position = player.currentPosition
            if (player.isPlaying && System.currentTimeMillis() - lastSave > 30_000) {
                save(false)
                lastSave = System.currentTimeMillis()
            }
            // Relevé pour l'écran d'appoint (il fait avancer la barre entre deux)
            if (player.isPlaying && scrobbleStarted && System.currentTimeMillis() - lastScrobble > ScrobbleLogic.PROGRESS_EVERY_MS) {
                sendScrobble("progress", false)
                lastScrobble = System.currentTimeMillis()
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
        swallowOkUp = false
        showMenu = false
        player.play()
        runCatching { keyFocus.requestFocus() }
    }

    // ── Télécommande tactile : commandes de la tablette de la pièce ──
    val onRemote by rememberUpdatedState<(RemoteCommand) -> Unit> { command ->
        when (command.action) {
            "toggle" -> if (player.playWhenReady) pause() else resume()
            "pause" -> if (player.playWhenReady) pause()
            "play" -> if (!player.playWhenReady) resume()
            "seek" -> command.seconds?.let {
                player.seekTo((player.currentPosition + it * 1000L).coerceAtLeast(0))
                osdUntil = System.currentTimeMillis() + 3000
            }
            // Intro / récap en cours → sa fin ; sinon carte « Épisode suivant » → l'enchaîner
            "skip" -> {
                val at = player.currentPosition / 1000.0
                val segment = skips.firstOrNull { at >= it.start && at < it.end }
                if (segment != null) player.seekTo((segment.end * 1000).toLong()) else if (showUpNext) playNext()
            }
            "next" -> if (upNext != null) playNext()
            // Outils sous-titres (feuille Sous-titres de la tablette)
            "subtitle_download" -> downloadSubtitles()
            "subtitle_sync" -> syncSubtitles()
            "subtitle_shift" -> command.seconds?.let { shiftSubtitles(it) } // valeur en ms
            "track" -> command.track?.let { (kind, index) ->
                val type = if (kind == "audio") C.TRACK_TYPE_AUDIO else C.TRACK_TYPE_TEXT
                if (index < 0) {
                    if (type == C.TRACK_TYPE_TEXT) userSelectTrack(type, null)
                } else {
                    trackChoices(tracks, type).getOrNull(index)?.takeIf { it.supported }?.let { userSelectTrack(type, it) }
                }
            }
        }
        if (scrobbleStarted) sendScrobble("progress", false)
    }
    // Bazarr travaille / a répondu, décalage changé : la tablette suit aussitôt
    LaunchedEffect(subtitleBusy, subtitleNote, subtitleShiftMs) {
        if (scrobbleStarted) sendScrobble("progress", false)
    }
    LaunchedEffect(Unit) {
        if (touch) return@LaunchedEffect // téléphone : pas de tablette qui le pilote
        var after = -1L
        while (true) {
            val page = runCatching { repository.remote(after) }.getOrNull()
            if (page == null) {
                delay(5_000) // serveur injoignable : on réessaie sans insister
                continue
            }
            after = page.lastId
            page.commands.forEach { onRemote(it) }
        }
    }

    // Retour : carte « Épisode suivant » → l'écarter ; pendant la lecture →
    // pause et menu ; dans le menu → quitter
    BackHandler {
        when {
            showUpNext -> upNextDismissed = true
            qualityCard != null && !showMenu -> declineQualityCard()
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
                val code = event.key.nativeKeyCode
                val ok = PlayerKeyLogic.isConfirm(code)
                if (ok && event.type == KeyEventType.KeyUp && swallowOkUp) {
                    swallowOkUp = false
                    return@onPreviewKeyEvent true
                }
                if (showMenu || playbackError != null || event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                // Quelle action pour cette touche (règle dans PlayerKeyLogic, testée), puis on l'exécute
                val screen = PlayerKeyLogic.Screen(
                    upNextShown = showUpNext,
                    qualityCardShown = qualityCard != null,
                    skipShown = activeSkip != null,
                    hasNext = upNext != null,
                )
                when (PlayerKeyLogic.action(code, screen)) {
                    PlayerKeyLogic.Action.PLAY_NEXT -> { playNext(); true }
                    PlayerKeyLogic.Action.ACCEPT_QUALITY -> { acceptQualityCard(); true }
                    PlayerKeyLogic.Action.SKIP_SEGMENT -> {
                        activeSkip?.let { player.seekTo((it.end * 1000).toLong()) }
                        true
                    }
                    PlayerKeyLogic.Action.PAUSE_MENU -> { swallowOkUp = ok; pause(); true }
                    PlayerKeyLogic.Action.PLAY -> { player.play(); true }
                    PlayerKeyLogic.Action.SEEK_BACK -> { seekBy(forward = false, repeat = event.nativeKeyEvent.repeatCount); true }
                    PlayerKeyLogic.Action.SEEK_FORWARD -> { seekBy(forward = true, repeat = event.nativeKeyEvent.repeatCount); true }
                    PlayerKeyLogic.Action.SHOW_BAR -> { osdUntil = System.currentTimeMillis() + 3000; true }
                    PlayerKeyLogic.Action.EXIT -> { onExit(); true }
                    PlayerKeyLogic.Action.NONE -> false
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
                val shown = scrubTarget ?: position // pendant le défilement : l'instant visé
                val fraction = if (duration > 0) (shown.toFloat() / duration).coerceIn(0f, 1f) else 0f
                val trickplay = info.trickplay
                if (scrubTarget != null && trickplay != null) {
                    // Vignette au-dessus de l'instant visé, sans sortir de l'écran
                    BoxWithConstraints(Modifier.fillMaxWidth().padding(bottom = 10.dp)) {
                        val thumb = 240.dp
                        val x = (maxWidth * fraction - thumb / 2).coerceIn(0.dp, (maxWidth - thumb).coerceAtLeast(0.dp))
                        Column(Modifier.offset(x = x)) {
                            TrickplayThumb(trickplay, shown / 1000.0, app.api::absolute, width = thumb)
                            Text(
                                formatClock(shown / 1000),
                                style = MaterialTheme.typography.titleMedium,
                                modifier = Modifier.padding(top = 4.dp).align(Alignment.CenterHorizontally),
                            )
                        }
                    }
                }
                ProgressBar(fraction, Modifier.fillMaxWidth(), height = 4.dp)
                Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
                    Text(formatClock(shown / 1000), style = MaterialTheme.typography.labelLarge)
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

        // Carte « Le réseau ne suit pas ce fichier… Passer en 1080p ? » (ADR-012)
        AnimatedVisibility(
            visible = qualityCard != null && !showMenu && !showUpNext,
            enter = fadeIn() + slideInHorizontally { it },
            exit = fadeOut() + slideOutHorizontally { it },
            modifier = Modifier.align(Alignment.BottomEnd).padding(end = gutter, bottom = 48.dp),
        ) {
            when (qualityCard) {
                QualityCardKind.SUGGEST -> QualityCard(
                    QualityLogic.suggestMessage(info.bitrate),
                    accept = "Passer en 1080p",
                    decline = "Non merci",
                    onAccept = ::acceptQualityCard,
                    onDecline = ::declineQualityCard,
                )
                QualityCardKind.ALWAYS -> QualityCard(
                    "Toujours lire en 1080p sur cette TV ?",
                    accept = "Oui, toujours",
                    decline = "Non",
                    onAccept = ::acceptQualityCard,
                    onDecline = ::declineQualityCard,
                )
                null -> Unit
            }
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
                onSelectTrack = { type, choice -> userSelectTrack(type, choice) },
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
                subtitleDownload = SubtitleDownload(
                    busy = subtitleBusy,
                    note = subtitleNote,
                    onClick = subtitleRequest?.let { ::downloadSubtitles },
                    onSync = subtitleRequest?.let { ::syncSubtitles },
                    onShift = ::shiftSubtitles,
                    shiftMs = subtitleShiftMs,
                ),
                quality = QualityChoice(
                    options = QualityLogic.options(
                        info,
                        screenHdr10,
                        // Format de l'original : la piste lue si c'est lui, sinon la fiche du titre
                        originalFormat = ScrobbleLogic.videoLabel(
                            selectedVideoFormat(tracks)?.height?.takeIf { quality == Quality.ORIGINAL },
                            techBadges(meta?.file),
                            info.videoRange,
                            toneMapped = false,
                        ),
                        doviForcedSdr = doviForcedSdr,
                    ),
                    current = quality,
                    onSelect = ::setQuality,
                ),
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
