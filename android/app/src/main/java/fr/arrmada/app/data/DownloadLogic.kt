package fr.arrmada.app.data

/*
 * Feuille « Télécharger » (reprise de l'add-on, ADR-005), en Kotlin pur :
 * testée par DownloadLogicTest.
 */

/** Titre à télécharger, d'où qu'il vienne (recherche, Découvrir, fiche, écran Série). */
data class DownloadTarget(
    val kind: String, // « movie » ou « series »
    val title: String,
    val year: Int? = null,
    val tmdbId: Long? = null,
    val tvdbId: Long? = null,
    val arrId: Int? = null,
    val inLibrary: Boolean = false,
    val overview: String? = null,
    val poster: String? = null,
    val fanart: String? = null,
) {
    val isMovie: Boolean get() = kind == "movie"

    companion object {
        fun of(item: LookupItem) = DownloadTarget(
            kind = if (item.type == "movie") "movie" else "series", title = item.title, year = item.year,
            tmdbId = item.tmdbId, tvdbId = item.tvdbId, arrId = item.arrId, inLibrary = item.inLibrary,
            overview = item.overview, poster = item.posterUrl,
        )

        // Recommandation TMDB : pour une série, c'est l'identifiant TMDB de la
        // série ; le serveur le convertit en TVDB.
        fun of(item: TmdbItem) = DownloadTarget(
            kind = if (item.type == "movie") "movie" else "series", title = item.title,
            year = item.year?.take(4)?.toIntOrNull(), tmdbId = item.tmdbId, inLibrary = item.inLibrary,
            overview = item.overview, poster = item.posterUrl, fanart = item.backdropUrl,
        )

        fun of(series: SeriesDetail) = DownloadTarget(
            kind = "series", title = series.title, year = series.year, tvdbId = series.tvdbId,
            arrId = series.id.takeIf { it > 0 }, inLibrary = true, overview = series.overview,
            poster = series.images.poster, fanart = series.images.fanart,
        )

        fun of(movie: MovieDetail) = DownloadTarget(
            kind = "movie", title = movie.title, year = movie.year, tmdbId = movie.tmdbId,
            arrId = movie.id.takeIf { it > 0 }, inLibrary = true, overview = movie.overview,
            poster = movie.images.poster, fanart = movie.images.fanart,
        )
    }
}

/** Portée d'une demande de série (ordre et libellés de l'add-on). */
enum class Scope(val key: String, val label: String) {
    SERIES("series", "Toute la série"),
    SEASON("season", "Une saison"),
    EPISODE("episode", "Un épisode"),
}

object DownloadLogic {

    /** Libellé du bouton principal : il dit exactement ce qui va partir. */
    fun buttonLabel(target: DownloadTarget, scope: Scope, season: Int?, ticked: List<Int>): String = when {
        target.isMovie -> "Télécharger le film"
        scope == Scope.SERIES -> "Télécharger toute la série"
        season == null -> "Choisis une saison"
        scope == Scope.SEASON -> "Télécharger la saison $season"
        ticked.isEmpty() -> "Coche un épisode"
        ticked.size == 1 -> "Télécharger S%02dE%02d".format(season, ticked.first())
        else -> "Télécharger ${ticked.size} épisodes"
    }

    /** Vrai si la sélection est complète (sinon le bouton rappelle ce qui manque). */
    fun ready(target: DownloadTarget, scope: Scope, season: Int?, ticked: List<Int>): Boolean = when {
        target.isMovie || scope == Scope.SERIES -> true
        season == null -> false
        scope == Scope.SEASON -> true
        else -> ticked.isNotEmpty()
    }

    /** Corps de la requête envoyée au serveur. */
    fun request(target: DownloadTarget, scope: Scope, season: Int?, ticked: List<Int>, tonight: Boolean): DownloadRequest =
        DownloadRequest(
            type = if (target.isMovie) "movie" else "series",
            title = target.title,
            priority = tonight,
            tmdbId = target.tmdbId?.takeIf { it > 0 },
            tvdbId = target.tvdbId?.takeIf { it > 0 },
            arrId = target.arrId?.takeIf { it > 0 },
            scope = if (target.isMovie) null else scope.key,
            season = season.takeIf { !target.isMovie && scope != Scope.SERIES },
            episodes = ticked.sorted().takeIf { !target.isMovie && scope == Scope.EPISODE },
        )

    /** Sous-titre d'une pastille de saison : « complète », « 4/10 sur le NAS »… */
    fun seasonSubtitle(count: SeasonCount): String = when {
        count.episodes > 0 && count.have >= count.episodes -> "complète"
        count.have > 0 -> "${count.have}/${count.episodes} sur le NAS"
        count.episodes > 0 -> "${count.episodes} épisodes"
        else -> ""
    }

    /** État d'un épisode dans la liste : déjà là, à venir, ou sa durée. */
    fun episodeState(ep: SeasonEpisode): String = when {
        ep.hasFile -> "Déjà sur le NAS"
        !ep.aired -> shortDate(ep.airDate)?.let { "Sortie le $it" } ?: "À venir"
        ep.runtime != null && ep.runtime > 0 -> "${ep.runtime} min"
        else -> ""
    }
}
