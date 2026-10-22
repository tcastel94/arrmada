package fr.arrmada.app.data

/**
 * Séries maison (Naruto Kai, One Pace…) branchées sur l'écran Série existant,
 * comme un adaptateur de prise : la série maison est traduite en
 * [SeriesDetail] « façon Sonarr », et le vu / la reprise des fichiers (écran
 * Vidéos, repérés par empreinte) en états par (saison, épisode). Ainsi
 * SeriesLogic (Lire la suite, rangées, épisode suivant) sert tel quel.
 * Kotlin pur : testé sur la JVM.
 */
object LocalSeriesLogic {

    /** Préfixe des identifiants de séries maison dans la grille (« local:3 »). */
    const val PREFIX = "local:"

    fun isLocal(externalId: String): Boolean = externalId.startsWith(PREFIX)

    fun idOf(externalId: String): Int? = externalId.removePrefix(PREFIX).toIntOrNull()?.takeIf { isLocal(externalId) }

    /** Carte de la grille Séries (même rendu qu'une série Sonarr). */
    fun libraryItem(s: LocalSeriesSummary): LibraryItem = LibraryItem(
        externalId = PREFIX + s.id,
        title = s.title,
        type = "series",
        year = s.year,
        posterUrl = s.posterUrl,
        fanartUrl = s.fanartUrl,
        hasFile = s.available && s.episodes > 0,
        overview = s.overview,
        added = s.added,
    )

    /** Série maison → fiche « façon Sonarr » ; la pastille (« Kai ») prend la place de la chaîne TV. */
    fun toDetail(d: LocalSeriesDetail): SeriesDetail = SeriesDetail(
        id = d.id,
        title = d.title,
        year = d.year,
        overview = d.overview,
        network = d.badge.ifBlank { null },
        images = Images(poster = d.posterUrl, fanart = d.fanartUrl),
        seasons = d.seasons.map { season ->
            SeasonInfo(
                seasonNumber = season.seasonNumber,
                episodeCount = season.episodes.size,
                episodesHave = season.episodes.size,
                name = season.name.ifBlank { null },
                episodes = season.episodes.map { ep ->
                    EpisodeInfo(
                        seasonNumber = ep.seasonNumber,
                        episodeNumber = ep.episodeNumber,
                        title = ep.title,
                        overview = ep.overview,
                        airDate = ep.airDate,
                        hasFile = true,
                    )
                },
            )
        },
    )

    /** Vignettes des épisodes (au format des vignettes Jellyfin de l'écran Série). */
    fun thumbnails(d: LocalSeriesDetail, season: Int): List<JellyfinEpisode> =
        d.seasons.firstOrNull { it.seasonNumber == season }?.episodes.orEmpty().map { ep ->
            JellyfinEpisode(season = ep.seasonNumber, episode = ep.episodeNumber, itemId = ep.token, title = ep.title, overview = ep.overview, image = ep.image)
        }

    /**
     * Vu / reprise des fichiers (media_type « file », clé = empreinte) →
     * états par (saison, épisode), comme pour une série Sonarr.
     */
    fun states(d: LocalSeriesDetail, all: List<WatchState>): Map<Pair<Int, Int>, WatchState> {
        val byWatchId = all.filter { it.mediaType == "file" }.associateBy { it.id }
        return d.seasons.flatMap { it.episodes }.mapNotNull { ep ->
            byWatchId[ep.watchId]?.let { state ->
                (ep.seasonNumber to ep.episodeNumber) to state.copy(season = ep.seasonNumber, episode = ep.episodeNumber, title = ep.title)
            }
        }.toMap()
    }

    fun episode(d: LocalSeriesDetail, season: Int, episode: Int): LocalEpisode? =
        d.seasons.firstOrNull { it.seasonNumber == season }?.episodes?.firstOrNull { it.episodeNumber == episode }

    /** Épisode suivant (dans l'arc, sinon premier de l'arc suivant) ; null à la fin de la série. */
    fun next(d: LocalSeriesDetail, token: String): LocalEpisode? {
        val all = d.seasons.sortedBy { it.seasonNumber }.flatMap { it.episodes }
        val index = all.indexOfFirst { it.token == token }
        return if (index >= 0) all.getOrNull(index + 1) else null
    }

    /**
     * Rangée Reprendre : épisodes de séries maison commencés et pas finis,
     * présentés comme des épisodes de série (« S02E15 · L'examen commence »).
     */
    fun resume(all: List<WatchState>, index: List<LocalIndexItem>, series: List<LocalSeriesSummary>): List<ResumeEntry> {
        val byWatchId = index.associateBy { it.watchId }
        val byId = series.associateBy { it.id }
        return all
            .filter { it.mediaType == "file" && !it.watched && it.position > 0 }
            .mapNotNull { state ->
                val place = byWatchId[state.id] ?: return@mapNotNull null
                val show = byId[place.seriesId] ?: return@mapNotNull null
                ResumeEntry(
                    state = state.copy(mediaType = "episode", season = place.season, episode = place.episode, title = place.title),
                    item = libraryItem(show),
                    file = place.token,
                    localSeries = place.seriesId,
                )
            }
            .sortedByDescending { it.state.updatedAt }
            .distinctBy { it.localSeries } // un épisode par série, comme pour les séries Sonarr
    }
}
