package fr.arrmada.app.data

import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Page acteur : textes, ouverture d'une affiche, lecture de la réponse du serveur. */
class PersonLogicTest {

    @Test
    fun metaInFrench() {
        val keanu = PersonInfo(name = "Keanu Reeves", knownFor = "Acting", birthday = "1964-09-02", placeOfBirth = "Beyrouth, Liban")
        assertEquals("Acteur, actrice  ·  né(e) le 2 septembre 1964  ·  Beyrouth, Liban", PersonLogic.meta(keanu))
        assertEquals("Réalisation", PersonLogic.meta(PersonInfo(knownFor = "Directing")))
        assertEquals("", PersonLogic.meta(PersonInfo()))
    }

    @Test
    fun unreadableBirthdayIsSkipped() {
        assertNull(PersonLogic.birth("vers 1900"))
        assertNull(PersonLogic.birth(""))
        assertEquals("1 janvier 2000", PersonLogic.birth("2000-01-01T00:00:00"))
    }

    @Test
    fun subtitleTellsWhereTheMovieIs() {
        assertEquals("1999  ·  Neo  ·  Sur le NAS", PersonLogic.subtitle(FilmCredit(year = 1999, character = "Neo", radarrId = 4, hasFile = true)))
        assertEquals("2026  ·  Demandé, pas encore téléchargé", PersonLogic.subtitle(FilmCredit(year = 2026, radarrId = 9)))
        assertEquals("Pas encore dans ta médiathèque", PersonLogic.subtitle(FilmCredit()))
    }

    @Test
    fun ownedMovieOpensItsSheetOtherwiseDownload() {
        assertEquals(CreditOpen.Movie("4", 603), PersonLogic.open(FilmCredit(tmdbId = 603, title = "Matrix", radarrId = 4)))
        val other = PersonLogic.open(FilmCredit(tmdbId = 245891, title = "John Wick", year = 2014, poster = "https://img/jw.jpg"))
        other as CreditOpen.Download
        assertEquals(DownloadTarget(kind = "movie", title = "John Wick", year = 2014, tmdbId = 245891, poster = "https://img/jw.jpg"), other.target)
    }

    @Test
    fun readsTheServerAnswer() {
        // Mêmes réglages que le client de l'appli (Api.json)
        val json = Json { ignoreUnknownKeys = true; coerceInputValues = true; explicitNulls = false }
        val text = """{"person":{"tmdb_id":6384,"name":"Keanu Reeves","photo":null,"biography":"Acteur canadien.","known_for":"Acting","birthday":"1964-09-02","place_of_birth":null},
            "in_library":[{"tmdb_id":603,"title":"Matrix","year":1999,"character":"Neo","poster":"https://img/m.jpg","vote_average":8.2,"popularity":80,"radarr_id":4,"has_file":true}],
            "discover":[{"tmdb_id":245891,"title":"John Wick","year":2014,"character":"John Wick","poster":null,"vote_average":7.4,"popularity":60}],
            "counts":{"in_library":1,"discover":1}}"""
        val data = json.decodeFromString(Filmography.serializer(), text)
        assertEquals("Keanu Reeves", data.person?.name)
        assertEquals(4, data.inLibrary.single().radarrId)
        assertNull(data.discover.single().radarrId)
        // Erreur du serveur (TMDB absent) : pas d'acteur, un message
        val error = json.decodeFromString(Filmography.serializer(), """{"error":"TMDB non configuré","person":null,"in_library":[],"discover":[]}""")
        assertNull(error.person)
        assertEquals("TMDB non configuré", error.error)
    }
}
