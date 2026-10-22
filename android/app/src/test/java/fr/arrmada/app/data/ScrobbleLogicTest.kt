package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Écran d'appoint : « lecture en cours » envoyée comme l'add-on Kodi. */
class ScrobbleLogicTest {

    private val dune = ScrobbleLogic.identity("movie", 438631, 0, 0, "Dune", null, localSeries = false)
    private val expanse = ScrobbleLogic.identity("episode", 280619, 2, 3, "The Expanse", "S02E03 · Static", localSeries = false)

    @Test
    fun `film et episode`() {
        assertEquals("movie", dune.mediaType)
        assertEquals(438631L, dune.tmdbId)
        assertNull(dune.season)
        assertEquals("episode", expanse.mediaType)
        assertNull(expanse.tmdbId) // TVDB : pas un identifiant TMDB
        assertEquals(2, expanse.season)
        assertEquals(3, expanse.episode)
        assertEquals("Static", expanse.episodeTitle)
        // Série maison (Naruto Kai) : un épisode, même lu comme un fichier
        val kai = ScrobbleLogic.identity("file", 0, 2, 15, "Naruto Kai", "S02E15", localSeries = true)
        assertEquals("episode", kai.mediaType)
        assertEquals(15, kai.episode)
    }

    @Test
    fun `progression et pause`() {
        val progress = ScrobbleLogic.payload("progress", dune, 1500.6, 3000.0, paused = true)
        assertEquals(50.0, progress.percentage, 0.0)
        assertEquals(1500, progress.position)
        assertEquals(3000, progress.total)
        assertTrue(progress.paused!!)
        assertTrue(ScrobbleLogic.payload("pause", dune, 10.0, 3000.0).paused!!)
        assertEquals(0.0, ScrobbleLogic.payload("play", dune, 0.0, 0.0).percentage, 0.0) // durée inconnue
    }

    @Test
    fun `stop - au bout ou pourcentage atteint`() {
        assertEquals(100.0, ScrobbleLogic.payload("stop", dune, 2990.0, 3000.0, ended = true).percentage, 0.0)
        val quit = ScrobbleLogic.payload("stop", dune, 600.0, 3000.0)
        assertEquals(20.0, quit.percentage, 0.0)
        assertNull(quit.position)
    }

    @Test
    fun `format de l'image`() {
        assertEquals("4K · Dolby Vision", ScrobbleLogic.videoLabel(2160, emptyList(), "DOVI", toneMapped = false))
        assertEquals("4K · SDR (converti)", ScrobbleLogic.videoLabel(2160, emptyList(), "DOVI", toneMapped = true))
        assertEquals("1080p · HDR10+", ScrobbleLogic.videoLabel(1080, emptyList(), "HDR10Plus", toneMapped = false))
        // Piste pas encore connue : pastilles de la fiche Radarr
        assertEquals("4K · HDR", ScrobbleLogic.videoLabel(null, listOf("4K", "HDR", "Atmos"), "", toneMapped = false))
        assertEquals("SD", ScrobbleLogic.videoLabel(480, emptyList(), "SDR", toneMapped = false))
    }

    @Test
    fun `chapitre en cours, sauf les noms sans interet`() {
        val chapters = listOf(Chapter(0, "Ouverture", 0.0), Chapter(1, "Arrakis", 600.0), Chapter(2, "Chapitre 3", 1200.0))
        assertEquals("Ouverture", ScrobbleLogic.chapterAt(chapters, 10.0))
        assertEquals("Arrakis", ScrobbleLogic.chapterAt(chapters, 900.0))
        assertEquals("", ScrobbleLogic.chapterAt(chapters, 1300.0))
        assertEquals("", ScrobbleLogic.chapterAt(emptyList(), 10.0))
    }

    @Test
    fun `stop sans la fiche ni les pistes`() {
        val rich = dune.copy(overview = "Arrakis…", remote = true, audioTracks = listOf(ScrobbleTrack(0, "Français")))
        val stop = ScrobbleLogic.payload("stop", rich, 100.0, 3000.0)
        assertEquals("", stop.overview)
        assertTrue(stop.audioTracks.isEmpty())
        assertEquals("Dune", stop.title)
        assertTrue(ScrobbleLogic.payload("progress", rich, 100.0, 3000.0).remote)
    }

    @Test
    fun `commandes de la tablette`() {
        val json = kotlinx.serialization.json.Json { ignoreUnknownKeys = true }
        val page = json.decodeFromString(
            RemotePage.serializer(),
            """{"last_id": 7, "commands": [
                {"id": 6, "action": "seek", "value": -10},
                {"id": 7, "action": "track", "value": {"type": "text", "index": -1}},
                {"id": 8, "action": "toggle", "value": null}]}""",
        )
        assertEquals(7L, page.lastId)
        assertEquals(-10, page.commands[0].seconds)
        assertEquals("text" to -1, page.commands[1].track)
        assertNull(page.commands[2].seconds)
        assertNull(page.commands[2].track)
    }
}
