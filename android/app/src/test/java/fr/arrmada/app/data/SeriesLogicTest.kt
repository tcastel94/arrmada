package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate

/** Règles de l'écran Série : « Lire la suite », statuts, enchaînement. */
class SeriesLogicTest {

    private fun ep(season: Int, number: Int, hasFile: Boolean = true, air: String? = "2020-01-01") =
        EpisodeInfo(id = season * 100 + number, seasonNumber = season, episodeNumber = number, title = "E$number", airDate = air, hasFile = hasFile)

    private val series = SeriesDetail(
        id = 42, title = "The Expanse", tvdbId = 280619,
        seasons = listOf(
            SeasonInfo(seasonNumber = 0, episodes = listOf(ep(0, 1))),
            SeasonInfo(seasonNumber = 2, episodes = listOf(ep(2, 1), ep(2, 2), ep(2, 3, hasFile = false, air = "2099-01-01"))),
            SeasonInfo(seasonNumber = 1, episodes = listOf(ep(1, 2), ep(1, 1), ep(1, 3, hasFile = false))),
        ),
    )

    private fun state(s: Int, e: Int, watched: Boolean = false, position: Int = 0, at: String = "2026-10-01T10:00:00+00:00") =
        WatchState(mediaType = "episode", idType = "tvdb", id = "280619", season = s, episode = e, watched = watched, position = position, total = 3000, updatedAt = at)

    private fun states(vararg list: WatchState) = SeriesLogic.statesBySeries(list.toList(), 280619)

    @Test
    fun `saisons dans l'ordre, speciaux a la fin`() {
        assertEquals(listOf(1, 2, 0), SeriesLogic.orderedSeasons(series).map { it.seasonNumber })
    }

    @Test
    fun `rien vu - premier episode disponible`() {
        val next = SeriesLogic.nextUp(series, states())!!
        assertEquals("S01E01", next.row.code)
        assertFalse(next.resume)
    }

    @Test
    fun `episode commence - reprendre`() {
        val next = SeriesLogic.nextUp(series, states(state(1, 1, watched = true), state(1, 2, position = 754)))!!
        assertTrue(next.resume)
        assertEquals("Reprendre S01E02 à 12:34", next.label)
    }

    @Test
    fun `suite du dernier vu en sautant le manquant`() {
        // S01E03 manquant : la suite de S01E02 est S02E01
        val next = SeriesLogic.nextUp(series, states(state(1, 1, true), state(1, 2, true)))!!
        assertEquals("S02E01", next.row.code)
    }

    @Test
    fun `tout vu - plus rien a lire`() {
        assertNull(SeriesLogic.nextUp(series, states(state(2, 2, watched = true))))
    }

    @Test
    fun `etats d'une autre serie ignores`() {
        val other = WatchState(mediaType = "episode", idType = "tvdb", id = "1", season = 1, episode = 1, watched = true)
        assertTrue(SeriesLogic.statesBySeries(listOf(other), 280619).isEmpty())
    }

    @Test
    fun `statuts et fichier double`() {
        val season2 = series.seasons.first { it.seasonNumber == 2 }
        val jellyfin = listOf(JellyfinEpisode(season = 2, episode = 1, episodeEnd = 2, itemId = "x", image = "/api/tv/item-image/x", runtime = 2700))
        val rows = SeriesLogic.rows(season2, jellyfin, states(state(2, 1, position = 900)), today = LocalDate.of(2026, 10, 21))
        assertEquals(listOf(EpisodeStatus.AVAILABLE, EpisodeStatus.AVAILABLE, EpisodeStatus.UPCOMING), rows.map { it.status })
        assertEquals("/api/tv/item-image/x", rows[1].image) // E02 couvert par le fichier E01-E02
        assertEquals(0.3f, rows[0].progress, 0.001f)
        val season1 = series.seasons.first { it.seasonNumber == 1 }
        assertEquals(EpisodeStatus.MISSING, SeriesLogic.rows(season1, emptyList(), emptyMap()).last().status)
    }

    @Test
    fun `episode suivant pour l'enchainement`() {
        assertEquals(2 to 1, SeriesLogic.following(series, 1, 2)!!.let { it.seasonNumber to it.episodeNumber })
        assertNull(SeriesLogic.following(series, 2, 2))
    }

    @Test
    fun `saison ouverte d'office`() {
        val next = SeriesLogic.nextUp(series, states(state(1, 1, true), state(1, 2, true)))
        assertEquals(2, SeriesLogic.initialSeason(series, next))
        assertEquals(1, SeriesLogic.initialSeason(series, null))
    }

    @Test
    fun `date courte`() {
        assertEquals("03/11", shortDate("2026-11-03T01:00:00Z"))
        assertNull(shortDate(null))
    }
}
