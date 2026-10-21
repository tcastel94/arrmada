package fr.arrmada.app.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDateTime
import java.time.ZoneOffset

/** Règles des écrans de la phase 3 (mêmes résultats que les tests de l'add-on). */
class LiveLogicTest {
    private val utc = ZoneOffset.UTC
    private val now = LocalDateTime.of(2026, 10, 21, 20, 47, 10)
    private val nbsp = ' '

    // ── Mise en forme ──

    @Test
    fun `nombres, octets et durées à la française`() {
        assertEquals("3${nbsp}412", Fr.int(3412))
        assertEquals("1 film", Fr.plural(1, "film"))
        assertEquals("0 série", Fr.plural(0, "série"))
        assertEquals("2${nbsp}séries".replace(nbsp, ' '), Fr.plural(2, "série"))
        assertEquals("1,5${nbsp}Go", Fr.bytes(1.5 * 1024 * 1024 * 1024))
        assertEquals("512${nbsp}Ko", Fr.bytes(512.0 * 1024))
        assertEquals("1 h 02", Fr.timeLeft("01:02:03"))
        assertEquals("26 h 03", Fr.timeLeft("1.02:03:04"))
        assertEquals("12 min", Fr.timeLeft("00:12:00"))
        assertEquals("< 1 min", Fr.timeLeft("00:00:20"))
        assertEquals("il y a 4 min", Fr.ago("2026-10-21T20:43:00+00:00", now, utc))
        assertEquals("à 08:00", Fr.ago("2026-10-21T08:00:00Z", now, utc))
        assertEquals("Bonsoir", Fr.greeting(21))
    }

    // ── Téléchargements ──

    @Test
    fun `carte en téléchargement, prêt vers, étapes, torrent`() {
        val card = BoardCard(
            title = "Dune", phase = "downloading", progress = 60.0, timeLeftSeconds = 720, deviceName = "Salon TV",
            requestedAt = "2026-10-21T20:43:05+00:00", quality = "Bluray-2160p", protocol = "torrent", arrId = 1, canCancel = true,
        )
        val view = BoardLogic.card(card, now, utc)
        // 20:47:10 + 12 min + 2 min = 21:01:10 → 21:02
        assertEquals("Prêt vers 21:02", view.headline)
        assertEquals("60 % · torrent : pas de priorité possible", view.detail)
        assertEquals("Salon TV · il y a 4 min · Bluray-2160p", view.who)
        assertEquals(BoardLogic.Step.NOW, view.steps[1])
        assertEquals(listOf(BoardLogic.Action.DETAIL, BoardLogic.Action.CANCEL), view.actions)
    }

    @Test
    fun `carte bloquée, prête, introuvable`() {
        val blocked = BoardLogic.card(BoardCard(phase = "blocked", progress = 100.0, error = "Import impossible", blockedDownload = BlockedDownload("radarr", "x")), now, utc)
        assertEquals("Bloqué", blocked.headline)
        assertEquals(BoardLogic.Step.ERROR, blocked.steps[2])
        assertEquals(BoardLogic.Action.UNSTICK, blocked.actions.first())
        val ready = BoardLogic.card(BoardCard(phase = "ready", subtitles = "fr"), now, utc)
        assertEquals("Prêt à regarder", ready.headline)
        assertEquals("Sous-titres français", ready.detail)
        assertEquals(BoardLogic.Tone.READY, ready.tone)
        val noSubs = BoardLogic.card(BoardCard(phase = "ready", subtitles = "off"), now, utc)
        assertEquals(BoardLogic.Step.TODO, noSubs.steps[3])
        val notFound = BoardLogic.card(BoardCard(phase = "notfound"), now, utc)
        assertEquals(listOf(BoardLogic.Action.SEARCH), notFound.actions)
    }

