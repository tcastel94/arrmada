package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Liste « À voir » du profil qui regarde (GET /api/watchlist).
 *
 * Le serveur sait quel profil regarde grâce à l'en-tête `X-Profile-Id` que
 * l'appli envoie déjà (ADR-008) : chaque membre de la famille a sa liste.
 * Un titre est repéré par son identifiant public (TMDB pour un film, TVDB
 * pour une série) : il peut être dans la liste avant d'être sur le NAS.
 */
@Serializable
data class WatchlistItem(
    val key: String = "",
    @SerialName("media_type") val mediaType: String = "movie", // « movie » ou « series »
    @SerialName("external_id") val externalId: String = "",
    @SerialName("tmdb_id") val tmdbId: Long? = null,
    @SerialName("tvdb_id") val tvdbId: Long? = null,
    val title: String = "",
    val year: Int? = null,
    @SerialName("poster_url") val posterUrl: String? = null,
    @SerialName("fanart_url") val fanartUrl: String? = null,
    val overview: String = "",
    @SerialName("in_library") val inLibrary: Boolean = false,
    @SerialName("has_file") val hasFile: Boolean = false,
    // Identifiant Radarr / Sonarr : ouvrir la fiche
    @SerialName("media_id") val mediaId: String? = null,
) {
    val isMovie: Boolean get() = mediaType == "movie"
}

@Serializable
data class Watchlist(val items: List<WatchlistItem> = emptyList())

/** Corps de POST /api/watchlist (les null ne sont pas envoyés). */
@Serializable
data class WatchlistAdd(
    @SerialName("media_type") val mediaType: String,
    val title: String,
    @SerialName("tmdb_id") val tmdbId: Long? = null,
    @SerialName("tvdb_id") val tvdbId: Long? = null,
    val year: Int? = null,
    @SerialName("poster_url") val posterUrl: String? = null,
)

@Serializable
data class WatchlistAdded(val item: WatchlistItem = WatchlistItem())

/** Un titre que l'on peut mettre dans « Ma liste » depuis sa fiche. */
data class WatchlistTarget(
    val mediaType: String, // « movie » ou « series »
    val id: Long, // TMDB (film) ou TVDB (série)
    val title: String,
    val year: Int? = null,
    val poster: String? = null,
) {
    val key: String get() = WatchlistLogic.key(mediaType, id)

    fun body() = WatchlistAdd(
        mediaType = mediaType,
        title = title,
        tmdbId = id.takeIf { mediaType == "movie" },
        tvdbId = id.takeIf { mediaType == "series" },
        year = year,
        // Seulement une adresse web : une affiche « /MediaCover/… » de Radarr ne sert à rien au serveur
        posterUrl = poster?.takeIf { it.startsWith("http://") || it.startsWith("https://") },
    )
}

/** Ce qu'on fait d'une carte « Ma liste » (testé sans écran). */
sealed interface WatchlistOpen {
    data class Movie(val radarrId: String, val tmdbId: Long?) : WatchlistOpen
    data class Show(val sonarrId: String) : WatchlistOpen
    data class Download(val target: DownloadTarget) : WatchlistOpen
}

object WatchlistLogic {
    /** « movie:tmdb:438631 » / « series:tvdb:280619 » (même clé que le serveur). */
    fun key(mediaType: String, id: Long): String = if (mediaType == "movie") "movie:tmdb:$id" else "series:tvdb:$id"

    /**
     * Liste après un ajout : le titre en tête (le serveur range les plus
     * récents d'abord), sans doublon. [item] est la réponse du serveur ; sa
     * clé manque sur un serveur ancien, on prend celle de la fiche.
     */
    fun added(list: List<WatchlistItem>?, item: WatchlistItem, target: WatchlistTarget): List<WatchlistItem> {
        val key = item.key.ifBlank { target.key }
        val entry = if (item.title.isBlank()) {
            // Réponse vide (serveur ancien) : ce que la fiche sait du titre
            WatchlistItem(
                key = key,
                mediaType = target.mediaType,
                externalId = target.id.toString(),
                tmdbId = target.id.takeIf { target.mediaType == "movie" },
                tvdbId = target.id.takeIf { target.mediaType == "series" },
                title = target.title,
                year = target.year,
                posterUrl = target.poster,
            )
        } else {
            item.copy(key = key)
        }
        return listOf(entry) + list.orEmpty().filter { it.key != key }
    }

    /** Liste après un retrait. */
    fun removed(list: List<WatchlistItem>, key: String): List<WatchlistItem> = list.filter { it.key != key }

    /** Disponibles d'abord (on peut les lancer ce soir), puis l'ordre du serveur (récents d'abord). */
    fun ordered(items: List<WatchlistItem>): List<WatchlistItem> =
        items.withIndex().sortedWith(compareBy({ if (it.value.hasFile) 0 else 1 }, { it.index })).map { it.value }

    /** Petite ligne sous la carte / dans le héros. */
    fun note(item: WatchlistItem): String = when {
        item.hasFile -> "Prêt à regarder"
        item.inLibrary -> "Demandé : en attente de téléchargement"
        else -> "Pas encore sur le NAS"
    }

    /** OK sur une carte : sa fiche si le titre est suivi, sinon la feuille « Télécharger ». */
    fun open(item: WatchlistItem): WatchlistOpen {
        val arrId = item.mediaId?.takeIf { it.isNotBlank() }
        return when {
            arrId != null && item.isMovie -> WatchlistOpen.Movie(arrId, item.tmdbId)
            arrId != null -> WatchlistOpen.Show(arrId)
            else -> WatchlistOpen.Download(
                DownloadTarget(
                    kind = item.mediaType,
                    title = item.title,
                    year = item.year,
                    tmdbId = item.tmdbId,
                    tvdbId = item.tvdbId,
                    overview = item.overview.ifBlank { null },
                    poster = item.posterUrl,
                    fanart = item.fanartUrl,
                )
            )
        }
    }
}
