package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

/*
 * Réponses JSON de l'API ArrMada, telles que les renvoie le serveur.
 *
 * Le serveur renvoie des dictionnaires Python sans schéma strict : chaque
 * champ a donc une valeur par défaut, et les champs inconnus sont ignorés
 * (voir Api.json). Un champ ajouté côté serveur ne casse jamais l'appli.
 */

// ─── Appairage (comme l'add-on Kodi, ADR-003) ───────────────────────────────

@Serializable
data class PairStart(
    @SerialName("device_code") val deviceCode: String,
    @SerialName("user_code") val userCode: String,
    @SerialName("verification_url") val verificationUrl: String = "",
    @SerialName("qr_url") val qrUrl: String = "",
    @SerialName("expires_in") val expiresIn: Int = 600,
    val interval: Int = 3,
)

@Serializable
data class PairPoll(
    val status: String = "pending",
    val token: String? = null,
    val device: Device? = null,
)

@Serializable
data class Device(
    val paired: Boolean = true,
    val name: String = "",
    val room: String = "",
    @SerialName("has_amp") val hasAmp: Boolean = false,
)

// ─── Médiathèque ────────────────────────────────────────────────────────────

/** Film ou série de la médiathèque (listes, « Ajouts récents »). */
@Serializable
data class LibraryItem(
    // Identifiant Radarr / Sonarr, à passer à /api/media/movie/{id}
    @SerialName("external_id") val externalId: String = "",
    // Attention : pour une série, « tmdb_id » contient l'identifiant TVDB
    @SerialName("tmdb_id") val tmdbId: Long? = null,
    @SerialName("tmdb_tv_id") val tmdbTvId: Long? = null,
    val title: String = "",
    val type: String = "movie",
    val year: Int? = null,
    val genres: List<String> = emptyList(),
    val quality: String? = null,
    val resolution: JsonElement? = null,
    @SerialName("video_dynamic_range") val dynamicRange: String? = null,
    @SerialName("audio_codec") val audioCodec: String? = null,
    @SerialName("poster_url") val posterUrl: String? = null,
    @SerialName("fanart_url") val fanartUrl: String? = null,
    @SerialName("clearlogo_url") val clearlogoUrl: String? = null,
    @SerialName("has_file") val hasFile: Boolean = false,
    val rating: Double? = null,
    val runtime: Int? = null,
    val overview: String? = null,
    val added: String? = null,
) {
    val isMovie: Boolean get() = type == "movie"
}

@Serializable
data class Pagination(
    val page: Int = 1,
    @SerialName("total_pages") val totalPages: Int = 1,
    val total: Int = 0,
)

@Serializable
data class LibraryPage(
    val items: List<LibraryItem> = emptyList(),
    val pagination: Pagination = Pagination(),
)

// ─── Recommandations (TMDB) ─────────────────────────────────────────────────

@Serializable
data class TmdbItem(
    @SerialName("tmdb_id") val tmdbId: Long = 0,
    val title: String = "",
    val type: String = "movie",
    val year: String? = null, // texte ici (« 2024 »), contrairement à la médiathèque
    val overview: String? = null,
    val rating: Double? = null,
    @SerialName("poster_url") val posterUrl: String? = null,
    @SerialName("backdrop_url") val backdropUrl: String? = null,
    @SerialName("in_library") val inLibrary: Boolean = false,
)

@Serializable
data class BecauseGroup(
    @SerialName("base_title") val baseTitle: String = "",
    val recommendations: List<TmdbItem> = emptyList(),
)

@Serializable
data class Recommendations(
    @SerialName("trending_movies") val trendingMovies: List<TmdbItem> = emptyList(),
    @SerialName("trending_series") val trendingSeries: List<TmdbItem> = emptyList(),
    @SerialName("because_you_have") val becauseYouHave: List<BecauseGroup> = emptyList(),
)

// ─── Calendrier (« Bientôt ») ───────────────────────────────────────────────

@Serializable
data class CalendarEntry(
    val id: String = "",
    val title: String = "",
    val subtitle: String = "",
    val type: String = "movie", // « movie » ou « episode »
    val label: String = "", // « S02E05 » ou l'année
    @SerialName("air_date") val airDate: String? = null,
    @SerialName("has_file") val hasFile: Boolean = false,
    @SerialName("poster_url") val posterUrl: String? = null,
    val overview: String? = null,
    @SerialName("movie_id") val movieId: Int? = null,
    @SerialName("series_id") val seriesId: Int? = null,
)