    @Test
    fun `ligne de file, état, actions SABnzbd, résumé`() {
        val paused = QueueItem(title = "X", status = "paused", trackedState = "downloading", protocol = "usenet", downloadId = "SAB_1", serviceType = "radarr", movieId = 3, progress = 40.0, sizeBytes = 100.0, sizeLeftBytes = 60.0, timeLeft = "00:12:00")
        val row = BoardLogic.row(paused, speed = 5.0 * 1024 * 1024)
        assertEquals("En pause", row.label)
        assertEquals(listOf(BoardLogic.Action.TOP, BoardLogic.Action.RESUME, BoardLogic.Action.DETAIL), row.actions)
        assertEquals("12 min · 5,0${nbsp}Mo/s", row.eta)
        val importing = BoardLogic.status(QueueItem(status = "completed", trackedState = "importPending"))
        assertEquals("Import en attente" to BoardLogic.Family.IMPORT, importing)
        val failed = BoardLogic.row(QueueItem(error = "Fichier corrompu", downloadId = "h", protocol = "torrent"))
        assertEquals(BoardLogic.Family.ERROR, failed.family)
        assertEquals("Fichier corrompu", failed.meta)
        assertEquals(listOf(BoardLogic.Action.UNSTICK), failed.actions)
        val board = Board(tonight = listOf(BoardCard(status = "open")), queue = listOf(paused), sab = SabInfo(paused = true, kbpersec = 1024.0))
        assertEquals("1 pour ce soir · 1 en file · 1,0${nbsp}Mo/s · SABnzbd en pause (sauf ce soir)", BoardLogic.summary(board))
        assertEquals("OK : En tête · Reprendre · Fiche", BoardLogic.hint(row.actions))
    }

    // ── Événements ──

    private fun event(id: String, type: String, vararg data: Pair<String, Any?>) = ServerEvent(
        id = id, type = type,
        data = buildJsonObject {
            data.forEach { (k, v) ->
                when (v) {
                    is String -> put(k, v)
                    is Number -> put(k, v)
                    is Boolean -> put(k, v)
                }
            }
        },
    )

    @Test
    fun `curseur, premier passage muet, redémarrage du serveur`() {
        val cursor = EventLogic.Cursor()
        val old = EventsPage(listOf(event("41", "new_import")), bootId = "a", lastId = 41)
        assertTrue(cursor.accept(old).isEmpty())
        assertEquals(41, cursor.sinceId)
        val next = EventsPage(listOf(event("42", "new_import")), bootId = "a", lastId = 42)
        assertEquals(1, cursor.accept(next).size)
        val restarted = EventsPage(listOf(event("1", "x"), event("2", "y")), bootId = "b", lastId = 2)
        assertEquals(2, cursor.accept(restarted).size)
        assertEquals(2, cursor.sinceId)
    }

    @Test
    fun `bulles comme l'add-on`() {
        val imported = EventLogic.bubble(event("1", "new_import", "event" to "Download", "title" to "Dune", "quality" to "Bluray-2160p", "size" to 7.5 * 1024 * 1024 * 1024, "poster" to "https://img/p.jpg"))!!
        assertEquals("Importé sur le NAS", imported.heading)
        assertEquals("Dune · Bluray-2160p · 7,5 Go", imported.message)
        assertEquals("https://img/p.jpg", imported.icon)
        val added = EventLogic.bubble(event("2", "new_import", "event" to "MovieAdded", "title" to "Dune", "year" to 2021))!!
        assertEquals("Dune (2021) · Radarr", added.message)
        assertTrue(EventLogic.bubble(event("3", "import_blocked", "title" to "Dune", "service" to "radarr"))!!.error)
        assertNull(EventLogic.bubble(event("4", "download_update", "title" to "Dune")))
        val three = listOf("A", "B", "C").map { EventLogic.Bubble("Importé sur le NAS", "$it · 1080p", title = it) }
        assertEquals(listOf(EventLogic.Bubble("3 nouveautés ArrMada", "A, B, C", title = "A, B, C")), EventLogic.merge(three))
        assertEquals("Pendant ta séance · Importé sur le NAS", EventLogic.merge(three.take(1), "Pendant ta séance").single().heading)
    }

