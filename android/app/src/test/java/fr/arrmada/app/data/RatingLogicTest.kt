package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Libellés des notes : la source toujours écrite, virgule française. */
class RatingLogicTest {

    @Test
    fun labels() {
        assertEquals("IMDb 8,5", RatingLogic.label(8.5, "imdb"))
        assertEquals("TMDB 7,1", RatingLogic.label(7.06, "tmdb"))
        assertEquals("TMDB 6,0", RatingLogic.label(6.0, null)) // serveur d'avant 2.13
        assertNull(RatingLogic.label(null, "imdb"))
        assertNull(RatingLogic.label(0.0, "imdb"))
        assertNull(RatingLogic.label(8.0, "inconnue"))
    }

    @Test
    fun detailBadgesPreferImdb() {
        assertEquals(
            listOf("IMDb 8,5", "Metacritic 79", "Rotten Tomatoes 93 %"),
            RatingLogic.detailBadges(Ratings(tmdb = 8.2, imdb = 8.5, rottenTomatoes = 93.0, metacritic = 79.0)),
        )
        assertEquals(listOf("TMDB 7,0"), RatingLogic.detailBadges(Ratings(tmdb = 7.0)))
        assertEquals(emptyList<String>(), RatingLogic.detailBadges(Ratings()))
    }
}
