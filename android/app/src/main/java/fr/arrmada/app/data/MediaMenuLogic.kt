package fr.arrmada.app.data

/**
 * Titre visé par un appui long (affiche d'une rangée ou d'une grille, carte
 * « Reprendre », carte « Ma liste »), réduit à ce dont le menu a besoin.
 */
data class MenuTarget(
    val kind: String, // « movie » ou « series »
    val title: String,
    val year: Int? = null,
    val poster: String? = null,
    val tmdbId: Long? = null, // film
    val tvdbId: Long? = null, // série
    val arrId: String? = null, // Radarr / Sonarr : de quoi ouvrir la fiche
    val hasFile: Boolean = false,
    val localSeries: Int? = null, // série maison (Naruto Kai…) : ni liste ni bande-annonce
    val resume: ResumeEntry? = null, // carte « Reprendre » : le film ou l'épisode commencé
) {
    val isMovie: Boolean get() = kind == "movie"

    /** De quoi l'ajouter à « Ma liste » (TMDB pour un film, TVDB pour une série). */
    val watchlist: WatchlistTarget?
        get() = when {
            localSeries != null -> null
            isMovie -> tmdbId?.let { WatchlistTarget("movie", it, title, year, poster) }
            else -> tvdbId?.let { WatchlistTarget("series", it, title, year, poster) }
        }
}

/** Actions proposées, dans l'ordre du menu. */
enum class MenuAction { RESUME, PLAY, FROM_START, OPEN, TRAILER, ADD_TO_LIST, REMOVE_FROM_LIST, MARK_WATCHED, MARK_UNWATCHED }

/** Menu de l'appui long (testé sans écran). */
object MediaMenuLogic {

    fun of(item: LibraryItem): MenuTarget = MenuTarget(
        kind = if (item.isMovie) "movie" else "series",
        title = item.title,
        year = item.year,
        poster = item.posterUrl,
        tmdbId = item.tmdbId.takeIf { item.isMovie },
        tvdbId = item.tmdbId.takeIf { !item.isMovie }, // « tmdb_id » d'une série = TVDB
        arrId = item.externalId.takeIf { it.isNotBlank() && LocalSeriesLogic.idOf(it) == null },
        hasFile = item.hasFile,
        localSeries = LocalSeriesLogic.idOf(item.externalId),
    )

    fun of(item: WatchlistItem): MenuTarget = MenuTarget(
        kind = item.mediaType,
        title = item.title,
        year = item.year,
        poster = item.posterUrl,
        tmdbId = item.tmdbId,
        tvdbId = item.tvdbId,
        arrId = item.mediaId?.takeIf { it.isNotBlank() },
        hasFile = item.hasFile,
    )

    fun of(entry: ResumeEntry): MenuTarget {
        val base = entry.item?.let(::of) ?: MenuTarget(kind = if (entry.isEpisode) "series" else "movie", title = entry.title)
        val id = entry.state.id.toLongOrNull()
        return base.copy(
            title = entry.title,
            tmdbId = if (entry.isEpisode) base.tmdbId else id ?: base.tmdbId,
            tvdbId = if (entry.isEpisode) id ?: base.tvdbId else base.tvdbId,
            localSeries = base.localSeries ?: entry.localSeries.takeIf { it > 0 },
            hasFile = true,
            resume = entry,
        )
    }

    /**
     * Actions du menu. [inList] : le titre est dans « Ma liste » ; [watched] :
     * déjà vu (film seulement, null si on ne sait pas).
     */
    fun actions(target: MenuTarget, inList: Boolean, watched: Boolean?): List<MenuAction> = buildList {
        val resume = target.resume
        if (resume != null) {
            if (resume.state.position > 0 && !resume.state.watched) add(MenuAction.RESUME)
            add(MenuAction.FROM_START)
        } else if (target.isMovie && target.hasFile && target.tmdbId != null) {
            add(MenuAction.PLAY)
        }
        if (target.arrId != null || target.localSeries != null) add(MenuAction.OPEN)
        if (target.isMovie && target.tmdbId != null) add(MenuAction.TRAILER)
        if (target.watchlist != null) add(if (inList) MenuAction.REMOVE_FROM_LIST else MenuAction.ADD_TO_LIST)
        // Vu / pas vu : un film sur le disque, ou l'épisode d'une carte « Reprendre »
        val markable = (resume != null && resume.file == null) || (target.isMovie && target.hasFile && target.tmdbId != null)
        if (markable) add(if (watched == true) MenuAction.MARK_UNWATCHED else MenuAction.MARK_WATCHED)
    }

    fun label(action: MenuAction, target: MenuTarget): String = when (action) {
        MenuAction.RESUME -> "Reprendre à " + fr.arrmada.app.ui.components.formatClock((target.resume?.state?.position ?: 0).toLong())
        MenuAction.PLAY -> "Lire"
        MenuAction.FROM_START -> "Lire depuis le début"
        MenuAction.OPEN -> if (target.localSeries != null || target.resume?.isEpisode == true || !target.isMovie) "Ouvrir la série" else "Ouvrir la fiche"
        MenuAction.TRAILER -> "Bande-annonce"
        MenuAction.ADD_TO_LIST -> "Ajouter à ma liste"
        MenuAction.REMOVE_FROM_LIST -> "Retirer de ma liste"
        MenuAction.MARK_WATCHED -> if (target.resume?.isEpisode == true) "Marquer l’épisode comme vu" else "Marquer comme vu"
        MenuAction.MARK_UNWATCHED -> "Marquer comme non vu"
    }

    /** Ligne sous le titre du menu : « Film · 2021 », « S04E03 · La traque ». */
    fun subtitle(target: MenuTarget): String {
        val resume = target.resume
        if (resume != null && resume.isEpisode) return resume.subtitle
        return listOfNotNull(if (target.isMovie) "Film" else "Série", target.year?.toString()).joinToString(" · ")
    }

    /** Le film est-il marqué vu ? (dans les états partagés du profil) */
    fun watched(target: MenuTarget, states: List<WatchState>): Boolean? {
        val resume = target.resume
        if (resume != null) return resume.state.watched
        val tmdb = target.tmdbId?.toString() ?: return null
        if (!target.isMovie) return null
        return states.firstOrNull { it.mediaType == "movie" && it.id == tmdb }?.watched ?: false
    }

    /** État à envoyer pour « Marquer comme vu / non vu » ; null si le titre ne s'y prête pas. */
    fun watchedUpdate(target: MenuTarget, watched: Boolean, now: String): WatchStateUpdate? {
        val resume = target.resume
        if (resume != null) {
            val s = resume.state
            if (resume.file != null) return null // vidéo d'une série maison : depuis son écran
            return WatchStateUpdate(
                mediaType = s.mediaType, idType = s.idType, id = s.id, season = s.season, episode = s.episode,
                title = s.title, watched = watched, position = 0, total = s.total, lastPlayed = now,
            )
        }
        val tmdb = target.tmdbId ?: return null
        if (!target.isMovie) return null
        return WatchStateUpdate(
            mediaType = "movie", idType = "tmdb", id = tmdb.toString(), title = target.title,
            watched = watched, position = 0, total = 0, lastPlayed = now,
        )
    }
}