@Serializable
data class Calendar(val items: List<CalendarEntry> = emptyList())

// ─── Vu / reprise partagés (watch_states) ───────────────────────────────────

@Serializable
data class WatchState(
    @SerialName("media_type") val mediaType: String = "movie",
    @SerialName("id_type") val idType: String = "tmdb",
    val id: String = "",
    val season: Int? = null,
    val episode: Int? = null,
    val title: String = "",
    val watched: Boolean = false,
    val position: Int = 0,
    val total: Int = 0,
    @SerialName("last_played") val lastPlayed: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
)

@Serializable
data class WatchStates(
    val states: List<WatchState> = emptyList(),
    val cursor: String = "",
    val more: Boolean = false,
)

/** État déposé par l'appli (POST /api/kodi/watch-state). */
@Serializable
data class WatchStateUpdate(
    @SerialName("media_type") val mediaType: String,
    @SerialName("id_type") val idType: String,
    val id: String,
    val season: Int? = null,
    val episode: Int? = null,
    val title: String = "",
    val watched: Boolean,
    val position: Int,
    val total: Int,
    @SerialName("last_played") val lastPlayed: String,
)

@Serializable
data class WatchStatePost(val states: List<WatchStateUpdate>, val merge: Boolean = false)

// ─── Fiche d'un film ────────────────────────────────────────────────────────

@Serializable
data class Ratings(
    val tmdb: Double? = null,
    val imdb: Double? = null,
    @SerialName("rotten_tomatoes") val rottenTomatoes: Double? = null,
    val metacritic: Double? = null,
)

@Serializable
data class Images(
    val poster: String? = null,
    val fanart: String? = null,
    val logo: String? = null,
    val clearlogo: String? = null,
    val discart: String? = null,
    @SerialName("disc_type") val discType: String? = null,
    val landscape: String? = null,
) {
    /** Logo du titre : celui trouvé par ArrMada en priorité, sinon celui de Radarr. */
    val bestLogo: String? get() = clearlogo ?: logo
}

@Serializable
data class FileInfo(
    val quality: String? = null,
    val resolution: JsonElement? = null, // entier, ou "" quand Radarr ne sait pas
    @SerialName("video_codec") val videoCodec: String? = null,
    @SerialName("video_dynamic_range") val dynamicRange: String? = null,
    @SerialName("video_dynamic_range_type") val dynamicRangeType: String? = null,
    @SerialName("audio_codec") val audioCodec: String? = null,
    @SerialName("audio_channels") val audioChannels: Double? = null,
    @SerialName("audio_languages") val audioLanguages: String? = null,
    @SerialName("subtitle_languages") val subtitleLanguages: String? = null,
) {
    val height: Int? get() = (resolution as? JsonPrimitive)?.intOrNull
}

@Serializable
data class Person(
    val name: String = "",
    val character: String = "",
    val job: String = "",
    val photo: String? = null,
)

@Serializable
data class MovieDetail(
    val error: String? = null,
    val id: Int = 0,
    val title: String = "",
    val year: Int? = null,
    val overview: String? = null,
    val genres: List<String> = emptyList(),
    val runtime: Int? = null, // minutes
    val certification: String? = null,
    @SerialName("tmdb_id") val tmdbId: Long? = null,
    @SerialName("youtube_trailer_id") val trailerId: String? = null,
    @SerialName("has_file") val hasFile: Boolean = false,
    val ratings: Ratings = Ratings(),
    val images: Images = Images(),
    val file: FileInfo? = null,
    val cast: List<Person> = emptyList(),
    val crew: List<Person> = emptyList(),
)

// ─── Lecture (routes /api/tv, ADR-007) ──────────────────────────────────────

@Serializable
data class Chapter(
    val index: Int = 0,
    val name: String = "",
    val start: Double = 0.0, // secondes
    val image: String? = null, // adresse relayée par le serveur (jeton requis)
)

@Serializable
data class Resume(val position: Int = 0, val watched: Boolean = false)

@Serializable
data class Segment(val kind: String = "", val start: Double = 0.0, val end: Double = 0.0)

@Serializable
data class PlayInfo(
    val status: String = "error",
    val reason: String? = null,
    @SerialName("item_id") val itemId: String = "",
    val title: String? = null,
    val duration: Int = 0,
    val stream: String = "",
    val chapters: List<Chapter> = emptyList(),
    val resume: Resume = Resume(),
    val segments: List<Segment> = emptyList(),
)
