package fr.arrmada.app.data

import fr.arrmada.app.ui.music.MusicRules
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Libellés de l'écran Musique de la TV (cartes d'artistes, d'albums, résultats). */
class MusicRulesTest {

    @Test
    fun artistLine() {
        assertEquals("3 albums · 20/30 pistes", MusicRules.artistLine(MusicArtist(albums = 3, tracksHave = 20, tracksTotal = 30)))
        assertEquals("1 album", MusicRules.artistLine(MusicArtist(albums = 1)))
    }

    @Test
    fun albumTag() {
        assertNull(MusicRules.albumTag(MusicAlbum(status = "complete", tracksHave = 10, tracksTotal = 10)))
        assertEquals("10/12", MusicRules.albumTag(MusicAlbum(status = "partial", tracksHave = 10, tracksTotal = 12)))
        assertEquals("Absent", MusicRules.albumTag(MusicAlbum(status = "missing", tracksTotal = 8)))
    }

    @Test
    fun hitLine() {
        assertEquals("Groupe · Electronic", MusicRules.hitLine(MusicArtistHit(type = "Group", genres = listOf("Electronic"))))
        assertEquals("Artiste", MusicRules.hitLine(MusicArtistHit(type = "Person")))
        assertEquals("MusicBrainz", MusicRules.hitLine(MusicArtistHit()))
    }

    @Test
    fun listenableAlbum() {
        assertEquals(true, MusicAlbum(tracksHave = 1).listenable)
        assertEquals(false, MusicAlbum(tracksHave = 0).listenable)
    }

    @Test
    fun albumMenu() {
        val partial = MusicAlbum(status = "partial", tracksHave = 10, tracksTotal = 12, monitored = true)
        assertEquals("10 pistes sur 12 sur le NAS", MusicRules.albumState(partial))
        assertEquals("Récupérer les pistes manquantes", MusicRules.searchLabel(partial))
        assertEquals("Récupérer cet album", MusicRules.searchLabel(MusicAlbum(status = "missing")))
        assertEquals("Pas sur le NAS (non suivi)", MusicRules.albumState(MusicAlbum(status = "missing")))
        assertEquals("Chercher une meilleure version", MusicRules.searchLabel(MusicAlbum(status = "complete")))
    }

    @Test
    fun downloadTitle() {
        assertEquals("Radiohead – Kid A", MusicRules.downloadTitle(MusicDownloadAlbum(name = "dossier", artist = "Radiohead", album = "Kid A")))
        assertEquals("dossier", MusicRules.downloadTitle(MusicDownloadAlbum(name = "dossier")))
    }
}
