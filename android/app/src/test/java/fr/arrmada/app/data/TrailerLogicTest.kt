package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Bouton « Bande-annonce » : fichier du NAS, YouTube de TMDB, YouTube de Radarr. */
class TrailerLogicTest {

    @Test
    fun nasFileFirst() {
        val info = TrailerInfo(status = "ok", stream = "/api/tv/stream/abc", youtube = "fr_trailer1")
        assertEquals(TrailerSource.Local("/api/tv/stream/abc"), TrailerLogic.choose(info, "en_trailer1"))
    }

    @Test
    fun frenchTmdbTrailerBeforeRadarr() {
        val info = TrailerInfo(status = "none", youtube = "fr_trailer1")
        assertEquals(TrailerSource.YouTube("fr_trailer1"), TrailerLogic.choose(info, "en_trailer1"))
    }

    @Test
    fun radarrWhenServerHasNothingOrIsOld() {
        assertEquals(TrailerSource.YouTube("en_trailer1"), TrailerLogic.choose(TrailerInfo(), "en_trailer1"))
        // Réponse pas encore arrivée : l'identifiant de Radarr suffit pour montrer le bouton
        assertEquals(TrailerSource.YouTube("en_trailer1"), TrailerLogic.choose(null, " en_trailer1 "))
        assertTrue(TrailerLogic.available(null, "en_trailer1"))
    }

    @Test
    fun nothingUsable() {
        assertEquals(TrailerSource.None, TrailerLogic.choose(TrailerInfo(), null))
        assertEquals(TrailerSource.None, TrailerLogic.choose(TrailerInfo(), ""))
        // Adresse complète au lieu d'un identifiant, flux qui ne vient pas du serveur
        assertEquals(TrailerSource.None, TrailerLogic.choose(TrailerInfo(youtube = "https://youtu.be/x"), null))
        assertEquals(TrailerSource.None, TrailerLogic.choose(TrailerInfo(status = "ok", stream = "http://ailleurs/x.mp4"), null))
        assertFalse(TrailerLogic.available(null, null))
        assertNull(TrailerLogic.youtubeId(null, "", "abc"))
    }

    @Test
    fun youtubeTvAppFirstThenAnyApp() {
        val targets = TrailerLogic.youtubeTargets("fr_trailer1")
        assertEquals("com.google.android.youtube.tv" to "https://www.youtube.com/watch?v=fr_trailer1", targets.first())
        assertEquals(listOf(null, null), targets.drop(1).map { it.first })
        assertEquals("vnd.youtube:fr_trailer1", targets[1].second)
    }
}
