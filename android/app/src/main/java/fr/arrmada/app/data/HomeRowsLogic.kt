package fr.arrmada.app.data

import java.net.URLDecoder
import java.net.URLEncoder
import java.time.OffsetDateTime

/**
 * Une carte posée sur l'écran d'accueil d'Android TV (hors de l'appli) :
 * rangée « À suivre » du système ou chaîne « ArrMada ».
 *
 * [key] : identifiant stable d'une synchro à l'autre (comme une clé primaire),
 * pour mettre à jour une carte au lieu de la supprimer puis la recréer.
 */
data class HomeCard(
    val key: String,
    val kind: String, // « movie », « episode » ou « series »
    val title: String,
    val episodeTitle: String? = null,
    val season: Int? = null,
    val episode: Int? = null,
    val description: String? = null,
    val poster: String? = null, // adresse complète de l'affiche (téléchargée puis servie au lanceur)
    val link: String, // lien arrmada://… ouvert au clic
    val positionMs: Long = 0,
    val durationMs: Long = 0,
    val lastWatchedMs: Long = 0, // tri de la rangée « À suivre » (le plus récent d'abord)
)

/** Ce qu'un lien arrmada://… demande à l'appli. */
sealed interface HomeLink {
    /** Lire (ou reprendre) un film ou un épisode : mêmes champs que PlayRequest. */
    data class Play(
        val kind: String,
        val id: Long,
        val season: Int,
        val episode: Int,
        val startSeconds: Int,
        val radarrId: String?,
        val sonarrId: String?,
    ) : HomeLink

    data class Movie(val radarrId: String, val tmdbId: Long?) : HomeLink
    data class Show(val sonarrId: String) : HomeLink
    data object Home : HomeLink
}

/**
 * Règles des rangées de l'accueil Android TV, en Kotlin pur (testées sur la
 * JVM) : quelles cartes, dans quel ordre, et le format des liens. La partie
 * Android (TvProvider) est dans home/TvHomeRows.kt.
 */
object HomeRowsLogic {

    const val SCHEME = "arrmada"
    const val MAX_RESUME = 10
    const val MAX_RECENT = 20

    /**
     * « À suivre » : films et épisodes commencés (la rangée Reprendre de
     * l'appli), avec la position pour la barre de progression du lanceur.
     * [entries] : (état de lecture, titre de la médiathèque s'il est connu).
     */
    fun resumeCards(entries: List<Pair<WatchState, LibraryItem?>>, absolute: (String?) -> String?): List<HomeCard> =
        entries
            // Identifiant TMDB / TVDB numérique : sinon pas de lecture possible depuis le lien
            .filter { (state, _) -> !state.watched && state.position > 0 && (state.id.toLongOrNull() ?: 0) > 0 }
            .take(MAX_RESUME)
            .map { (state, item) ->
                val episode = state.mediaType == "episode"
                val title = item?.title ?: state.title
                HomeCard(
                    key = "resume:${state.mediaType}:${state.id}" + if (episode) ":${state.season ?: 0}:${state.episode ?: 0}" else "",
                    kind = if (episode) "episode" else "movie",
                    title = title,
                    episodeTitle = state.title.takeIf { episode && it.isNotBlank() && it != title },
                    season = state.season.takeIf { episode },
                    episode = state.episode.takeIf { episode },
                    description = item?.overview,
                    poster = absolute(item?.posterUrl),
                    link = playLink(
                        HomeLink.Play(
                            kind = if (episode) "episode" else "movie",
                            id = state.id.toLongOrNull() ?: 0,
                            season = state.season ?: 0,
                            episode = state.episode ?: 0,
                            startSeconds = state.position,
                            radarrId = item?.externalId?.takeIf { !episode },
                            sonarrId = item?.externalId?.takeIf { episode },
                        )
                    ),
                    positionMs = state.position * 1000L,
                    durationMs = state.total * 1000L,
                    lastWatchedMs = epochMillis(state.lastPlayed.ifBlank { state.updatedAt }),
                )
            }

    /** Chaîne « ArrMada » : les derniers ajouts (films et séries), le clic ouvre la fiche. */
    fun recentCards(items: List<LibraryItem>, absolute: (String?) -> String?): List<HomeCard> =
        items
            .filter { it.externalId.isNotBlank() }
            .distinctBy { it.type to it.externalId }
            .take(MAX_RECENT)
            .map { item ->
                HomeCard(
                    key = "recent:${item.type}:${item.externalId}",
                    kind = if (item.isMovie) "movie" else "series",
                    title = item.title,
                    description = item.overview,
                    poster = absolute(item.posterUrl),
                    link = if (item.isMovie) {
                        "$SCHEME://movie?radarr=${enc(item.externalId)}" + (item.tmdbId?.let { "&tmdb=$it" } ?: "")
                    } else {
                        "$SCHEME://show?sonarr=${enc(item.externalId)}"
                    },
                )
            }

    fun playLink(p: HomeLink.Play): String =
        "$SCHEME://play?kind=${p.kind}&id=${p.id}&season=${p.season}&episode=${p.episode}&start=${p.startSeconds}" +
            (p.radarrId?.let { "&radarr=${enc(it)}" } ?: "") +
            (p.sonarrId?.let { "&sonarr=${enc(it)}" } ?: "")

    /** Lien reçu par l'appli → écran à ouvrir ; null si ce n'est pas un lien ArrMada valide. */
    fun parse(link: String?): HomeLink? {
        if (link == null || !link.startsWith("$SCHEME://")) return null
        val rest = link.removePrefix("$SCHEME://")
        val host = rest.substringBefore('?').trimEnd('/')
        val query = rest.substringAfter('?', "")
            .split('&')
            .filter { '=' in it }
            .associate { it.substringBefore('=') to URLDecoder.decode(it.substringAfter('='), "UTF-8") }
        return when (host) {
            "home" -> HomeLink.Home
            "movie" -> query["radarr"]?.takeIf { it.isNotBlank() }?.let { HomeLink.Movie(it, query["tmdb"]?.toLongOrNull()) }
            "show" -> query["sonarr"]?.takeIf { it.isNotBlank() }?.let { HomeLink.Show(it) }
            "play" -> {
                val kind = query["kind"]?.takeIf { it == "movie" || it == "episode" } ?: return null
                val id = query["id"]?.toLongOrNull()?.takeIf { it > 0 } ?: return null
                HomeLink.Play(
                    kind = kind,
                    id = id,
                    season = query["season"]?.toIntOrNull() ?: 0,
                    episode = query["episode"]?.toIntOrNull() ?: 0,
                    startSeconds = query["start"]?.toIntOrNull()?.coerceAtLeast(0) ?: 0,
                    radarrId = query["radarr"]?.takeIf { it.isNotBlank() },
                    sonarrId = query["sonarr"]?.takeIf { it.isNotBlank() },
                )
            }
            else -> null
        }
    }

    /** Date ISO du serveur (« 2026-10-21T20:00:00+00:00 », ou sans fuseau = UTC) → millisecondes ; 0 si illisible. */
    fun epochMillis(iso: String): Long {
        if (iso.isBlank()) return 0
        return runCatching { OffsetDateTime.parse(iso).toInstant().toEpochMilli() }
            .recoverCatching { java.time.LocalDateTime.parse(iso).toInstant(java.time.ZoneOffset.UTC).toEpochMilli() }
            .getOrDefault(0)
    }

    private fun enc(value: String): String = URLEncoder.encode(value, "UTF-8")
}
