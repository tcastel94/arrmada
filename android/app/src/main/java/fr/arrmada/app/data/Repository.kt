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

    /** Ce que la web app affiche pour cet appareil (« ArrMada Android TV », « … (téléphone) »). */
    var kindLabel: String = " TV"

    suspend fun pairStart(): PairStart =
        api.post("/api/devices/pair/start", PairStartBody("ArrMada Android$kindLabel · ${Build.MANUFACTURER} ${Build.MODEL}"))

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

    // ── Fiches : gardées 2 min en mémoire ──
    // Revenir sur une fiche, ou l'ouvrir après l'avoir survolée (préchargement),
    // est alors instantané. Comme un cache disque côté système : on sert la
    // copie récente, on ne relit le serveur qu'une fois la copie périmée.
    private val details = java.util.concurrent.ConcurrentHashMap<String, Pair<Long, Any>>()

    @Suppress("UNCHECKED_CAST")
    private suspend fun <T : Any> cached(key: String, ttlMs: Long, fresh: Boolean, load: suspend () -> T): T {
        val hit = details[key]
        if (!fresh && hit != null && System.currentTimeMillis() - hit.first < ttlMs) return hit.second as T
        return load().also { details[key] = System.currentTimeMillis() to it }
    }

    suspend fun movie(radarrId: String, fresh: Boolean = false): MovieDetail =
        cached("movie:$radarrId", DETAIL_TTL, fresh) { api.get<MovieDetail>("/api/media/movie/$radarrId") }

    suspend fun series(sonarrId: String, fresh: Boolean = false): SeriesDetail =
        cached("series:$sonarrId", DETAIL_TTL, fresh) { api.get<SeriesDetail>("/api/media/series/$sonarrId") }

    /**
     * Précharge la fiche d'un titre survolé (et, pour un film, s'il se lit
     * dans Jellyfin) : quand on appuie sur OK, tout est déjà là.
     */
    suspend fun prefetch(item: LibraryItem) {
        if (item.externalId.isBlank()) return
        if (item.isMovie) {
            movie(item.externalId)
            item.tmdbId?.let { playMovie(it) }
        } else {
            series(item.externalId)
        }
    }

    /** Épisodes d'une saison présents dans Jellyfin (vignettes, durées). */
    suspend fun seasonEpisodes(tvdbId: Long, season: Int): SeasonEpisodes =
        api.get("/api/tv/series/$tvdbId/season/$season")

    // ── Vu / reprise ──
    // États vu / reprise gardés en mémoire : le premier appel relit tout, les
    // suivants ne demandent que ce qui a changé depuis (curseur du serveur,
    // comme un « rsync » incrémental).
    private val states = LinkedHashMap<String, WatchState>()
    private var statesCursor = ""
    private val statesLock = kotlinx.coroutines.sync.Mutex()

    /** Tous les états partagés (premier passage page par page, 500 par page). */
    suspend fun watchStates(): List<WatchState> = statesLock.withLock {
        do {
            val since = if (statesCursor.isNotEmpty()) "?since=" + java.net.URLEncoder.encode(statesCursor, "UTF-8") else ""
            val page: WatchStates = api.get("/api/kodi/watch-state$since")
            page.states.forEach { states[stateKey(it)] = it }
            if (page.cursor.isNotEmpty()) statesCursor = page.cursor
        } while (page.more && page.cursor.isNotEmpty())
        states.values.toList()
    }

    private fun stateKey(s: WatchState) = "${s.mediaType}|${s.idType}|${s.id}|${s.season}|${s.episode}"

    suspend fun saveWatchState(update: WatchStateUpdate) {
        api.post<kotlinx.serialization.json.JsonObject, WatchStatePost>("/api/kodi/watch-state", WatchStatePost(listOf(update)))
        // La reprise d'un film a changé : sa prochaine lecture relit le serveur
        if (update.mediaType == "movie") details.remove("play:${update.id}")
    }

    /**
     * Rangée « Reprendre » : titres commencés et pas finis, du plus récent au
     * plus ancien, rapprochés de la médiathèque pour avoir leurs images.
     */
    suspend fun resumeRow(states: List<WatchState>, movies: List<LibraryItem>, series: List<LibraryItem>): List<ResumeEntry> {
        val moviesByTmdb = movies.associateBy { it.tmdbId?.toString() }
        val seriesByTvdb = series.associateBy { it.tmdbId?.toString() } // tmdb_id = TVDB pour une série
        return states
            // Les vidéos de l'écran Vidéos n'ont ni fiche ni affiche : pas dans Reprendre
            .filter { !it.watched && it.position > 0 && it.mediaType != "file" }
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
    /** Infos de lecture d'un film (gardées 30 s : le préchargement les sert à la fiche). */
    suspend fun playMovie(tmdbId: Long, fresh: Boolean = false): PlayInfo =
        cached("play:$tmdbId", PLAY_TTL, fresh) { api.get<PlayInfo>("/api/tv/play/movie/$tmdbId") }

    suspend fun playEpisode(tvdbId: Long, season: Int, episode: Int): PlayInfo =
        api.get("/api/tv/play/episode/$tvdbId/$season/$episode")

    /** Fin de lecture d'un remux : Jellyfin arrête la conversion. */
    suspend fun stopRemux(itemId: String) {
        api.post<kotlinx.serialization.json.JsonObject, kotlinx.serialization.json.JsonObject>(
            "/api/tv/hls/$itemId/stop",
            kotlinx.serialization.json.JsonObject(emptyMap()),
        )
    }

    // ── Téléchargements (écran de l'add-on) ──
    private val empty = kotlinx.serialization.json.JsonObject(emptyMap())
    private fun seg(text: String) = java.net.URLEncoder.encode(text, "UTF-8").replace("+", "%20")

    suspend fun board(): Board = api.get("/api/kodi/downloads/board")

    /** « top » (passer en tête), « pause », « resume » sur un élément SABnzbd. */
    suspend fun queueAction(downloadId: String, op: String): ActionResult =
        api.post("/api/kodi/queue/${seg(downloadId)}/$op", empty)

    suspend fun cancelRequest(requestId: Int): ActionResult = api.post("/api/kodi/tv-requests/$requestId/cancel", empty)

    suspend fun retryRequest(requestId: Int): ActionResult = api.post("/api/kodi/tv-requests/$requestId/retry", empty)

    suspend fun diagnose(service: String, downloadId: String): Diagnose =
        api.get("/api/kodi/downloads/$service/${seg(downloadId)}/diagnose")

    /** Débloque (import forcé, autre version…) : le serveur peut mettre 30 s à répondre. */
    suspend fun unstick(service: String, downloadId: String): ActionResult =
        api.post("/api/kodi/downloads/$service/${seg(downloadId)}/unstick", empty, slow = true)

    /** « Pause sauf ce soir » / « Tout reprendre » : toute la file SABnzbd. */
    suspend fun pauseAll(service: String): ActionResult = api.post("/api/kodi/downloads/$service/0/pause", empty)

    suspend fun resumeAll(service: String): ActionResult = api.post("/api/kodi/downloads/$service/0/resume", empty)

    // ── Ampli Yamaha (onglet « Ampli » du menu pause) ──
    suspend fun ampState(): AmpState = api.get("/api/yamaha/state")

    /** Profils des pièces (nom, enceintes « 5.1 » / « 7.2.2 »), relus toutes les 10 min au plus. */
    suspend fun roomProfiles(): Map<String, RoomProfile> =
        cached("rooms", 10 * 60_000L, false) { api.get<Map<String, RoomProfile>>("/api/yamaha/profiles") }

    suspend fun ampControl(action: String, value: kotlinx.serialization.json.JsonElement?): ActionResult =
        api.post("/api/yamaha/control", AmpControl(action, value))

    // ── Événements, caméra, tableau de bord, bande-annonce ──
    suspend fun events(sinceId: Long): EventsPage = api.get("/api/events/recent?since_id=$sinceId")

    suspend fun cameraSnapshot(id: Int): CameraSnapshot = api.get("/api/cameras/snapshot/$id")

    suspend fun dashboard(): Dashboard = api.get("/api/kodi/dashboard")

    // ── Téléphone / tablette : envoyer un titre sur une TV ──
    suspend fun playTargets(): List<PlayTarget> = api.get<PlayTargets>("/api/tv/targets").items

    suspend fun playOnTv(deviceId: Int, what: PlayOnTv): ActionResult = api.post("/api/tv/targets/$deviceId/play", what)

    // ── Profils famille (ADR-008) ──
    suspend fun profiles(): List<FamilyProfile> = api.get<FamilyProfiles>("/api/profiles").items

    /**
     * Changement de profil : on oublie ce qui dépend de qui regarde (vu /
     * reprise, infos de lecture) ; la médiathèque et les fiches restent.
     */
    suspend fun forgetViewer() {
        statesLock.withLock {
            states.clear()
            statesCursor = ""
        }
        details.keys.removeAll { it.startsWith("play:") }
    }

    suspend fun movieTrailer(tmdbId: Long): TrailerInfo =
        cached("trailer:$tmdbId", DETAIL_TTL, false) { api.get<TrailerInfo>("/api/tv/trailer/movie/$tmdbId") }

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

    /** Cette TV (pièce, ampli, identifiant), relue toutes les 10 min au plus. */
    /** Écran Vidéos : dossiers déclarés ([token] null) ou contenu d'un dossier. */
    suspend fun videos(token: String?): VideoListing =
        api.get("/api/videos/browse" + (token?.let { "?path=${q(it)}" } ?: ""))

    /** Infos de lecture d'une vidéo de l'écran Vidéos (même format qu'un film). */
    suspend fun playFile(token: String): PlayInfo = api.get("/api/videos/play/$token")

    /** Version plus récente de l'appli sur le serveur (ADR-009) pour ce type d'APK. */
    suspend fun updateOffer(versionCode: Int, buildType: String): UpdateOffer =
        api.get("/api/android/update?version_code=$versionCode&build_type=${q(buildType)}")

    suspend fun device(): Device = cached("me", 10 * 60_000L, false) { me() }

    companion object {
        private const val DETAIL_TTL = 2 * 60_000L
        private const val PLAY_TTL = 30_000L
        private val LAST_PLAYED = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

        /** Format attendu par le serveur (celui de Kodi) : « 2026-10-19 21:42:05 ». */
        fun nowLastPlayed(): String = LocalDateTime.now().format(LAST_PLAYED)
    }
}
