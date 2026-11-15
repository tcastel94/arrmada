package fr.arrmada.app.ui.player

import androidx.media3.common.C
import androidx.media3.common.Player
import androidx.media3.common.Tracks
import fr.arrmada.app.data.HlsAudioLogic
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.PlaybackLogic
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.Scrobble
import fr.arrmada.app.data.ScrobbleCast
import fr.arrmada.app.data.ScrobbleLogic
import fr.arrmada.app.data.ScrobbleSkip
import fr.arrmada.app.data.ScrobbleTrack
import fr.arrmada.app.data.Segment
import fr.arrmada.app.data.WatchStateUpdate
import fr.arrmada.app.ui.detail.techBadges

// Ce que le lecteur envoie au serveur pendant la lecture : la position
// enregistrée (vu / en cours, partagée avec les TV sous Kodi) et la
// « lecture en cours » pour l'écran d'appoint (tablette sous la TV).
// PlayerSurface décide quand envoyer ; ces fonctions préparent le contenu.

/**
 * Position à enregistrer sur le serveur ([pos] / [total] en secondes,
 * [watched] : vu). Null : vidéo de l'écran Vidéos sans empreinte, rien à
 * enregistrer.
 */
internal fun watchStateUpdate(
    request: PlayRequest,
    info: PlayInfo,
    meta: PlaybackMeta?,
    pos: Int,
    total: Int,
    watched: Boolean,
): WatchStateUpdate? {
    // Vidéo de l'écran Vidéos : repérée par l'empreinte de son chemin (fournie par le serveur)
    val file = request.kind == "file"
    if (file && info.watchId.isBlank()) return null
    return WatchStateUpdate(
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
}

/**
 * « Lecture en cours » pour l'écran d'appoint ([event] : play, progress,
 * pause, resume, stop) : titre, position, et ce que la tablette affiche en
 * plus pendant la séance (formats, pistes, chapitre, épisode suivant,
 * fiche, outils sous-titres).
 */
internal fun scrobblePayload(
    event: String,
    ended: Boolean,
    request: PlayRequest,
    info: PlayInfo,
    meta: PlaybackMeta?,
    player: Player,
    duration: Long,
    tracks: Tracks,
    hlsChoices: List<HlsAudioLogic.Choice>,
    toneMapped: Boolean,
    upNext: UpNext?,
    skips: List<Segment>,
    subtitles: SubtitleTools,
): Scrobble {
    val what = ScrobbleLogic.identity(
        request.kind, request.id, request.season, request.episode,
        title = meta?.title ?: info.title.orEmpty(),
        subtitle = meta?.subtitle,
        localSeries = request.localSeries > 0,
    )
    val total = (player.duration.takeIf { it > 0 } ?: duration) / 1000.0
    val positionS = player.currentPosition / 1000.0
    // Flux converti : les pistes du serveur (le lecteur n'en voit qu'une), sinon celles du lecteur
    val audioChoices = if (hlsChoices.isNotEmpty()) {
        hlsChoices.map { TrackChoice(it.label, it.detail, it.selected, supported = true, group = null, index = it.index) }
    } else {
        trackChoices(tracks, C.TRACK_TYPE_AUDIO)
    }
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
        subtitleTools = subtitles.request != null,
        subtitleBusy = subtitles.busy,
        subtitleNote = subtitles.note.orEmpty(),
        subtitleShiftMs = subtitles.shiftMs,
    )
    return ScrobbleLogic.payload(
        event, rich, positionS, total, paused = !player.playWhenReady, ended = ended,
    )
}
