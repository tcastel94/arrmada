package fr.arrmada.app.data

import java.time.LocalDate

/*
 * Règles de l'écran Série et de l'enchaînement des épisodes, en Kotlin pur
 * (sans Android) : testées par SeriesLogicTest sur la machine de build.
 */

/** Où en est un épisode, pour l'affichage (pastille, barre de reprise). */
enum class EpisodeStatus { AVAILABLE, MISSING, UPCOMING }

/** Épisode affiché : Sonarr (existe-t-il ?) + Jellyfin (vignette) + vu / reprise partagés. */
data class EpisodeRow(
    val season: Int,
    val episode: Int,
    val title: String,
    val overview: String?,
    val airDate: String?,
    val status: EpisodeStatus,
    val image: String?, // vignette Jellyfin (adresse relayée) ou null
    val runtime: Int, // secondes (0 si inconnu)
    val watched: Boolean,
    val position: Int, // reprise en secondes (0 si rien)
    val total: Int,
    val file: FileInfo?,
) {
    val code: String get() = "S%02dE%02d".format(season, episode)
    val progress: Float get() = if (!watched && position > 0 && total > 0) position.toFloat() / total else 0f
    val inProgress: Boolean get() = !watched && position > 0
}

/** Ce que propose le bouton principal de l'écran Série. */
data class NextUp(val row: EpisodeRow, val resume: Boolean) {
    val label: String
        get() = if (resume) {
            "Reprendre ${row.code} à " + fr.arrmada.app.ui.components.formatClock(row.position.toLong())
        } else {
            "Lire ${row.code}"
        }
}

object SeriesLogic {

    /** Saisons dans l'ordre de visionnage : les « spéciaux » (saison 0) à la fin. */
    fun orderedSeasons(series: SeriesDetail): List<SeasonInfo> =
        series.seasons.sortedWith(compareBy({ it.seasonNumber == 0 }, { it.seasonNumber }))

    /** États vu / reprise des épisodes de cette série (clé : saison, épisode). */
    fun statesBySeries(states: List<WatchState>, tvdbId: Long?): Map<Pair<Int, Int>, WatchState> =
        states
            .filter { it.mediaType == "episode" && it.idType == "tvdb" && it.id == tvdbId?.toString() }
            .filter { it.season != null && it.episode != null }
            .associateBy { it.season!! to it.episode!! }

    /** Lignes d'une saison : tous les épisodes Sonarr, enrichis par Jellyfin et les états. */
    fun rows(
        season: SeasonInfo,
        jellyfin: List<JellyfinEpisode>,
        states: Map<Pair<Int, Int>, WatchState>,
        today: LocalDate = LocalDate.now(),
    ): List<EpisodeRow> {
        // Un fichier double (E01-E02) couvre plusieurs numéros
        fun jellyfinFor(number: Int) = jellyfin.firstOrNull {
            it.episode == number || (it.episodeEnd != null && number in it.episode..it.episodeEnd)
        }
        return season.episodes.sortedBy { it.episodeNumber }.map { ep ->
            val jf = jellyfinFor(ep.episodeNumber)
            val state = states[ep.seasonNumber to ep.episodeNumber]
            val status = when {
                ep.hasFile -> EpisodeStatus.AVAILABLE
                isFuture(ep.airDate, today) -> EpisodeStatus.UPCOMING
                else -> EpisodeStatus.MISSING
            }
            EpisodeRow(
                season = ep.seasonNumber,
                episode = ep.episodeNumber,
                title = ep.title?.takeIf { it.isNotBlank() } ?: jf?.title ?: "Épisode ${ep.episodeNumber}",
                overview = ep.overview?.takeIf { it.isNotBlank() } ?: jf?.overview,
                airDate = ep.airDate,
                status = status,
                image = jf?.image,
                runtime = jf?.runtime ?: 0,
                watched = state?.watched == true,
                position = state?.position ?: 0,
                total = state?.total?.takeIf { it > 0 } ?: jf?.runtime ?: 0,
                file = ep.file,
            )
        }
    }

    /**
     * Bouton « Lire la suite » :
     *  1. un épisode commencé (le plus récent) → « Reprendre SxxEyy à … » ;
     *  2. sinon l'épisode disponible qui suit le dernier vu ;
     *  3. sinon le premier épisode disponible.
     * null si aucun épisode n'est sur le disque.
     */
    fun nextUp(series: SeriesDetail, states: Map<Pair<Int, Int>, WatchState>): NextUp? {
        val ordered = orderedSeasons(series).filter { it.seasonNumber > 0 }
            .flatMap { s -> s.episodes.sortedBy { it.episodeNumber } }
        val available = ordered.filter { it.hasFile }
        if (available.isEmpty()) return null

        fun rowOf(ep: EpisodeInfo): EpisodeRow {
            val state = states[ep.seasonNumber to ep.episodeNumber]
            return EpisodeRow(
                season = ep.seasonNumber, episode = ep.episodeNumber,
                title = ep.title ?: "Épisode ${ep.episodeNumber}", overview = ep.overview, airDate = ep.airDate,
                status = EpisodeStatus.AVAILABLE, image = null, runtime = 0,
                watched = state?.watched == true, position = state?.position ?: 0, total = state?.total ?: 0,
                file = ep.file,
            )
        }

        val started = states.values
            .filter { !it.watched && it.position > 0 }
            .maxByOrNull { it.updatedAt }
            ?.let { s -> available.firstOrNull { it.seasonNumber == s.season && it.episodeNumber == s.episode } }
        if (started != null) return NextUp(rowOf(started), resume = true)

        val lastWatched = ordered.indexOfLast { states[it.seasonNumber to it.episodeNumber]?.watched == true }
        val next = ordered.drop(lastWatched + 1).firstOrNull { it.hasFile }
            ?: if (lastWatched >= 0) null else available.first()
        return next?.let { NextUp(rowOf(it), resume = false) }
    }

    /** Épisode disponible qui suit (season, episode), pour l'enchaînement ; null en fin de série. */
    fun following(series: SeriesDetail, season: Int, episode: Int): EpisodeInfo? {
        val ordered = orderedSeasons(series).filter { it.seasonNumber > 0 }
            .flatMap { s -> s.episodes.sortedBy { it.episodeNumber } }
        val index = ordered.indexOfFirst { it.seasonNumber == season && it.episodeNumber == episode }
        if (index < 0) return null
        return ordered.drop(index + 1).firstOrNull { it.hasFile }
    }

    /** Saison à ouvrir d'office : celle du prochain épisode, sinon la première. */
    fun initialSeason(series: SeriesDetail, next: NextUp?): Int =
        next?.row?.season ?: orderedSeasons(series).firstOrNull { it.seasonNumber > 0 }?.seasonNumber
            ?: orderedSeasons(series).firstOrNull()?.seasonNumber ?: 1

    private fun isFuture(airDate: String?, today: LocalDate): Boolean {
        val date = airDate?.take(10)?.let { runCatching { LocalDate.parse(it) }.getOrNull() } ?: return false
        return date.isAfter(today)
    }
}

/** « 2026-11-03 » → « 03/11 » */
fun shortDate(date: String?): String? =
    date?.take(10)?.split("-")?.takeIf { it.size == 3 }?.let { "${it[2]}/${it[1]}" }
