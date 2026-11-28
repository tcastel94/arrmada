package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Trakt (ADR-022) : note de fin de lecture, 5 étoiles à demi-étoiles = 1 à 10. */
class TraktLogicTest {

    @Test
    fun `demi-etoiles a la telecommande`() {
        assertEquals(1, TraktLogic.step(0, forward = true))
        assertEquals(0, TraktLogic.step(0, forward = false)) // jamais en dessous de 0
        assertEquals(10, TraktLogic.step(10, forward = true)) // ni au-dessus de 10
        assertEquals(6, TraktLogic.step(7, forward = false))
    }

    @Test
    fun `etoiles pleines, moitie, vides`() {
        // 7 = 3,5 étoiles
        val stars = (0 until 5).map { TraktLogic.star(it, 7) }
        assertEquals(
            listOf(TraktLogic.Star.FULL, TraktLogic.Star.FULL, TraktLogic.Star.FULL, TraktLogic.Star.HALF, TraktLogic.Star.EMPTY),
            stars,
        )
        assertTrue((0 until 5).all { TraktLogic.star(it, 0) == TraktLogic.Star.EMPTY })
        assertTrue((0 until 5).all { TraktLogic.star(it, 10) == TraktLogic.Star.FULL })
        assertEquals("3,5", TraktLogic.stars(7))
        assertEquals("4", TraktLogic.stars(8))
        assertEquals("Bien", TraktLogic.label(7))
        assertEquals("Chef-d'œuvre", TraktLogic.label(10))
        assertEquals("", TraktLogic.label(0))
    }

    @Test
    fun `quels titres se notent`() {
        assertTrue(TraktLogic.eligible("movie", 438631, localSeries = false))
        assertTrue(TraktLogic.eligible("episode", 280619, localSeries = false))
        assertFalse(TraktLogic.eligible("file", 0, localSeries = true)) // vidéo maison
        assertFalse(TraktLogic.eligible("episode", 280619, localSeries = true))
        assertFalse(TraktLogic.eligible("movie", 0, localSeries = false))
    }

    @Test
    fun `corps de la note selon l'etape`() {
        val episode = TraktLogic.body(TraktStep("episode", "Épisode S02E03"), 8, "episode", 280619, 2, 3, "The Expanse")
        assertEquals(TraktRateBody("episode", 8, null, 280619, 2, 3, "The Expanse"), episode)
        val season = TraktLogic.body(TraktStep("season", "Saison 2"), 7, "episode", 280619, 2, 3, "The Expanse")
        assertEquals(2, season.season)
        assertNull(season.episode)
        val show = TraktLogic.body(TraktStep("show", "La série"), 9, "episode", 280619, 2, 3, "The Expanse")
        assertNull(show.season)
        assertEquals(280619L, show.tvdbId)
        val movie = TraktLogic.body(TraktStep("movie", "Ce film"), 6, "movie", 438631, 0, 0, "Dune")
        assertEquals(TraktRateBody("movie", 6, 438631, null, null, null, "Dune"), movie)
    }

    @Test
    fun `adresse de la demande`() {
        assertEquals("/api/trakt/prompt?kind=movie", TraktLogic.promptPath("movie", 438631, 0, 0))
        assertEquals(
            "/api/trakt/prompt?kind=episode&tvdb_id=280619&season=2&episode=3",
            TraktLogic.promptPath("episode", 280619, 2, 3),
        )
    }
}
