package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * Musique (GET /api/music/…, ADR-015) : Lidarr tient la bibliothèque
 * (artistes suivis, albums présents ou manquants), Jellyfin sert l'écoute.
 * Mêmes réponses que pour la web app.
 */

/** Ce qui est prêt : Lidarr déclaré, bibliothèque « Musique » dans Jellyfin. */
@Serializable
data class MusicStatus(
    val lidarr: Boolean = false,
    val jellyfin: Boolean = false,
    @SerialName("jellyfin_libraries") val jellyfinLibraries: List<String> = emptyList(),
    val ready: Boolean = false,
    val hint: String? = null, // conseil en clair quand quelque chose manque
)

@Serializable
data class MusicArtist(
    val id: Int = 0,
    val mbid: String? = null,
    val name: String = "",
    val overview: String? = null,
    val genres: List<String> = emptyList(),
    val poster: String? = null,
    val fanart: String? = null,
    val albums: Int = 0,
    @SerialName("tracks_have") val tracksHave: Int = 0,
    @SerialName("tracks_total") val tracksTotal: Int = 0,
    @SerialName("size_bytes") val sizeBytes: Long = 0,
    val monitored: Boolean = false,
)

@Serializable
data class MusicArtists(val artists: List<MusicArtist> = emptyList(), val total: Int = 0)

@Serializable
data class MusicAlbum(
    val id: Int = 0,
    val mbid: String? = null,
    val title: String = "",
    val year: Int? = null,
    val type: String = "Album", // « Album », « EP », « Single »…
    val cover: String? = null,
    @SerialName("tracks_have") val tracksHave: Int = 0,
    @SerialName("tracks_total") val tracksTotal: Int = 0,
    val status: String = "missing", // « complete », « partial », « missing »
    val monitored: Boolean = false,
) {
    /** Au moins une piste sur le NAS : l'album peut s'écouter. */
    val listenable: Boolean get() = tracksHave > 0
}

/** Fiche d'un artiste (GET /api/music/artists/{id}). */
@Serializable
data class MusicArtistDetail(
    val id: Int = 0,
    val name: String = "",
    val overview: String? = null,
    val genres: List<String> = emptyList(),
    val poster: String? = null,
    val fanart: String? = null,
    val albums: Int = 0,
    @SerialName("tracks_have") val tracksHave: Int = 0,
    @SerialName("tracks_total") val tracksTotal: Int = 0,
    @SerialName("album_list") val albumList: List<MusicAlbum> = emptyList(),
)

/** Résultat de recherche d'artiste (MusicBrainz via Lidarr). */
@Serializable
data class MusicArtistHit(
    val mbid: String = "",
    val name: String = "",
    val overview: String? = null,
    val type: String? = null, // « Person », « Group »…
    val genres: List<String> = emptyList(),
    val poster: String? = null,
    @SerialName("in_library") val inLibrary: Boolean = false,
)

@Serializable
data class MusicLookup(val results: List<MusicArtistHit> = emptyList())

@Serializable
data class MusicAddBody(val mbid: String)

/** Piste à écouter : [stream] est l'adresse relayée par ArrMada (relative). */
@Serializable
data class MusicTrack(
    val id: String = "",
    val title: String = "",
    val number: Int? = null,
    val disc: Int? = null,
    val duration: Int = 0, // secondes
    val stream: String = "",
)

/** Pistes d'un album (GET /api/music/albums/{id}/tracks). */
@Serializable
data class MusicAlbumTracks(
    val title: String = "",
    val artist: String = "",
    val cover: String? = null,
    val available: Boolean = false,
    val reason: String? = null, // pourquoi on ne peut pas écouter (Jellyfin absent…)
    val tracks: List<MusicTrack> = emptyList(),
)

/** Réponse d'une action (recherche lancée, import lancé). */
@Serializable
data class MusicActionResult(val status: String = "", val message: String = "")

/** Album resté dans le dossier de téléchargements, vu par Lidarr. */
@Serializable
data class MusicDownloadAlbum(
    val folder: String = "",
    val name: String = "",
    val artist: String? = null,
    val album: String? = null,
    val tracks: Int = 0,
    @SerialName("size_bytes") val sizeBytes: Long = 0,
    val ready: Boolean = false, // reconnu par Lidarr : peut être importé
    val reason: String? = null, // sinon, pourquoi (mots de Lidarr)
)

@Serializable
data class MusicDownloads(
    val folders: List<String> = emptyList(),
    val albums: List<MusicDownloadAlbum> = emptyList(),
    /** Dossiers de bonus de films écartés (bande originale rangée avec un film). */
    val ignored: Int = 0,
)

@Serializable
data class MusicImportBody(val folder: String)

