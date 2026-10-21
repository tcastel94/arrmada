package fr.arrmada.app.data

import android.os.Build
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.Serializable
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** Élément de la rangée « Reprendre » : un film ou un épisode commencé. */
data class ResumeEntry(
    val state: WatchState,
    val item: LibraryItem?, // film ou série correspondant dans la médiathèque
) {
    val isEpisode: Boolean get() = state.mediaType == "episode"
    val progress: Float get() = if (state.total > 0) state.position.toFloat() / state.total else 0f
    val title: String get() = item?.title ?: state.title
    val subtitle: String
        get() = if (isEpisode) {
            "S%02dE%02d".format(state.season ?: 0, state.episode ?: 0) +
                (state.title.takeIf { it.isNotBlank() && it != item?.title }?.let { " · $it" } ?: "")
        } else {
            "Reprendre à " + fr.arrmada.app.ui.components.formatClock(state.position.toLong())
        }
}

/**
 * Tous les appels à l'API, regroupés. Chaque fonction correspond à une route
 * du serveur (mêmes routes que l'add-on Kodi, plus /api/tv pour la lecture).
 */
class Repository(private val api: Api) {

    // ── Appairage ──
    @Serializable
    private data class PairStartBody(val platform: String, val kind: String = "tv")

    @Serializable
    private data class PairPollBody(@kotlinx.serialization.SerialName("device_code") val deviceCode: String)

    suspend fun pairStart(): PairStart =
        api.post("/api/devices/pair/start", PairStartBody("ArrMada Android TV · ${Build.MANUFACTURER} ${Build.MODEL}"))

    /** null tant que la web app n'a pas validé ; ApiException(410) si le code a expiré. */
    suspend fun pairPoll(deviceCode: String): PairPoll = api.post("/api/devices/pair/poll", PairPollBody(deviceCode))

    suspend fun me(): Device = api.get("/api/devices/me")

    // ── Médiathèque ──
    suspend fun recent(): List<LibraryItem> = api.get("/api/kodi/widgets/recent")

    suspend fun library(type: String, sort: String = "added", order: String = "desc", page: Int = 1, perPage: Int = 200): LibraryPage =
        api.get("/api/media?type=$type&sort=$sort&order=$order&page=$page&per_page=$perPage")

    // Médiathèque complète gardée en mémoire 5 min (comme le cache du serveur) :
    // la rangée « Reprendre » et les grilles s'en servent sans la relire.
    private val libraryCache = mutableMapOf<String, Pair<Long, List<LibraryItem>>>()
    private val libraryLock = kotlinx.coroutines.sync.Mutex()

    /** Tous les films (« movie ») ou toutes les séries (« series »), plus récents d'abord. */
    suspend fun allLibrary(type: String, force: Boolean = false): List<LibraryItem> = libraryLock.withLock {
        val cached = libraryCache[type]
        if (!force && cached != null && System.currentTimeMillis() - cached.first < 5 * 60_000) {
            return cached.second
        }
        val items = mutableListOf<LibraryItem>()
        var page = 1
        do {
            val result = library(type, page = page)
            items += result.items
            page++
        } while (page <= result.pagination.totalPages && page <= 50)
        libraryCache[type] = System.currentTimeMillis() to items
        items
    }

    suspend fun recommendations(): Recommendations = api.get("/api/recommendations")

    suspend fun upcoming(days: Int = 14): Calendar = api.get("/api/calendar?days=$days")

    suspend fun movie(radarrId: String): MovieDetail = api.get("/api/media/movie/$radarrId")

    suspend fun series(sonarrId: String): SeriesDetail = api.get("/api/media/series/$sonarrId")

    /** Épisodes d'une saison présents dans Jellyfin (vignettes, durées). */
    suspend fun seasonEpisodes(tvdbId: Long, season: Int): SeasonEpisodes =
        api.get("/api/tv/series/$tvdbId/season/$season")

    // ── Vu / reprise ──
    /** Tous les états partagés (relus page par page, 500 par page). */
    suspend fun watchStates(): List<WatchState> {
        val all = mutableListOf<WatchState>()
        var cursor = ""
        do {
            val page: WatchStates = api.get("/api/kodi/watch-state" + if (cursor.isNotEmpty()) "?since=" + java.net.URLEncoder.encode(cursor, "UTF-8") else "")
            all += page.states
            cursor = page.cursor
        } while (page.more && cursor.isNotEmpty())
        return all
    }

