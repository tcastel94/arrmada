package fr.arrmada.app.data

/**
 * « Précédemment dans… » : avant un épisode lancé depuis le début, si la
 * série n'a pas été regardée depuis une semaine, l'appli rappelle de quoi
 * parlait l'épisode d'avant (titre + résumé de Sonarr).
 *
 * Tout est décidé ici, sans écran (testé en JVM) :
 *  - seulement un épisode, lancé depuis le début (une reprise en cours de
 *    route n'en a pas besoin) ;
 *  - seulement si la série a déjà été regardée (sinon il n'y a rien à
 *    rappeler), et pas depuis au moins [AWAY_DAYS] jours ;
 *  - jamais deux fois de suite pour la même série (« Revoir l'épisode
 *    précédent » ne redemande pas un résumé de celui d'encore avant).
 */
data class Recap(
    val seriesTitle: String,
    val previous: EpisodeInfo,
    val awayDays: Int,
    val fanart: String?,
) {
    val code: String get() = "S%02dE%02d".format(previous.seasonNumber, previous.episodeNumber)
}

object RecapLogic {
    const val AWAY_DAYS = 7
    private const val DAY_MS = 24 * 3600_000L

    /** La question se pose-t-elle ? (sinon la lecture part sans attendre) */
    fun applies(kind: String, startSeconds: Int, sonarrId: String?): Boolean =
        kind == "episode" && startSeconds <= 0 && !sonarrId.isNullOrBlank()

    /** Épisode juste avant (saison précédente si c'est le premier d'une saison), spéciaux exclus. */
    fun previous(series: SeriesDetail, season: Int, episode: Int): EpisodeInfo? {
        val ordered = SeriesLogic.orderedSeasons(series).filter { it.seasonNumber > 0 }
            .flatMap { s -> s.episodes.sortedBy { it.episodeNumber } }
        val index = ordered.indexOfFirst { it.seasonNumber == season && it.episodeNumber == episode }
        return if (index > 0) ordered[index - 1] else null
    }

    /** Dernière fois que la série a été regardée (ms), 0 si jamais. */
    fun lastWatchedMs(states: List<WatchState>, tvdbId: Long): Long =
        states.asSequence()
            .filter { it.mediaType == "episode" && it.id == tvdbId.toString() && (it.watched || it.position > 0) }
            .maxOfOrNull { HomeRowsLogic.epochMillis(it.updatedAt) } ?: 0L

    fun recap(
        series: SeriesDetail,
        states: List<WatchState>,
        tvdbId: Long,
        season: Int,
        episode: Int,
        nowMs: Long,
        shownRecently: Boolean = false,
    ): Recap? {
        if (shownRecently) return null
        val last = lastWatchedMs(states, tvdbId)
        if (last <= 0L) return null // jamais regardée : rien à rappeler
        val away = ((nowMs - last) / DAY_MS).toInt()
        if (away < AWAY_DAYS) return null
        val previous = previous(series, season, episode) ?: return null
        // Sans résumé ni titre, le rappel ne dirait rien
        if (previous.overview.isNullOrBlank() && previous.title.isNullOrBlank()) return null
        return Recap(series.title, previous, away, series.images.fanart ?: series.images.landscape)
    }

    /** « il y a 12 jours », « il y a 3 semaines », « il y a 2 mois ». */
    fun awayLabel(days: Int): String = when {
        days < 14 -> "il y a $days jours"
        days < 60 -> "il y a ${days / 7} semaines"
        else -> "il y a ${days / 30} mois"
    }
}
