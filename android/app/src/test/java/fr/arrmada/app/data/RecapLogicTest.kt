package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.OffsetDateTime

/** « Précédemment dans… » : quand le proposer, et avec quel épisode. */
class RecapLogicTest {

    private val now = OffsetDateTime.parse("2026-10-23T20:00:00Z").toInstant().toEpochMilli()

    private fun ep(season: Int, number: Int, overview: String? = "Résumé $season-$number", hasFile: Boolean = true) =
        EpisodeInfo(seasonNumber = season, episodeNumber = number, title = "E$number", overview = overview, hasFile = hasFile)

    private val series = SeriesDetail(
        title = "The Bear", tvdbId = 403245,
        seasons = listOf(
            SeasonInfo(seasonNumber = 0, episodes = listOf(ep(0, 1))),
            SeasonInfo(seasonNumber = 1, episodes = listOf(ep(1, 2), ep(1, 1))),
            SeasonInfo(seasonNumber = 2, episodes = listOf(ep(2, 1), ep(2, 2, overview = null))),
        ),
    )

    private fun seen(daysAgo: Long, episode: Int = 1, id: String = "403245") = WatchState(
        mediaType = "episode", idType = "tvdb", id = id, season = 1, episode = episode, watched = true,
        updatedAt = OffsetDateTime.parse("2026-10-23T20:00:00Z").minusDays(daysAgo).toString(),
    )

    @Test
    fun onlyForAnEpisodeFromTheStart() {
        assertTrue(RecapLogic.applies("episode", 0, "7"))
        assertFalse(RecapLogic.applies("episode", 120, "7")) // reprise en cours d'épisode
        assertFalse(RecapLogic.applies("movie", 0, "7"))
        assertFalse(RecapLogic.applies("episode", 0, null)) // pas de fiche Sonarr
    }

    @Test
    fun previousEpisodeCrossesSeasonsAndSkipsSpecials() {
        assertEquals(1 to 2, RecapLogic.previous(series, 2, 1)?.let { it.seasonNumber to it.episodeNumber })
        assertEquals(1 to 1, RecapLogic.previous(series, 1, 2)?.let { it.seasonNumber to it.episodeNumber })
        assertNull(RecapLogic.previous(series, 1, 1)) // tout premier épisode
    }

    @Test
    fun shownAfterAWeekAway() {
        val recap = RecapLogic.recap(series, listOf(seen(12), seen(30, 2)), 403245, 2, 1, now)!!
        assertEquals("S01E02", recap.code)
        assertEquals(12, recap.awayDays)
        assertEquals("The Bear", recap.seriesTitle)
    }

    @Test
    fun notShownWhenRecentNeverWatchedOrAlreadyShown() {
        assertNull(RecapLogic.recap(series, listOf(seen(3)), 403245, 2, 1, now)) // regardée il y a 3 jours
        assertNull(RecapLogic.recap(series, listOf(seen(30, id = "1")), 403245, 2, 1, now)) // autre série
        assertNull(RecapLogic.recap(series, emptyList(), 403245, 2, 1, now)) // jamais regardée
        assertNull(RecapLogic.recap(series, listOf(seen(30)), 403245, 2, 1, now, shownRecently = true))
        assertNull(RecapLogic.recap(series, listOf(seen(30)), 403245, 1, 1, now)) // rien avant S01E01
    }

    @Test
    fun startedButUnwatchedCountsButUntouchedDoesNot() {
        val started = seen(20).copy(watched = false, position = 300)
        assertEquals(20, RecapLogic.recap(series, listOf(started), 403245, 2, 1, now)?.awayDays)
        val untouched = seen(20).copy(watched = false, position = 0)
        assertNull(RecapLogic.recap(series, listOf(untouched), 403245, 2, 1, now))
    }

    @Test
    fun awayLabels() {
        assertEquals("il y a 9 jours", RecapLogic.awayLabel(9))
        assertEquals("il y a 3 semaines", RecapLogic.awayLabel(21))
        assertEquals("il y a 4 mois", RecapLogic.awayLabel(125))
    }
}
