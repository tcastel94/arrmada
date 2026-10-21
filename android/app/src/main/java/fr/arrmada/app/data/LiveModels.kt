package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/*
 * Réponses JSON des écrans « vivants » de la phase 3 (rafraîchis en
 * permanence) : téléchargements, ampli, événements du serveur, tableau de
 * bord. Mêmes routes que l'add-on Kodi, déjà ouvertes aux TV appairées.
 */

// ─── Téléchargements (GET /api/kodi/downloads/board) ────────────────────────

@Serializable
data class Board(
    val tonight: List<BoardCard> = emptyList(), // demandes « Pour ce soir » des TV
    val queue: List<QueueItem> = emptyList(), // file de Radarr / Sonarr
    val sab: SabInfo? = null, // null : pas de SABnzbd configuré
)

/** Demande lancée depuis une TV (« Pour ce soir »), suivie jusqu'à « Prêt à regarder ». */
@Serializable
data class BoardCard(
    val id: Int = 0,
    @SerialName("service_type") val serviceType: String = "",
    @SerialName("media_type") val mediaType: String = "movie",
    @SerialName("arr_id") val arrId: Int? = null,
    val title: String = "",
    val status: String = "open", // open, done, expired
    // searching, downloading, importing, subtitles, ready, blocked, notfound
    val phase: String = "searching",
    val progress: Double = 0.0,
    @SerialName("size_bytes") val sizeBytes: Double = 0.0,
    @SerialName("time_left_seconds") val timeLeftSeconds: Long? = null,
    val error: String = "",
    @SerialName("can_cancel") val canCancel: Boolean = false,
    @SerialName("blocked_download") val blockedDownload: BlockedDownload? = null,
    val quality: String? = null,
    val protocol: String? = null,
    val subtitles: String? = null, // fr, en, missing, off, searching
    @SerialName("device_name") val deviceName: String? = null,
    @SerialName("profile_name") val profileName: String? = null, // profil qui a demandé
    @SerialName("requested_at") val requestedAt: String? = null,
    val mine: Boolean = false,
    @SerialName("poster_url") val posterUrl: String? = null,
    @SerialName("fanart_url") val fanartUrl: String? = null,
)

@Serializable
data class BlockedDownload(
    @SerialName("service_type") val serviceType: String = "",
    @SerialName("download_id") val downloadId: String = "",
)

/** Élément de la file de Radarr / Sonarr. */
@Serializable
data class QueueItem(
    val id: Long = 0,
    val title: String = "",
    val status: String = "", // ce que dit SABnzbd / qBittorrent
    @SerialName("tracked_state") val trackedState: String = "", // ce que dit *arr
    val progress: Double = 0.0,
    @SerialName("size_bytes") val sizeBytes: Double = 0.0,
    @SerialName("size_left_bytes") val sizeLeftBytes: Double = 0.0,
    @SerialName("time_left") val timeLeft: String? = null, // « 1.02:03:04 »
    @SerialName("service_type") val serviceType: String = "",
    @SerialName("movie_id") val movieId: Int? = null,
    @SerialName("series_id") val seriesId: Int? = null,
    @SerialName("download_client") val downloadClient: String? = null,
    val protocol: String? = null,
    val error: String = "",
    val detail: String = "",
    val indexer: String? = null,
    val quality: String? = null,
    @SerialName("download_id") val downloadId: String? = null,
    @SerialName("poster_url") val posterUrl: String? = null,
    @SerialName("fanart_url") val fanartUrl: String? = null,
) {
    /** Fiche Radarr (film) ou Sonarr (série) du titre téléchargé. */
    val arrId: Int? get() = if (serviceType == "sonarr") seriesId else movieId
}

@Serializable
data class SabInfo(
    val paused: Boolean = false,
    val kbpersec: Double = 0.0,
    @SerialName("time_left") val timeLeft: String? = null,
    val slots: Int = 0,
)

/** Diagnostic « Débloquer » (GET …/diagnose). */
@Serializable
data class Diagnose(
    val status: String = "error",
    val title: String = "",
    val steps: List<DiagnoseStep> = emptyList(),
    val action: String = "",
    @SerialName("can_fix") val canFix: Boolean = false,
    val message: String? = null,
)

@Serializable
data class DiagnoseStep(
    val state: String = "", // ok, err, next
    val text: String = "",
    val detail: String = "",
)

// ─── Ampli Yamaha (GET /api/yamaha/state, /profiles) ────────────────────────

@Serializable
data class AmpState(
    val devices: List<AmpDevice> = emptyList(),
    val status: String? = null, // « no_amp » : pièce sans ampli (bureau)
    val detail: String? = null,
)

@Serializable
data class AmpDevice(
    val id: Int = 0,
    val name: String = "",
    val online: Boolean = false,
    val power: String? = null, // on, standby
    @SerialName("volume_pct") val volumePct: Int = 0,
    val mute: Boolean = false,
    val input: String? = null,
    @SerialName("actual_db") val actualDb: Double? = null,
    @SerialName("sound_program") val soundProgram: String? = null,
    // Absents (null) quand l'ampli ne les a pas : le réglage est alors masqué
    @SerialName("dialog_level") val dialogLevel: Int? = null,
    @SerialName("adaptive_drc") val adaptiveDrc: Boolean? = null,
    @SerialName("extra_bass") val extraBass: Boolean? = null,
    @SerialName("subwoofer_volume") val subwooferVolume: Int? = null, // caisson, −12 à +12
    val error: String? = null,
)