    @Test
    fun `annonce pour cette TV seulement, et récente`() {
        assertTrue(EventLogic.forMe(3, 3, "2026-10-21T20:46:00+00:00", now, utc))
        assertFalse(EventLogic.forMe(4, 3, "2026-10-21T20:46:00+00:00", now, utc))
        assertFalse(EventLogic.forMe(3, 3, "2026-10-21T20:40:00+00:00", now, utc))
        val json = Json { ignoreUnknownKeys = true }
        val ready = json.decodeFromString(PlayAnnounce.serializer(), """{"device_id":3,"title":"Severance","media_type":"episode","id":"371980","season":2,"episode":5,"quality":"WEBDL-2160p","subtitles":"fr","at":"x"}""")
        assertEquals(371980L, ready.externalId)
        assertEquals("Severance S02E05", EventLogic.readyTitle(ready))
        assertEquals("WEBDL-2160p · sous-titres français", EventLogic.readyDetail(ready))
        assertEquals("Entrée · 21:42", EventLogic.cameraSubtitle(CameraEvent(camera = "Entrée", at = "2026-10-21T21:42:05+00:00"), now, utc))
        assertEquals("On sonne à la porte", EventLogic.cameraLabel(CameraEvent(detection = "ring")))
    }

    // ── Ampli (menu pause) ──

    @Test
    fun `ampli, résumé et programmes`() {
        assertEquals("−42,5 dB", AmpLogic.decibels(-42.5))
        assertEquals("Surround Decoder", AmpLogic.programName("surr_decoder"))
        val amp = AmpDevice(online = true, volumePct = 42, actualDb = -38.5, soundProgram = "drama", mute = true)
        assertEquals("42 % · −38,5 dB · Drama · muet", AmpLogic.summary(amp))
        assertTrue(AmpLogic.PROGRAMS.any { it.first == "straight" })
    }

    // ── Tableau de bord ──

    @Test
    fun `stockage dédoublonné et résumé`() {
        val tb = 1024L * 1024 * 1024 * 1024
        val dash = Dashboard(
            stats = DashStats(movies = 3412, series = 186, totalSize = "42.1 TB"),
            disks = listOf(Disk("/mnt/user", 60 * tb, 13 * tb), Disk("/mnt/user", 60 * tb, 13 * tb), Disk("/data", 60 * tb, 13 * tb)),
            downloads = listOf(DashDownload("A", 60.0, "00:12:00", "radarr")),
            downloadsCount = 3,
        )
        val storage = DashboardLogic.storage(dash)
        assertEquals(78, storage.usedPct)
        assertEquals("78 % · 13,0${nbsp}To libres", storage.hint)
        assertEquals("3${nbsp}412 films · 186 séries · 42.1 TB · 3 téléchargements en cours", DashboardLogic.summary(dash))
        assertEquals("60 % · 12 min · Radarr", DashboardLogic.downloadMeta(dash.downloads[0]))
    }

    // ── Ce soir ──

    @Test
    fun `ce soir, horaires et ce qui tient avant`() {
        val slots = TonightLogic.slots(now)
        assertEquals(listOf("Avant 22:00", "Avant 22:30", "Avant 23:00", "Avant 23:30", "Avant minuit", "Sans limite"), slots.map { it.label })
        assertEquals(2, TonightLogic.defaultSlot(slots, now)) // 23:00 laisse 2 h
        val movies = listOf(
            LibraryItem(externalId = "1", tmdbId = 1, title = "Court", hasFile = true, runtime = 60),
            LibraryItem(externalId = "2", tmdbId = 2, title = "Long", hasFile = true, runtime = 150),
            LibraryItem(externalId = "3", tmdbId = 3, title = "Vu", hasFile = true, runtime = 90),
        )
        val states = listOf(
            WatchState(mediaType = "movie", id = "3", watched = true),
            WatchState(mediaType = "movie", id = "2", position = 3600, total = 9000, updatedAt = "2026-10-21T19:00:00"),
        )
        val rows = TonightLogic.candidates(states, movies, emptyList())
        assertEquals(listOf("Long", "Court"), rows.map { it.title }) // commencé d'abord, « Vu » écarté
        val before22 = TonightLogic.rows(rows, slots[0], now)
        assertEquals(listOf("Court"), before22.map { it.title })
        assertEquals("1 h 00 · fini vers 21:47", TonightLogic.status(before22[0], now))
        assertEquals("Reprise à 1:00:00 · reste 1 h 30 · fini vers 22:17", TonightLogic.status(rows[0], now))
    }
}
