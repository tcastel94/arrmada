package fr.arrmada.app.ui.player

import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.data.TrackLanguageLogic
import fr.arrmada.app.data.TrackPreference
import fr.arrmada.app.data.TrickplayLogic
import fr.arrmada.app.data.TraktLogic
import fr.arrmada.app.data.TraktStep
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.annotation.OptIn
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.nativeKeyCode
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.C
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.ui.PlayerView
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.data.SoundAdvisor
import fr.arrmada.app.data.DolbyVisionLogic
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.HlsAudioLogic
import fr.arrmada.app.data.Quality
import fr.arrmada.app.data.QualityLogic
import fr.arrmada.app.data.RemoteCommand
import fr.arrmada.app.data.ScrobbleLogic
import fr.arrmada.app.data.StreamSwitchLogic
import fr.arrmada.app.ui.detail.techBadges
import fr.arrmada.app.data.PlaybackLogic
import fr.arrmada.app.data.PlayerKeyLogic
import fr.arrmada.app.ui.components.MessageScreen
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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

    // Téléphone / tablette : plein écran, à l'horizontale, pendant la lecture (PlayerSetup.kt)
    LandscapeFullscreen(touch)

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
    // Lecture convertie dès le départ (réglage « 1080p » de la TV, remux .m2ts /
    // .iso, SDR) : Jellyfin ne mettra qu'une piste audio dans son flux, la
    // règle des langues d'office (TrackLanguageLogic : dernier choix du profil,
    // sinon VO + sous-titres FR, sinon VF) se décide donc ici, sur les pistes du
    // serveur, avant de préparer le lecteur (HlsAudioLogic.indexAtStart).
    // La fiche ([meta]) et le dernier choix du profil ([trackPreference]) sont
    // lus par PlayerScreen AVANT de créer cet écran (3 s au plus) : on prend ce
    // qui est là, comme la lecture directe prend ses pistes d'office au premier
    // jeu de pistes. S'ils arrivent après (serveur lent), on ne recharge pas le
    // flux pour autant : la conversion repartirait de zéro, coupure visible,
    // pour une fiche en retard ; la piste par défaut de Jellyfin joue et le
    // panneau Audio permet d'en changer. Null : rien à demander.
    val initialHlsAudio = remember {
        if (!initialSource.second) {
            null
        } else {
            // Sous-titres que le flux converti aura : ceux posés à côté du fichier et
            // les pistes texte du MKV, posées à côté elles aussi (StreamSwitchLogic)
            val subs = StreamSwitchLogic.sideloaded(hls = true, side = info.subtitles, embedded = info.embeddedSubtitles)
            HlsAudioLogic.indexAtStart(info.audioTracks, meta?.originalLanguage, subs, TrackLanguageLogic.remembered(trackPreference))
        }
    }

    // ── Création du lecteur (une fois) ──
    val player = remember { createPlayer(context, app) } // PlayerSetup.kt

    var showMenu by remember { mutableStateOf(false) }
    // Ampli de la pièce et son conseillé (enceintes × piste en cours) : RoomSound.kt
    val roomSound = remember { RoomSound(app, repository, context, uiScope, touch) }
    // Ampli relu à l'ouverture du menu pause (onglet « Ampli ») et après chaque commande
    LaunchedEffect(showMenu, roomSound.ampRead) {
        if (!showMenu && roomSound.ampRead == 0) return@LaunchedEffect
        roomSound.readAmp()
    }
    LaunchedEffect(Unit) { roomSound.readRoom() }
    var osdUntil by remember { mutableLongStateOf(0L) }
    var position by remember { mutableLongStateOf(request.startSeconds * 1000L) }
    // Aperçu en image (trickplay) : ←/→ déplacent une position visée, vignette
    // à l'appui ; la lecture ne saute qu'une fois, quand on lâche la touche
    var scrubTarget by remember { mutableStateOf<Long?>(null) }
    var duration by remember { mutableLongStateOf(info.duration * 1000L) }
    var tracks by remember { mutableStateOf(Tracks.EMPTY) }
    // Outils Sous-titres (Bazarr, resynchro, décalage) et leur état : SubtitleTools.kt
    val subtitles = remember { SubtitleTools(info, request, player, repository, uiScope, context) }
    // Choix des pistes (langues d'office, mémoire par profil) : TrackChooser.kt
    val trackChooser = remember { TrackChooser(player, request, repository, app.appScope) }
    // Pistes texte extraites par Jellyfin, qui peuvent répondre dans des minutes :
    // demandées en arrière-plan avec le client patient de l'API, gardées en local
    // (LateSubtitleFetcher)
    val lateSubtitles = remember { LateSubtitleFetcher(app.api.slowHttp, app.api.baseUrl, uiScope, context.cacheDir) }
    // Flux lu, qualité, piste audio du flux converti, reprises automatiques : StreamSwitcher.kt
    val streams = remember {
        StreamSwitcher(
            info, request, player, app, repository, uiScope, context, subtitles, trackChooser, lateSubtitles,
            startQuality, reducedQuality, initialSource, initialHlsAudio, sdrAtStart, screenDolbyVision,
        )
    }
    // Flux converti : les pistes du serveur pour le panneau Audio et la tablette
    // (le lecteur n'en voit qu'une) ; vide en lecture directe
    val hlsChoices = remember(streams.source, streams.hlsAudio) {
        if (streams.source.second) HlsAudioLogic.choices(info.audioTracks, streams.hlsAudio, ::languageName) else emptyList()
    }
    val currentMeta by rememberUpdatedState(meta) // la fiche peut arriver après le lecteur
    val currentPreference by rememberUpdatedState(trackPreference)
    // Le bouton central ouvre le menu à l'appui : son relâchement est avalé
    // (sinon il « clique » sur « Reprendre », qui a le focus, et relance aussitôt)
    var swallowOkUp by remember { mutableStateOf(false) }
    var finished by remember { mutableStateOf(false) } // fin enregistrée (vu)
    // Trakt (ADR-022) : notes à proposer en fin de lecture (vide : profil sans compte Trakt)
    var traktSteps by remember { mutableStateOf<List<TraktStep>>(emptyList()) }
    var rating by remember { mutableStateOf<RatingSession?>(null) }
    var upNextDismissed by remember { mutableStateOf(false) }
    var countdown by remember { mutableIntStateOf(PlaybackLogic.UP_NEXT_SECONDS) }
    val keyFocus = remember { FocusRequester() }

    val sound = remember(tracks, meta) { selectedSound(tracks, meta?.file?.audioCodec) }
    val advice = SoundAdvisor.advise(if (roomSound.hasAmp) roomSound.layout else null, sound, screenName = if (touch) "l’appareil" else "la TV")

    // Décodage auto : dès que le son du film est connu (ou change de piste),
    // l'ampli prend le programme conseillé, une fois le préréglage terminé
    LaunchedEffect(advice.program, roomSound.autoSound, roomSound.hasAmp) { roomSound.autoProgram(advice, presetDone) }

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
        val update = watchStateUpdate(request, info, meta, pos, total, watched) ?: return
        app.appScope.launch { runCatching { repository.saveWatchState(update) } }
    }

    /**
     * Quitte le titre (épisode suivant, fin, retour) : s'il a été vu jusqu'au
     * bout et que le profil a un compte Trakt, la carte de note passe d'abord.
     */
    fun leave(after: () -> Unit) {
        if (rating != null) return // carte déjà ouverte : elle enchaînera elle-même
        saveProgress() // « vu » si l'on a dépassé 90 %
        if (finished && traktSteps.isNotEmpty()) {
            player.pause()
            showMenu = false // depuis « Quitter » du menu pause : la carte prend toute la place
            rating = RatingSession(traktSteps, 0, after)
        } else {
            after()
        }
    }

    fun playNext() {
        val next = upNext ?: return
        saveProgress(done = true)
        leave { onPlayNext(next.request) }
    }

    // Le lecteur et ses écouteurs sont créés une seule fois : ils appellent
    // toujours la DERNIÈRE version de ces actions (la fiche et l'épisode
    // suivant arrivent après le démarrage de la lecture).
    val save by rememberUpdatedState<(Boolean) -> Unit> { done -> saveProgress(done) }
    val onEnded by rememberUpdatedState {
        saveProgress(done = true)
        val next = upNext
        leave { if (next != null && !upNextDismissed) onPlayNext(next.request) else onExit() }
    }

    // Trakt : ce qu'il faudra proposer de noter, demandé dès le début (rien d'affiché pendant la lecture)
    LaunchedEffect(Unit) {
        if (!TraktLogic.eligible(request.kind, request.id, request.localSeries > 0)) return@LaunchedEffect
        runCatching { repository.traktPrompt(request.kind, request.id, request.season, request.episode) }
            .onSuccess { prompt -> if (prompt.linked) traktSteps = prompt.steps }
    }

    /** Envoie la note de l'étape en cours, puis passe à la suivante (ou quitte). */
    fun rate(value: Int?) {
        val session = rating ?: return
        val step = session.steps[session.index]
        if (value != null) {
            val title = currentMeta?.title ?: info.title.orEmpty()
            val body = TraktLogic.body(step, value, request.kind, request.id, request.season, request.episode, title)
            app.appScope.launch {
                val message = runCatching { repository.traktRate(body).message }
                    .getOrElse { it.message ?: "Note non envoyée à Trakt" }
                // appScope travaille hors du fil de l'écran : le message s'affiche sur ce dernier
                withContext(Dispatchers.Main) { Toast.makeText(context, message, Toast.LENGTH_SHORT).show() }
            }
        }
        if (session.index + 1 < session.steps.size) {
            rating = session.copy(index = session.index + 1)
        } else {
            rating = null
            session.after()
        }
    }

    // Premier flux, par load() : une lecture convertie dès le départ (réglage
    // « 1080p » de la TV, remux .m2ts / .iso, SDR) pose les pistes texte du
    // fichier à côté du flux, Jellyfin peut encore être en train de les extraire
    LaunchedEffect(Unit) { streams.load(initialSource.first, initialSource.second, request.startSeconds * 1000L, Tracks.EMPTY) }

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
    LaunchedEffect(streams.qualityCard) {
        if (streams.qualityCard == null) return@LaunchedEffect
        delay(QUALITY_CARD_MS)
        if (streams.qualityCard == QualityCardKind.ALWAYS) app.prefs.qualityAsked = true
        streams.qualityCard = null
        streams.rebuffers = emptyList()
    }

    // Écran d'appoint (tablette sous la TV) : « lecture en cours » envoyée au
    // serveur, comme le faisait l'add-on Kodi (affiche, heure de fin, mode
    // séance de Fully Kiosk). Pas depuis un téléphone : la tablette du salon
    // afficherait ce qu'on regarde ailleurs.
    var scrobbleStarted by remember { mutableStateOf(false) }
    val sendScrobble by rememberUpdatedState<(String, Boolean) -> Unit> { event, ended ->
        if (!touch) {
            val payload = scrobblePayload(
                event, ended, request, info, meta, player, duration, tracks, hlsChoices, streams.toneMapped, upNext, skips, subtitles,
            )
            app.appScope.launch { runCatching { repository.scrobble(payload) } }
        }
    }

    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onTracksChanged(newTracks: Tracks) {
                tracks = newTracks
                // Langues d'office, choix rangé, sous-titres attendus : StreamSwitcher.onTracksChanged
                streams.onTracksChanged(newTracks, currentMeta?.originalLanguage, currentPreference)
                // Piste changée (menu pause ou tablette) : la tablette suit aussitôt
                if (scrobbleStarted) sendScrobble("progress", false)
                // Image absente ou Dolby Vision profil 5 sur cet écran : filets de sécurité
                streams.checkVideo(newTracks)
            }

            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY && player.duration > 0) duration = player.duration
                if (state == Player.STATE_READY) streams.readyOnce = true
                // Attente de chargement en pleine lecture : le réseau suit-il le fichier ?
                if (state == Player.STATE_BUFFERING) streams.onBuffering()
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
                    streams.lastSeekAt = System.currentTimeMillis()
                }
            }

            // Pause / reprise demandées (et non les attentes de chargement)
            override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
                if (scrobbleStarted) sendScrobble(if (playWhenReady) "resume" else "pause", false)
            }

            // Reprise automatique (son par FFmpeg, image réencodée, remux) ou message : StreamSwitcher
            override fun onPlayerError(e: PlaybackException) = streams.onPlayerError(e)
        }
        player.addListener(listener)
        onDispose {
            save(false)
            if (scrobbleStarted) sendScrobble("stop", finished)
            streams.lateLoad?.cancel()
            lateSubtitles.clear() // attente interrompue, fichiers de sous-titres effacés
            player.removeListener(listener)
            player.release()
            // Remux : Jellyfin arrête la conversion (sinon elle tourne à vide)
            if (streams.remuxed) app.appScope.launch { runCatching { repository.stopRemux(info.itemId) } }
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
            "subtitle_download" -> subtitles.download(streams::reloadSameStream)
            "subtitle_sync" -> subtitles.sync(streams::reloadSameStream)
            "subtitle_shift" -> command.seconds?.let { subtitles.shift(it, tracks, streams::reloadSameStream) } // valeur en ms
            "track" -> command.track?.let { (kind, index) ->
                val type = if (kind == "audio") C.TRACK_TYPE_AUDIO else C.TRACK_TYPE_TEXT
                if (index < 0) {
                    if (type == C.TRACK_TYPE_TEXT) trackChooser.select(type, null)
                } else if (type == C.TRACK_TYPE_AUDIO && hlsChoices.isNotEmpty()) {
                    // Flux converti : la tablette a reçu les pistes du serveur (même rang)
                    hlsChoices.getOrNull(index)?.let { streams.setHlsAudio(it.index) }
                } else {
                    trackChoices(tracks, type).getOrNull(index)?.takeIf { it.supported }?.let { trackChooser.select(type, it) }
                }
            }
        }
        if (scrobbleStarted) sendScrobble("progress", false)
    }
    // Bazarr travaille / a répondu, décalage changé : la tablette suit aussitôt
    LaunchedEffect(subtitles.busy, subtitles.note, subtitles.shiftMs) {
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
            rating != null -> rate(null) // passer cette note
            showUpNext -> upNextDismissed = true
            streams.qualityCard != null && !showMenu -> streams.declineQualityCard()
            showMenu -> leave(onExit)
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
                            onTap = { if (!showMenu && streams.playbackError == null) pause() },
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
                if (rating != null) return@onPreviewKeyEvent false // la carte de note a la main
                if (showMenu || streams.playbackError != null || event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                // Quelle action pour cette touche (règle dans PlayerKeyLogic, testée), puis on l'exécute
                val screen = PlayerKeyLogic.Screen(
                    upNextShown = showUpNext,
                    qualityCardShown = streams.qualityCard != null,
                    skipShown = activeSkip != null,
                    hasNext = upNext != null,
                )
                when (PlayerKeyLogic.action(code, screen)) {
                    PlayerKeyLogic.Action.PLAY_NEXT -> { playNext(); true }
                    PlayerKeyLogic.Action.ACCEPT_QUALITY -> { streams.acceptQualityCard(); true }
                    PlayerKeyLogic.Action.SKIP_SEGMENT -> {
                        activeSkip?.let { player.seekTo((it.end * 1000).toLong()) }
                        true
                    }
                    PlayerKeyLogic.Action.PAUSE_MENU -> { swallowOkUp = ok; pause(); true }
                    PlayerKeyLogic.Action.PLAY -> { player.play(); true }
                    PlayerKeyLogic.Action.SEEK_BACK -> { seekBy(forward = false, repeat = event.nativeKeyEvent.repeatCount); true }
                    PlayerKeyLogic.Action.SEEK_FORWARD -> { seekBy(forward = true, repeat = event.nativeKeyEvent.repeatCount); true }
                    PlayerKeyLogic.Action.SHOW_BAR -> { osdUntil = System.currentTimeMillis() + 3000; true }
                    PlayerKeyLogic.Action.EXIT -> { leave(onExit); true }
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

        // Barre d'avance rapide, « Passer l'intro », « Épisode suivant », carte de qualité : PlayerHud.kt
        PlayerHud(
            info = info,
            showMenu = showMenu,
            osdUntil = osdUntil,
            scrubTarget = scrubTarget,
            position = position,
            duration = duration,
            activeSkip = activeSkip,
            showUpNext = showUpNext,
            upNext = upNext,
            countdown = countdown,
            qualityCard = streams.qualityCard,
            absolute = app.api::absolute,
            onAcceptQuality = streams::acceptQualityCard,
            onDeclineQuality = streams::declineQualityCard,
        )

        // Menu pause façon Apple TV
        AnimatedVisibility(visible = showMenu, enter = fadeIn(), exit = fadeOut()) {
            PauseMenu(
                info = info,
                meta = meta,
                repository = repository,
                position = position,
                duration = duration,
                tracks = tracks,
                absolute = app.api::absolute,
                onResume = ::resume,
                onSeek = { seconds ->
                    player.seekTo((seconds * 1000).toLong())
                    resume()
                },
                onSelectTrack = { type, choice -> trackChooser.select(type, choice) },
                onQuit = { leave(onExit) },
                onSkip = { seconds -> player.seekTo((player.currentPosition + seconds * 1000L).coerceAtLeast(0)) },
                audio = AudioContext(roomSound.room, roomSound.hasAmp, advice, roomSound.autoSound),
                amp = roomSound.amp,
                onAmp = roomSound::ampCommand,
                onAuto = { on ->
                    roomSound.autoSound = on
                    app.prefs.autoSound = on
                },
                onApplyAdvice = { advice.program?.let { roomSound.ampCommand("sound_program", JsonPrimitive(it)) } },
                subtitleDownload = SubtitleDownload(
                    busy = subtitles.busy,
                    note = subtitles.note,
                    onClick = subtitles.request?.let { { subtitles.download(streams::reloadSameStream) } },
                    onSync = subtitles.request?.let { { subtitles.sync(streams::reloadSameStream) } },
                    onShift = { deltaMs -> subtitles.shift(deltaMs, tracks, streams::reloadSameStream) },
                    shiftMs = subtitles.shiftMs,
                ),
                quality = QualityChoice(
                    options = QualityLogic.options(
                        info,
                        screenHdr10,
                        // Format de l'original : la piste lue si c'est lui, sinon la fiche du titre
                        originalFormat = ScrobbleLogic.videoLabel(
                            selectedVideoFormat(tracks)?.height?.takeIf { streams.quality == Quality.ORIGINAL },
                            techBadges(meta?.file),
                            info.videoRange,
                            toneMapped = false,
                        ),
                        doviForcedSdr = streams.doviForcedSdr,
                    ),
                    current = streams.quality,
                    onSelect = { streams.setQuality(it) },
                ),
                hlsAudio = HlsAudioChoice(hlsChoices, streams::setHlsAudio).takeIf { hlsChoices.isNotEmpty() },
            )
        }

        streams.playbackError?.let { message ->
            MessageScreen("Lecture interrompue", message, "Retour", onExit)
        }

        // Note Trakt de fin de lecture : épisode, puis saison / série au dernier épisode
        rating?.let { session ->
            RatingCard(
                step = session.steps[session.index],
                position = session.index,
                count = session.steps.size,
                onRate = { rate(it) },
                onSkip = { rate(null) },
            )
        }
    }

    // Rafraîchit la barre d'avance rapide jusqu'à ce qu'elle s'efface
    LaunchedEffect(osdUntil) {
        while (System.currentTimeMillis() < osdUntil) delay(250)
        osdUntil = 0
    }
    LaunchedEffect(Unit) { runCatching { keyFocus.requestFocus() } }
}
