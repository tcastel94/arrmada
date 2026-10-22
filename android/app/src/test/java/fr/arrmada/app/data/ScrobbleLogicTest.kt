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
}