    suspend fun saveWatchState(update: WatchStateUpdate) {
        api.post<kotlinx.serialization.json.JsonObject, WatchStatePost>("/api/kodi/watch-state", WatchStatePost(listOf(update)))
    }

    /**
     * Rangée « Reprendre » : titres commencés et pas finis, du plus récent au
     * plus ancien, rapprochés de la médiathèque pour avoir leurs images.
     */
    suspend fun resumeRow(states: List<WatchState>, movies: List<LibraryItem>, series: List<LibraryItem>): List<ResumeEntry> {
        val moviesByTmdb = movies.associateBy { it.tmdbId?.toString() }
        val seriesByTvdb = series.associateBy { it.tmdbId?.toString() } // tmdb_id = TVDB pour une série
        return states
            .filter { !it.watched && it.position > 0 }
            .sortedByDescending { it.updatedAt }
            .distinctBy { if (it.mediaType == "episode") "s:${it.id}" else "m:${it.id}" } // un épisode par série
            .take(20)
            .map { state ->
                val item = if (state.mediaType == "episode") seriesByTvdb[state.id] else moviesByTmdb[state.id]
                ResumeEntry(state, item)
            }
    }

    @Serializable
    private data class EpisodeSearchBody(
        @kotlinx.serialization.SerialName("media_type") val mediaType: String = "episode",
        @kotlinx.serialization.SerialName("tvdb_id") val tvdbId: Long,
        val title: String,
        val season: Int,
        val episode: Int,
    )

    /** « Chercher » un épisode manquant (Sonarr lance la recherche), comme l'add-on. */
    suspend fun searchEpisode(tvdbId: Long, title: String, season: Int, episode: Int): ActionResult =
        api.post("/api/kodi/actions/search", EpisodeSearchBody(tvdbId = tvdbId, title = title, season = season, episode = episode))

    // ── Recherche et demandes ──
    private fun q(text: String) = java.net.URLEncoder.encode(text, "UTF-8")

    /** Titres de la médiathèque dont le nom contient [text] (30 au plus). */
    suspend fun searchLibrary(text: String): SearchResults = api.get("/api/media/search?q=${q(text)}")

    /** Titres à ajouter (Radarr + Sonarr, donc TMDB / TVDB). */
    suspend fun lookup(text: String): List<LookupItem> = api.get("/api/kodi/media/lookup?q=${q(text)}&type=all")

    suspend fun seasons(title: String, tmdbId: Long?, tvdbId: Long?, season: Int? = null): SeasonsInfo {
        val params = buildList {
            add("title=${q(title)}")
            tmdbId?.let { add("tmdb_id=$it") }
            tvdbId?.let { add("tvdb_id=$it") }
            season?.let { add("season=$it") }
        }.joinToString("&")
        return api.get("/api/kodi/media/seasons?$params")
    }

    /** Ajoute le titre si besoin et lance le téléchargement (réponse immédiate). */
    suspend fun download(request: DownloadRequest): ActionResult = api.post("/api/kodi/media/download", request)

    // ── Lecture ──
    suspend fun playMovie(tmdbId: Long): PlayInfo = api.get("/api/tv/play/movie/$tmdbId")

    suspend fun playEpisode(tvdbId: Long, season: Int, episode: Int): PlayInfo =
        api.get("/api/tv/play/episode/$tvdbId/$season/$episode")

    // ── Ampli ──
    @Serializable
    private data class PresetBody(
        val room: String,
        @kotlinx.serialization.SerialName("media_type") val mediaType: String,
        @kotlinx.serialization.SerialName("audio_codec") val audioCodec: String? = null,
        @kotlinx.serialization.SerialName("audio_channels") val audioChannels: Double? = null,
    )

    /** Préréglage Yamaha de la pièce avant un film, comme l'add-on (rien au bureau). */
    suspend fun applyAmpPreset(device: Device, mediaType: String, audioCodec: String?, audioChannels: Double?) {
        if (!device.hasAmp || device.room.isBlank()) return
        api.post<kotlinx.serialization.json.JsonObject, PresetBody>(
            "/api/yamaha/preset/apply",
            PresetBody(device.room, mediaType, audioCodec, audioChannels),
        )
    }

    companion object {
        private val LAST_PLAYED = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

        /** Format attendu par le serveur (celui de Kodi) : « 2026-10-19 21:42:05 ». */
        fun nowLastPlayed(): String = LocalDateTime.now().format(LAST_PLAYED)
    }
}
