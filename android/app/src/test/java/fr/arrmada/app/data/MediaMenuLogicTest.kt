package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Appui long sur une carte : actions proposées, libellés, état « vu » envoyé. */
class MediaMenuLogicTest {

    private val dune = LibraryItem(externalId = "12", tmdbId = 438631, title = "Dune", type = "movie", year = 2021, hasFile = true, posterUrl = "/api/img/dune")
    private val expanse = LibraryItem(externalId = "7", tmdbId = 280619, title = "The Expanse", type = "series", hasFile = true)

    @Test
    fun movieOnDisk() {
        val target = MediaMenuLogic.of(dune)
        assertEquals(438631L, target.tmdbId)
        assertNull(target.tvdbId)
        assertEquals(
            listOf(MenuAction.PLAY, MenuAction.OPEN, MenuAction.TRAILER, MenuAction.ADD_TO_LIST, MenuAction.MARK_WATCHED),
            MediaMenuLogic.actions(target, inList = false, watched = false),
        )
        assertEquals(
            listOf(MenuAction.PLAY, MenuAction.OPEN, MenuAction.TRAILER, MenuAction.REMOVE_FROM_LIST, MenuAction.MARK_UNWATCHED),
            MediaMenuLogic.actions(target, inList = true, watched = true),
        )
        assertEquals("Film · 2021", MediaMenuLogic.subtitle(target))
    }

    @Test
    fun seriesUsesTvdbForTheList() {
        val target = MediaMenuLogic.of(expanse)
        assertEquals(280619L, target.tvdbId) // « tmdb_id » d'une série = TVDB
        assertNull(target.tmdbId)
        assertEquals("series:tvdb:280619", target.watchlist?.key)
        assertEquals(listOf(MenuAction.OPEN, MenuAction.ADD_TO_LIST), MediaMenuLogic.actions(target, inList = false, watched = null))
        assertEquals("Ouvrir la série", MediaMenuLogic.label(MenuAction.OPEN, target))
    }

    @Test
    fun localSeriesOnlyOpens() {
        val kai = LibraryItem(externalId = LocalSeriesLogic.PREFIX + "3", title = "Naruto Kai", type = "series", hasFile = true)
        val target = MediaMenuLogic.of(kai)
        assertEquals(3, target.localSeries)
        assertNull(target.arrId)
        assertNull(target.watchlist)
        assertEquals(listOf(MenuAction.OPEN), MediaMenuLogic.actions(target, inList = false, watched = null))
    }

    @Test
    fun watchlistTitleNotDownloadedYet() {
        val item = WatchlistItem(key = "movie:tmdb:1", mediaType = "movie", tmdbId = 1, title = "Arrival", mediaId = null, hasFile = false)
        assertEquals(listOf(MenuAction.TRAILER, MenuAction.REMOVE_FROM_LIST), MediaMenuLogic.actions(MediaMenuLogic.of(item), inList = true, watched = false))
    }

    @Test
    fun resumeCardOfAnEpisode() {
        val state = WatchState(mediaType = "episode", idType = "tvdb", id = "280619", season = 2, episode = 3, title = "Static", position = 1200, total = 2700)
        val target = MediaMenuLogic.of(ResumeEntry(state, expanse))
        assertEquals(280619L, target.tvdbId)
        assertEquals(
            listOf(MenuAction.RESUME, MenuAction.FROM_START, MenuAction.OPEN, MenuAction.ADD_TO_LIST, MenuAction.MARK_WATCHED),
            MediaMenuLogic.actions(target, inList = false, watched = MediaMenuLogic.watched(target, emptyList())),
        )
        assertEquals("Reprendre à 20:00", MediaMenuLogic.label(MenuAction.RESUME, target))
        assertEquals("Marquer l’épisode comme vu", MediaMenuLogic.label(MenuAction.MARK_WATCHED, target))
        assertEquals("S02E03 · Static", MediaMenuLogic.subtitle(target))
        val update = MediaMenuLogic.watchedUpdate(target, true, "2026-10-28 21:00:00")!!
        assertEquals(WatchStateUpdate("episode", "tvdb", "280619", 2, 3, "Static", true, 0, 2700, "2026-10-28 21:00:00"), update)
    }

    @Test
    fun movieWatchedStateAndUpdate() {
        val target = MediaMenuLogic.of(dune)
        val states = listOf(WatchState(mediaType = "movie", id = "438631", watched = true), WatchState(mediaType = "episode", id = "438631"))
        assertEquals(true, MediaMenuLogic.watched(target, states))
        assertEquals(false, MediaMenuLogic.watched(target, emptyList()))
        assertNull(MediaMenuLogic.watched(MediaMenuLogic.of(expanse), states))
        val update = MediaMenuLogic.watchedUpdate(target, false, "now")!!
        assertEquals("movie", update.mediaType)
        assertEquals("tmdb", update.idType)
        assertEquals("438631", update.id)
        assertEquals(false, update.watched)
        assertNull(MediaMenuLogic.watchedUpdate(MediaMenuLogic.of(expanse), true, "now"))
    }

    @Test
    fun localVideoResumeIsNotMarkedFromHere() {
        val state = WatchState(mediaType = "file", id = "abc", position = 100, total = 1000)
        val target = MediaMenuLogic.of(ResumeEntry(state, null, file = "tok", localSeries = 3))
        assertNull(MediaMenuLogic.watchedUpdate(target, true, "now"))
        assertEquals(listOf(MenuAction.RESUME, MenuAction.FROM_START, MenuAction.OPEN), MediaMenuLogic.actions(target, inList = false, watched = false))
    }
}
