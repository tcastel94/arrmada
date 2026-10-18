package fr.arrmada.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Tests de ServerUrl : lancés à chaque build par build-apk.sh (et donc en CI). */
class ServerUrlTest {

    @Test
    fun `ajoute http quand le protocole manque`() {
        assertEquals("http://192.168.1.10:3000", ServerUrl.normalize("192.168.1.10:3000"))
    }

    @Test
    fun `retire espaces, majuscules du nom et slash final`() {
        assertEquals("http://tower.local:3000", ServerUrl.normalize("  http://Tower.local:3000/ "))
        assertEquals("https://arrmada.example.org", ServerUrl.normalize("HTTPS://arrmada.example.org/"))
    }

    @Test
    fun `garde le chemin d'un reverse proxy, retire les parametres`() {
        assertEquals("http://h:3000/arrmada", ServerUrl.normalize("http://h:3000/arrmada/"))
        assertEquals("http://h:3000", ServerUrl.normalize("http://h:3000/?x=1#top"))
    }

    @Test
    fun `refuse les adresses inutilisables`() {
        assertNull(ServerUrl.normalize(""))
        assertNull(ServerUrl.normalize("   "))
        assertNull(ServerUrl.normalize("ftp://nas:21"))
        assertNull(ServerUrl.normalize("http://"))
        assertNull(ServerUrl.normalize("http://h:99999"))
        assertNull(ServerUrl.normalize("http://h:abc"))
        assertNull(ServerUrl.normalize("adresse avec espaces"))
    }

    @Test
    fun `origine pour l'injection de scripts`() {
        assertEquals("http://192.168.1.10:3000", ServerUrl.origin("http://192.168.1.10:3000/media"))
        assertEquals("https://h", ServerUrl.origin("https://h/arrmada"))
    }

    @Test
    fun `meme machine quel que soit le port`() {
        assertTrue(ServerUrl.sameHost("http://h:3000", "http://H:8420/api/health"))
        assertTrue(ServerUrl.sameHost("http://h:3000", "https://h/login"))
        assertFalse(ServerUrl.sameHost("http://h:3000", "https://www.themoviedb.org/movie/1"))
        assertFalse(ServerUrl.sameHost("http://h:3000", "mailto:moi@exemple.fr"))
        assertFalse(ServerUrl.sameHost("http://h:3000", "pas une url"))
    }
}
