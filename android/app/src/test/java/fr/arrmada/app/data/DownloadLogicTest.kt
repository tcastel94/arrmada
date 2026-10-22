package fr.arrmada.app.data

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Feuille « Télécharger » : libellés, sélection complète, corps envoyé. */
class DownloadLogicTest {

    private val movie = DownloadTarget(kind = "movie", title = "Dune : Deuxième partie", tmdbId = 693134)
    private val series = DownloadTarget(kind = "series", title = "Severance", tvdbId = 371980, arrId = 23)

    @Test
    fun `libelles du bouton`() {
        assertEquals("Télécharger le film", DownloadLogic.buttonLabel(movie, Scope.SEASON, null, emptyList()))
        assertEquals("Télécharger toute la série", DownloadLogic.buttonLabel(series, Scope.SERIES, null, emptyList()))
        assertEquals("Choisis une saison", DownloadLogic.buttonLabel(series, Scope.SEASON, null, emptyList()))
        assertEquals("Télécharger la saison 2", DownloadLogic.buttonLabel(series, Scope.SEASON, 2, emptyList()))
        assertEquals("Coche un épisode", DownloadLogic.buttonLabel(series, Scope.EPISODE, 2, emptyList()))
        assertEquals("Télécharger S02E05", DownloadLogic.buttonLabel(series, Scope.EPISODE, 2, listOf(5)))
        assertEquals("Télécharger 3 épisodes", DownloadLogic.buttonLabel(series, Scope.EPISODE, 2, listOf(5, 6, 7)))
    }

    @Test
    fun `selection complete`() {
        assertTrue(DownloadLogic.ready(movie, Scope.SEASON, null, emptyList()))
        assertFalse(DownloadLogic.ready(series, Scope.SEASON, null, emptyList()))
        assertFalse(DownloadLogic.ready(series, Scope.EPISODE, 2, emptyList()))
        assertTrue(DownloadLogic.ready(series, Scope.EPISODE, 2, listOf(1)))
    }

    private val json = Json { explicitNulls = false; encodeDefaults = true }

    @Test
    fun `corps envoye au serveur, sans champs vides`() {
        val film = json.encodeToString(DownloadRequest.serializer(), DownloadLogic.request(movie, Scope.SEASON, null, emptyList(), true))
        assertEquals("""{"type":"movie","title":"Dune : Deuxième partie","priority":true,"tmdb_id":693134}""", film)
        val episodes = json.encodeToString(DownloadRequest.serializer(), DownloadLogic.request(series, Scope.EPISODE, 2, listOf(7, 5), false))
        assertEquals(
            """{"type":"series","title":"Severance","priority":false,"tvdb_id":371980,"arr_id":23,"scope":"episode","season":2,"episodes":[5,7]}""",
            episodes,
        )
        val whole = json.encodeToString(DownloadRequest.serializer(), DownloadLogic.request(series, Scope.SERIES, 2, listOf(1), true))
        assertEquals("""{"type":"series","title":"Severance","priority":true,"tvdb_id":371980,"arr_id":23,"scope":"series"}""", whole)
    }

    @Test
    fun `saisons et episodes`() {
        assertEquals("complète", DownloadLogic.seasonSubtitle(SeasonCount(1, 9, 9, 9)))
        assertEquals("4/10 sur le NAS", DownloadLogic.seasonSubtitle(SeasonCount(2, 10, 10, 4)))
        assertEquals("8 épisodes", DownloadLogic.seasonSubtitle(SeasonCount(3, 8, 8, 0)))
        assertEquals("Déjà sur le NAS", DownloadLogic.episodeState(SeasonEpisode(hasFile = true)))
        assertEquals("Sortie le 03/11", DownloadLogic.episodeState(SeasonEpisode(aired = false, airDate = "2026-11-03")))
        assertEquals("52 min", DownloadLogic.episodeState(SeasonEpisode(runtime = 52)))
    }
}
