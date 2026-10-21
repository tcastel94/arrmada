package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class HomeRowsLogicTest {
    private val absolute: (String?) -> String? = { it?.let { url -> if (url.startsWith("/api/")) "http://nas:8420$url" else url } }

    private val dune = LibraryItem(externalId = "12", tmdbId = 438631, title = "Dune", type = "movie", posterUrl = "https://image.tmdb.org/t/p/original/dune.jpg", overview = "Arrakis.")
    private val expanse = LibraryItem(externalId = "42", title = "The Expanse", type = "series", posterUrl = "/api/kodi/artwork/42/poster")

    @Test
    fun `À suivre, film et épisode commencés, avec position et lien de reprise`() {
        val cards = HomeRowsLogic.resumeCards(
            listOf(
                WatchState(mediaType = "movie", id = "438631", position = 2530, total = 9300, lastPlayed = "2026-10-21T20:00:00+00:00") to dune,
                WatchState(mediaType = "episode", idType = "tvdb", id = "280619", season = 2, episode = 4, title = "Static", position = 1300, total = 2700, updatedAt = "2026-10-20T19:00:00") to expanse,
            ),
            absolute,
        )
        assertEquals(2, cards.size)
        val movie = cards[0]
        assertEquals("resume:movie:438631", movie.key)
        assertEquals(2_530_000L, movie.positionMs)
        assertEquals(9_300_000L, movie.durationMs)
        assertEquals(HomeRowsLogic.epochMillis("2026-10-21T20:00:00Z"), movie.lastWatchedMs)
        assertEquals(
            HomeLink.Play("movie", 438631, 0, 0, 2530, radarrId = "12", sonarrId = null),
            HomeRowsLogic.parse(movie.link),
        )
        val episode = cards[1]
        assertEquals("resume:episode:280619:2:4", episode.key)
        assertEquals("The Expanse", episode.title)
        assertEquals("Static", episode.episodeTitle)
        assertEquals(2, episode.season)
        assertEquals("http://nas:8420/api/kodi/artwork/42/poster", episode.poster)
        assertEquals(HomeLink.Play("episode", 280619, 2, 4, 1300, radarrId = null, sonarrId = "42"), HomeRowsLogic.parse(episode.link))
    }

    @Test
    fun `À suivre, ni vus, ni pas commencés, ni sans identifiant`() {
        val cards = HomeRowsLogic.resumeCards(
            listOf(
                WatchState(mediaType = "movie", id = "1", position = 100, total = 200, watched = true) to null,
                WatchState(mediaType = "movie", id = "2", position = 0, total = 200) to null,
                WatchState(mediaType = "movie", id = "", position = 50, total = 200) to null,
                WatchState(mediaType = "movie", id = "abc", position = 50, total = 200) to null,
                WatchState(mediaType = "movie", id = "3", title = "Tenet", position = 50, total = 200) to null,
            ),
            absolute,
        )
        assertEquals(listOf("Tenet"), cards.map { it.title })
        assertNull(cards[0].poster)
    }

    @Test
    fun `chaîne ArrMada, liens vers la fiche, sans doublon, 20 au plus`() {
        val items = listOf(dune, dune, expanse) + (1..30).map { LibraryItem(externalId = "x$it", title = "Film $it", type = "movie") }
        val cards = HomeRowsLogic.recentCards(items, absolute)
        assertEquals(HomeRowsLogic.MAX_RECENT, cards.size)
        assertEquals(listOf("Dune", "The Expanse"), cards.take(2).map { it.title })
        assertEquals(HomeLink.Movie("12", 438631), HomeRowsLogic.parse(cards[0].link))
        assertEquals(HomeLink.Show("42"), HomeRowsLogic.parse(cards[1].link))
        assertEquals("series", cards[1].kind)
    }

    @Test
    fun `liens refusés`() {
        assertNull(HomeRowsLogic.parse(null))
        assertNull(HomeRowsLogic.parse("https://example.org/play?kind=movie&id=1"))
        assertNull(HomeRowsLogic.parse("arrmada://play?kind=movie&id=0"))
        assertNull(HomeRowsLogic.parse("arrmada://play?kind=album&id=5"))
        assertNull(HomeRowsLogic.parse("arrmada://movie"))
        assertNull(HomeRowsLogic.parse("arrmada://inconnu"))
        assertEquals(HomeLink.Home, HomeRowsLogic.parse("arrmada://home"))
        // Position négative ramenée au début
        val play = HomeRowsLogic.parse("arrmada://play?kind=movie&id=5&start=-20") as HomeLink.Play
        assertEquals(0, play.startSeconds)
    }

    @Test
    fun `identifiant avec caractères spéciaux, aller-retour`() {
        val link = HomeRowsLogic.playLink(HomeLink.Play("movie", 7, 0, 0, 10, radarrId = "a&b=c", sonarrId = null))
        assertTrue(link.startsWith("arrmada://play?"))
        assertEquals("a&b=c", (HomeRowsLogic.parse(link) as HomeLink.Play).radarrId)
    }

    @Test
    fun `dates du serveur`() {
        assertEquals(0L, HomeRowsLogic.epochMillis(""))
        assertEquals(0L, HomeRowsLogic.epochMillis("pas une date"))
        assertEquals(HomeRowsLogic.epochMillis("2026-10-20T19:00:00Z"), HomeRowsLogic.epochMillis("2026-10-20T19:00:00"))
    }
}
