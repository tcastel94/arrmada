package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Liste « À voir » : clés, ordre de la rangée, ouverture d'une carte. */
class WatchlistLogicTest {

    @Test
    fun keysMatchTheServer() {
        assertEquals("movie:tmdb:693134", WatchlistLogic.key("movie", 693134))
        assertEquals("series:tvdb:403245", WatchlistLogic.key("series", 403245))
        assertEquals("movie:tmdb:1", WatchlistTarget("movie", 1, "Dune").key)
    }

    @Test
    fun readyTitlesFirstThenServerOrder() {
        val items = listOf(
            WatchlistItem(key = "a", hasFile = false),
            WatchlistItem(key = "b", hasFile = true),
            WatchlistItem(key = "c", hasFile = false),
            WatchlistItem(key = "d", hasFile = true),
        )
        assertEquals(listOf("b", "d", "a", "c"), WatchlistLogic.ordered(items).map { it.key })
    }

    @Test
    fun openTrackedTitleOrDownloadSheet() {
        val movie = WatchlistItem(mediaType = "movie", tmdbId = 1, mediaId = "12", hasFile = true)
        assertEquals(WatchlistOpen.Movie("12", 1), WatchlistLogic.open(movie))
        val show = WatchlistItem(mediaType = "series", tvdbId = 5, mediaId = "7")
        assertEquals(WatchlistOpen.Show("7"), WatchlistLogic.open(show))
        val missing = WatchlistLogic.open(WatchlistItem(mediaType = "series", tvdbId = 5, title = "The Bear", mediaId = ""))
        missing as WatchlistOpen.Download
        assertEquals("series", missing.target.kind)
        assertEquals(5L, missing.target.tvdbId)
        assertNull(missing.target.tmdbId)
    }

    @Test
    fun bodyCarriesTheRightIdAndOnlyWebPosters() {
        val movie = WatchlistTarget("movie", 42, "Dune", 2021, "https://img/p.jpg").body()
        assertEquals(42L, movie.tmdbId)
        assertNull(movie.tvdbId)
        assertEquals("https://img/p.jpg", movie.posterUrl)
        val series = WatchlistTarget("series", 7, "The Bear", poster = "/MediaCover/1/poster.jpg").body()
        assertEquals(7L, series.tvdbId)
        assertNull(series.posterUrl)
    }

    @Test
    fun notes() {
        assertEquals("Prêt à regarder", WatchlistLogic.note(WatchlistItem(hasFile = true, inLibrary = true)))
        assertEquals("Demandé : en attente de téléchargement", WatchlistLogic.note(WatchlistItem(inLibrary = true)))
        assertEquals("Pas encore sur le NAS", WatchlistLogic.note(WatchlistItem()))
    }

    @Test
    fun addedTitleComesFirstWithoutDuplicate() {
        val list = listOf(WatchlistItem(key = "movie:tmdb:1", title = "Dune"), WatchlistItem(key = "series:tvdb:5", title = "The Bear"))
        val target = WatchlistTarget("series", 5, "The Bear")
        val after = WatchlistLogic.added(list, WatchlistItem(key = "series:tvdb:5", mediaType = "series", title = "The Bear", hasFile = true), target)
        assertEquals(listOf("series:tvdb:5", "movie:tmdb:1"), after.map { it.key })
        assertEquals(true, after.first().hasFile)
    }

    @Test
    fun addedWithEmptyServerAnswerUsesTheSheet() {
        // Serveur ancien : réponse sans le titre ; la fiche sait ce qu'il faut
        val target = WatchlistTarget("movie", 438631, "Dune", 2021, "https://image.tmdb.org/dune.jpg")
        val after = WatchlistLogic.added(null, WatchlistItem(), target)
        val item = after.single()
        assertEquals("movie:tmdb:438631", item.key)
        assertEquals("Dune", item.title)
        assertEquals(438631L, item.tmdbId)
        assertNull(item.tvdbId)
        assertEquals("https://image.tmdb.org/dune.jpg", item.posterUrl)
    }

    @Test
    fun removedTitleLeavesTheRow() {
        val list = listOf(WatchlistItem(key = "a"), WatchlistItem(key = "b"))
        assertEquals(listOf("b"), WatchlistLogic.removed(list, "a").map { it.key })
        assertEquals(listOf("a", "b"), WatchlistLogic.removed(list, "zzz").map { it.key })
    }
}
