package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalSeriesLogicTest {
    private fun ep(season: Int, number: Int, title: String) =
        LocalEpisode(seasonNumber = season, episodeNumber = number, title = title, token = "t$season-$number", watchId = "w$season-$number")

    private val naruto = LocalSeriesDetail(
        id = 3, title = "Naruto Kai", badge = "Kai", year = 2002, fanartUrl = "https://img/fond",
        seasons = listOf(
            LocalSeason(1, "Arc 01 - Pays des Vagues", listOf(ep(1, 1, "Uzumaki Naruto"), ep(1, 2, "Le ninja copieur"))),
            LocalSeason(2, "Arc 02 - Examen Chunin", listOf(ep(2, 15, "L'examen commence"), ep(2, 16, "Épisode 16"))),
        ),
    )

    private fun file(id: String, position: Int = 0, watched: Boolean = false, updated: String = "") =
        WatchState(mediaType = "file", idType = "sha1", id = id, position = position, total = 1400, watched = watched, updatedAt = updated)

    @Test
    fun `série maison vue comme une série Sonarr`() {
        val s = LocalSeriesLogic.toDetail(naruto)
        assertEquals("Kai", s.network)
        assertNull(s.tvdbId)
        assertEquals(listOf("Arc 01 - Pays des Vagues", "Arc 02 - Examen Chunin"), s.seasons.map { it.name })
        assertTrue(s.seasons.flatMap { it.episodes }.all { it.hasFile })
        assertEquals(listOf(15, 16), s.seasons[1].episodes.map { it.episodeNumber })
    }

    @Test
    fun `vu des fichiers rangé par saison et épisode, Lire la suite`() {
        val states = listOf(file("w1-1", watched = true, updated = "2026-10-20"), file("w1-2", watched = true, updated = "2026-10-21"), file("ailleurs", 30))
        val byEpisode = LocalSeriesLogic.states(naruto, states)
        assertEquals(setOf(1 to 1, 1 to 2), byEpisode.keys)
        assertEquals(1, byEpisode[1 to 2]?.season)
        // Arc 1 vu en entier : la suite est le premier épisode de l'arc 2
        val next = SeriesLogic.nextUp(LocalSeriesLogic.toDetail(naruto), byEpisode)
        assertEquals(2 to 15, next?.row?.season to next?.row?.episode)
    }

    @Test
    fun `épisode suivant, y compris d'un arc à l'autre`() {
        assertEquals("t1-2", LocalSeriesLogic.next(naruto, "t1-1")?.token)
        assertEquals("t2-15", LocalSeriesLogic.next(naruto, "t1-2")?.token)
        assertNull(LocalSeriesLogic.next(naruto, "t2-16"))
        assertNull(LocalSeriesLogic.next(naruto, "inconnu"))
    }

    @Test
    fun `grille et identifiants`() {
        val item = LocalSeriesLogic.libraryItem(LocalSeriesSummary(id = 3, title = "Naruto Kai", episodes = 4, posterUrl = "/api/videos/image/x"))
        assertEquals("local:3", item.externalId)
        assertEquals("series", item.type)
        assertTrue(item.hasFile)
        assertEquals(3, LocalSeriesLogic.idOf(item.externalId))
        assertNull(LocalSeriesLogic.idOf("42"))
        val empty = LocalSeriesLogic.libraryItem(LocalSeriesSummary(id = 4, episodes = 0))
        assertTrue(!empty.hasFile) // dossier vide : pas dans la grille
    }

    @Test
    fun `rangée Reprendre, un épisode par série, le plus récent`() {
        val index = naruto.seasons.flatMap { it.episodes }.map {
            LocalIndexItem(watchId = it.watchId, seriesId = 3, season = it.seasonNumber, episode = it.episodeNumber, title = it.title, token = it.token)
        }
        val states = listOf(
            file("w1-2", position = 300, updated = "2026-10-20T20:00:00"),
            file("w2-15", position = 600, updated = "2026-10-21T21:00:00"),
            file("w2-16", watched = true, updated = "2026-10-21T22:00:00"),
            file("hors-serie", position = 100, updated = "2026-10-22T08:00:00"),
        )
        val rows = LocalSeriesLogic.resume(states, index, listOf(LocalSeriesSummary(id = 3, title = "Naruto Kai", episodes = 4)))
        assertEquals(1, rows.size)
        val entry = rows.single()
        assertEquals("t2-15", entry.file)
        assertEquals(3, entry.localSeries)
        assertEquals("S02E15 · L'examen commence", entry.subtitle)
        assertEquals(600, entry.state.position)
    }
}