/** Profil sonore d'une pièce (GET /api/yamaha/profiles) : nom et enceintes. */
@Serializable
data class RoomProfile(val name: String = "", val speakers: String? = null)

@Serializable
data class AmpControl(val action: String, val value: JsonElement? = null, val zone: String = "main")

// ─── Événements du serveur (GET /api/events/recent) ─────────────────────────

@Serializable
data class EventsPage(
    val events: List<ServerEvent> = emptyList(),
    @SerialName("boot_id") val bootId: String = "",
    @SerialName("last_id") val lastId: Long = 0,
)

@Serializable
data class ServerEvent(
    val id: String = "",
    val type: String = "",
    val data: JsonObject = JsonObject(emptyMap()),
) {
    fun text(key: String): String = (data[key] as? JsonPrimitive)?.contentOrNull.orEmpty()
}

/** « Prêt à regarder » (tv_ready) et « Lire sur la TV » (play_request). */
@Serializable
data class PlayAnnounce(
    @SerialName("device_id") val deviceId: Int? = null,
    @SerialName("profile_id") val profileId: Int? = null, // « Prêt à regarder » d'un profil (ADR-008)
    val title: String = "",
    val subtitles: String? = null,
    val quality: String? = null,
    @SerialName("media_type") val mediaType: String = "movie",
    val id: JsonElement? = null, // TMDB (film) ou TVDB (série), nombre ou texte
    val season: Int? = null,
    val episode: Int? = null,
    @SerialName("service_type") val serviceType: String? = null,
    @SerialName("arr_id") val arrId: Int? = null,
    val at: String = "",
    val poster: String? = null,
    val resume: Boolean = true,
) {
    val externalId: Long? get() = (id as? JsonPrimitive)?.contentOrNull?.toLongOrNull()
    val isEpisode: Boolean get() = mediaType == "episode"
}

/** Détection d'une caméra (événement « camera »). */
@Serializable
data class CameraEvent(
    val camera: String = "",
    val detection: String = "",
    val label: String = "",
    @SerialName("snapshot_id") val snapshotId: Int? = null,
    val at: String = "",
)

/** Photo d'une détection, en base64 (le jeton n'apparaît jamais dans une adresse d'image). */
@Serializable
data class CameraSnapshot(val mime: String = "image/jpeg", val image: String = "")

// ─── Tableau de bord (GET /api/kodi/dashboard) ──────────────────────────────

@Serializable
data class Dashboard(
    val services: List<DashService> = emptyList(),
    val stats: DashStats = DashStats(),
    val disks: List<Disk> = emptyList(),
    val downloads: List<DashDownload> = emptyList(),
    @SerialName("downloads_count") val downloadsCount: Int? = null,
)

@Serializable
data class DashService(
    val name: String = "",
    val type: String = "",
    @SerialName("is_enabled") val isEnabled: Boolean = false,
)

@Serializable
data class DashStats(
    @SerialName("movies_count") val movies: Int = 0,
    @SerialName("series_count") val series: Int = 0,
    @SerialName("episodes_count") val episodes: Int = 0,
    @SerialName("total_size_human") val totalSize: String? = null,
)

@Serializable
data class Disk(
    val path: String = "",
    @SerialName("total_bytes") val totalBytes: Long = 0,
    @SerialName("free_bytes") val freeBytes: Long = 0,
)

@Serializable
data class DashDownload(
    val title: String = "",
    val progress: Double = 0.0,
    val timeleft: String? = null,
    val service: String? = null,
)

/** Profil famille (ADR-008) : qui regarde. */
@Serializable
data class FamilyProfile(
    val id: Int = 0,
    val name: String = "",
    val color: String = "#4A9EFF",
    val emoji: String = "",
    @SerialName("is_default") val isDefault: Boolean = false,
) {
    /** Lettre de l'avatar quand il n'y a pas d'emoji. */
    val initial: String get() = name.trim().take(1).uppercase()
}

@Serializable
data class FamilyProfiles(val items: List<FamilyProfile> = emptyList())

/** TV de la maison où envoyer un titre depuis le téléphone (GET /api/tv/targets). */
@Serializable
data class PlayTarget(val id: Int = 0, val name: String = "", val room: String = "", val online: Boolean = false)

@Serializable
data class PlayTargets(val items: List<PlayTarget> = emptyList())

/** Titre à lancer sur une TV (POST /api/tv/targets/{id}/play), format de « Lire sur la TV ». */
@Serializable
data class PlayOnTv(
    @SerialName("media_type") val mediaType: String,
    val id: String,
    val season: Int? = null,
    val episode: Int? = null,
    val title: String = "",
    val resume: Boolean = true,
)

/** Bande-annonce locale d'un film (GET /api/tv/trailer/movie/{tmdb}). */
@Serializable
data class TrailerInfo(
    val status: String = "none",
    val stream: String = "",
    val duration: Int = 0,
)
