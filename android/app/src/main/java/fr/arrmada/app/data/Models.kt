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
    val id: Int = 0, // cible des annonces « Prêt à regarder » / « Lire sur la TV »
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
    val overview: String? = null, // résumé de l'épisode (menu pause)
    val duration: Int = 0,
    // « direct » : fichier d'origine ; « remux » : conteneur changé à la volée
    // par Jellyfin (.m2ts, .iso… qu'ExoPlayer n'ouvre pas)
    val mode: String = "direct",
    val container: String = "", // extension du fichier (« mkv », « m2ts »…)
    val stream: String = "",
    @SerialName("remux_stream") val remuxStream: String = "", // secours si le direct échoue
    // Plage dynamique (« SDR », « HDR10 », « DOVI »…) ; Dolby Vision profil 5
    // (sans secours HDR10) : flux converti en SDR par Jellyfin, pour un écran sans DV
    @SerialName("video_range") val videoRange: String = "",
    @SerialName("dovi_only") val doviOnly: Boolean = false,
    @SerialName("sdr_stream") val sdrStream: String = "",
    val chapters: List<Chapter> = emptyList(),
    val resume: Resume = Resume(),
    val segments: List<Segment> = emptyList(),
    // Écran Vidéos : identifiant de vu / reprise du fichier, sous-titres posés à côté
    @SerialName("watch_id") val watchId: String = "",
    val subtitles: List<SideSubtitle> = emptyList(),
)

/** Sous-titre externe (« Ep01.fr.srt » à côté de la vidéo), servi en UTF-8 par le serveur. */
@Serializable
data class SideSubtitle(
    val url: String = "",
    val label: String = "",
    val language: String = "",
    val mime: String = "",
)

// ─── Série (Sonarr) et épisodes (Jellyfin) ──────────────────────────────────

/** Épisode tel que Sonarr le connaît (présent sur le disque, manquant ou à venir). */
@Serializable
data class EpisodeInfo(
    val id: Int = 0,
    @SerialName("season_number") val seasonNumber: Int = 0,
    @SerialName("episode_number") val episodeNumber: Int = 0,
    val title: String? = null,
    val overview: String? = null,
    @SerialName("air_date") val airDate: String? = null, // « 2023-01-15 »
    @SerialName("has_file") val hasFile: Boolean = false,
    val monitored: Boolean = false,
    val file: FileInfo? = null,
)

@Serializable
data class SeasonInfo(
    @SerialName("season_number") val seasonNumber: Int = 0,
    @SerialName("episode_count") val episodeCount: Int = 0,
    @SerialName("episodes_have") val episodesHave: Int = 0,
    val monitored: Boolean = false,
    val episodes: List<EpisodeInfo> = emptyList(),
    val name: String? = null, // série maison : nom de l'arc (« Arc 02 - Examen Chunin »)
)

@Serializable
data class SeriesRatings(val value: Double? = null)

/** Fiche d'une série (GET /api/media/series/{id Sonarr}). */
@Serializable
data class SeriesDetail(
    val error: String? = null,
    val id: Int = 0,
    val title: String = "",
    val year: Int? = null,
    val overview: String? = null,
    val network: String? = null,
    val genres: List<String> = emptyList(),
    val runtime: Int? = null,
    val status: String? = null, // « continuing », « ended »
    val certification: String? = null,
    @SerialName("tvdb_id") val tvdbId: Long? = null,
    val ratings: SeriesRatings = SeriesRatings(),
    val images: Images = Images(),
    val seasons: List<SeasonInfo> = emptyList(),
)

/** Épisode présent dans Jellyfin (GET /api/tv/series/{tvdb}/season/{n}). */
@Serializable
data class JellyfinEpisode(
    val season: Int? = null,
    val episode: Int = 0,
    @SerialName("episode_end") val episodeEnd: Int? = null, // fichier double « E01-E02 »
    @SerialName("item_id") val itemId: String = "",
    val title: String? = null,
    val overview: String? = null,
    val runtime: Int = 0, // secondes
    val image: String? = null, // vignette relayée par le serveur
)

@Serializable
data class SeasonEpisodes(
    val status: String = "error",
    val found: Boolean = false,
    val episodes: List<JellyfinEpisode> = emptyList(),
)

/** Réponse générique des actions (« status » ok / error + message à afficher). */
@Serializable
data class ActionResult(
    val status: String = "error",
    val message: String? = null,
    val title: String? = null,
    val code: String? = null,
    @SerialName("arr_id") val arrId: Int? = null,
) {
    val ok: Boolean get() = status == "ok"
}

// ─── Recherche et demandes (comme l'add-on, ADR-005) ────────────────────────

@Serializable
data class SearchResults(val items: List<LibraryItem> = emptyList(), val total: Int = 0)

/** Résultat de recherche TMDB / TVDB (GET /api/kodi/media/lookup). */
@Serializable
data class LookupItem(
    val title: String = "",
    val year: Int? = null,
    val type: String = "movie", // « movie » ou « series »
    @SerialName("tmdb_id") val tmdbId: Long? = null, // films seulement
    @SerialName("tvdb_id") val tvdbId: Long? = null, // séries seulement
    val overview: String? = null,
    @SerialName("poster_url") val posterUrl: String? = null,
    @SerialName("in_library") val inLibrary: Boolean = false,
    @SerialName("arr_id") val arrId: Int? = null, // identifiant Radarr / Sonarr s'il est suivi
)

/** Saison proposée par la feuille « Télécharger ». */
@Serializable
data class SeasonCount(val number: Int = 0, val episodes: Int = 0, val aired: Int = 0, val have: Int = 0)

@Serializable
data class SeasonEpisode(
    val season: Int = 0,
    val number: Int = 0,
    val title: String? = null,
    @SerialName("air_date") val airDate: String? = null,
    val aired: Boolean = true,
    @SerialName("has_file") val hasFile: Boolean = false,
    val runtime: Int? = null, // minutes
)

/** GET /api/kodi/media/seasons : saisons d'une série et épisodes d'une saison. */
@Serializable
data class SeasonsInfo(
    val status: String = "error",
    val message: String? = null,
    @SerialName("tvdb_id") val tvdbId: Long? = null,
    @SerialName("tmdb_id") val tmdbId: Long? = null,
    @SerialName("arr_id") val arrId: Int? = null,
    @SerialName("in_library") val inLibrary: Boolean = false,
    val source: String? = null, // « sonarr » ou « tmdb »
    val seasons: List<SeasonCount> = emptyList(),
    val season: Int? = null,
    val episodes: List<SeasonEpisode> = emptyList(),
)

/** Corps de POST /api/kodi/media/download (les null ne sont pas envoyés). */
@Serializable
data class DownloadRequest(
    val type: String, // « movie » ou « series »
    val title: String,
    val priority: Boolean, // « Pour ce soir » : passe devant les autres téléchargements
    @SerialName("tmdb_id") val tmdbId: Long? = null,
    @SerialName("tvdb_id") val tvdbId: Long? = null,
    @SerialName("arr_id") val arrId: Int? = null,
    val scope: String? = null, // série : « series », « season », « episode »
    val season: Int? = null,
    val episodes: List<Int>? = null, // numéros des épisodes de la saison
)
