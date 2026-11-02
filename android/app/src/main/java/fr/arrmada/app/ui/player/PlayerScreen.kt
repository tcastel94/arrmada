package fr.arrmada.app.ui.player

import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.data.SagaRules
import fr.arrmada.app.data.MovieSaga
import fr.arrmada.app.data.Recap
import fr.arrmada.app.data.RecapLogic
import fr.arrmada.app.data.TrackLanguageLogic
import fr.arrmada.app.data.TrackPreference
import androidx.annotation.OptIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.media3.common.util.UnstableApi
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.LocalSeriesDetail
import fr.arrmada.app.data.LocalSeriesLogic
import fr.arrmada.app.data.SeriesDetail
import fr.arrmada.app.data.SeriesLogic
import fr.arrmada.app.ui.components.MessageScreen
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.launch

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
    var movieSaga by remember(request) { mutableStateOf<MovieSaga?>(null) } // film d'une saga : le suivant
    // Dernier choix de pistes du profil pour ce titre (VF, sous-titres coupés…)
    var trackPreference by remember { mutableStateOf<TrackPreference?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    // « Précédemment dans… » : décidé en parallèle du chargement (2,5 s au plus)
    var recap by remember(request) { mutableStateOf<Recap?>(null) }
    var recapChecked by remember(request) {
        mutableStateOf(!RecapLogic.applies(request.kind, request.startSeconds, request.sonarrId))
    }

    LaunchedEffect(request) {
        if (recapChecked) return@LaunchedEffect
        val found = withTimeoutOrNull(2_500) {
            runCatching {
                val detail = repository.series(request.sonarrId.orEmpty()) // en cache depuis l'écran Série
                RecapLogic.recap(
                    series = detail,
                    states = repository.watchStates(),
                    tvdbId = request.id,
                    season = request.season,
                    episode = request.episode,
                    nowMs = System.currentTimeMillis(),
                    shownRecently = repository.recapShownRecently(request.id),
                )
            }.getOrNull()
        }
        found?.let { repository.markRecapShown(request.id) }
        recap = found
        recapChecked = true
    }

    // Film d'une saga (ADR-016) : le film suivant sur le NAS, pour la carte
    // de fin « Film suivant » (lu à côté, sans retarder la lecture)
    LaunchedEffect(request) {
        val radarrId = request.radarrId
        if (request.kind == "movie" && !radarrId.isNullOrBlank()) {
            movieSaga = runCatching { repository.movieSaga(radarrId) }.getOrNull()
        }
    }

    /** Fiche du titre (film Radarr, série Sonarr ou série maison) → [meta]. */
    suspend fun loadMeta(play: PlayInfo) {
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
    }

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
            // Fiche du titre pour le menu pause, l'épisode suivant et la langue
            // originale (VO + sous-titres FR choisis d'office) : lue AVANT de
            // lancer le lecteur, 3 s au plus (en cache depuis la fiche le plus
            // souvent) ; au-delà, la lecture part sans attendre et la fiche
            // arrive ensuite (pistes du fichier par défaut)
            val metaJob = launch { loadMeta(play) }
            // En même temps : le dernier choix de pistes du profil (null : rien de rangé)
            val preferenceJob = launch {
                TrackLanguageLogic.scope(request.kind, request.id, request.localSeries)?.let { scope ->
                    trackPreference = runCatching { repository.trackPreference(scope) }.getOrNull()?.takeIf { it.found }
                }
            }
            withTimeoutOrNull(3_000) {
                metaJob.join()
                preferenceJob.join()
            }
            info = play
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
    // Film d'une saga : le film suivant de la saga, s'il est sur le NAS
    val sagaUpNext = movieSaga?.let { ms ->
        val saga = ms.saga
        val next = ms.following
        val nextId = next?.movieId
        if (saga != null && next != null && nextId != null) {
            UpNext(
                request = PlayRequest("movie", next.tmdbId, radarrId = nextId.toString()),
                code = SagaRules.upNextCode(saga, next),
                title = next.title,
                image = saga.fanart ?: next.poster,
            )
        } else {
            null
        }
    }
    // Série maison : vidéo suivante de la série (dans l'arc, sinon l'arc suivant)
    val upNext = seriesUpNext ?: sagaUpNext ?: local?.let { d ->
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
        play == null || !recapChecked -> return MessageScreen("Préparation de la lecture…")
    }
    // « Précédemment dans… » d'abord (OK ou 15 s sans rien toucher : l'épisode part)
    val shownRecap = recap
    if (shownRecap != null) {
        RecapScreen(
            recap = shownRecap,
            nextCode = "S%02dE%02d".format(request.season, request.episode),
            absolute = app.api::absolute,
            onStart = { recap = null },
            // Revoir l'épisode d'avant : il remplace celui-ci (Retour ramène à l'écran Série)
            onReplayPrevious = if (shownRecap.previous.hasFile) ({
                onPlayNext(request.copy(season = shownRecap.previous.seasonNumber, episode = shownRecap.previous.episodeNumber, startSeconds = 0))
            }) else null,
            onExit = onExit,
        )
        return
    }
    PlayerSurface(request, play!!, meta, trackPreference, upNext, app, presetDone, onExit, onPlayNext)
}
