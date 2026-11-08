package fr.arrmada.app.data

import fr.arrmada.app.data.HlsAudioLogic.Heard
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Flux converti (1080p, remux, SDR) : Jellyfin n'y met qu'une piste audio, on lui demande celle qu'on entend. */
class HlsAudioLogicTest {

    // Fichier MULTi : VO TrueHD 7.1 par défaut, VF Dolby Digital Plus 5.1, audiodescription française stéréo
    private val multi = listOf(
        AudioTrack(index = 1, language = "eng", codec = "truehd", channels = 8, isDefault = true),
        AudioTrack(index = 2, language = "fre", codec = "eac3", channels = 6),
        AudioTrack(index = 3, language = "fre", codec = "ac3", channels = 2, title = "Audiodescription"),
    )

    @Test
    fun `la VF entendue en direct est demandee a Jellyfin`() {
        val heard = Heard(position = 1, language = "fr", mimeType = "audio/eac3", channels = 6)
        assertEquals(2, HlsAudioLogic.jellyfinIndex(heard, multi))
        // La VO : la piste par défaut, que Jellyfin aurait prise de lui-même
        assertEquals(1, HlsAudioLogic.jellyfinIndex(Heard(0, "en", "audio/true-hd", 8), multi))
    }

    @Test
    fun `deux pistes de la meme langue, le format et les canaux departagent`() {
        assertEquals(3, HlsAudioLogic.jellyfinIndex(Heard(2, "fr", "audio/ac3", 2), multi))
        // Rang perdu (le lecteur ne numérote pas comme le fichier) : le format et les canaux suffisent
        assertEquals(3, HlsAudioLogic.jellyfinIndex(Heard(0, "fr", "audio/ac3", 2), multi))
        // Même format partout : le rang décide
        assertEquals(2, HlsAudioLogic.jellyfinIndex(Heard(1, "fr", "audio/eac3", 0), multi))
    }

    @Test
    fun `langue inconnue, le rang dans le fichier decide`() {
        assertEquals(1, HlsAudioLogic.jellyfinIndex(Heard(0, null, "audio/true-hd", 8), multi))
        assertEquals(2, HlsAudioLogic.jellyfinIndex(Heard(1, "und", null, 0), multi))
        // Piste du fichier sans langue connue : prise si rien ne la contredit
        val unnamed = listOf(AudioTrack(index = 1, language = "", codec = "eac3", channels = 6))
        assertEquals(1, HlsAudioLogic.jellyfinIndex(Heard(0, "fr", "audio/eac3", 6), unnamed))
    }

    @Test
    fun `langue entendue absente du fichier, rien de demande`() {
        // Jellyfin prend alors sa première piste : pas pire qu'avant
        assertNull(HlsAudioLogic.jellyfinIndex(Heard(0, "ja", "audio/eac3", 6), multi))
    }

    @Test
    fun `rien d'entendu ou pas de liste, Jellyfin choisit`() {
        assertNull(HlsAudioLogic.jellyfinIndex(null, multi))
        assertNull(HlsAudioLogic.jellyfinIndex(Heard(0, "fr", "audio/eac3", 6), emptyList()))
    }

    @Test
    fun `deja sur un flux converti, la piste demandee reste`() {
        val heard = Heard(0, "en", "audio/true-hd", 8)
        // Le lecteur ne voit qu'une piste dans le HLS : on garde ce qu'on avait demandé
        assertEquals(2, HlsAudioLogic.indexForSwitch(currentIsHls = true, currentIndex = 2, heard = heard, tracks = multi))
        assertNull(HlsAudioLogic.indexForSwitch(currentIsHls = true, currentIndex = null, heard = heard, tracks = multi))
        // Depuis le direct : la piste entendue
        assertEquals(1, HlsAudioLogic.indexForSwitch(currentIsHls = false, currentIndex = 2, heard = heard, tracks = multi))
    }

    @Test
    fun `adresse du flux avec la piste`() {
        assertEquals("/api/tv/hls/x/sdr.m3u8?audio=2", HlsAudioLogic.withAudio("/api/tv/hls/x/sdr.m3u8", 2))
        assertEquals("/api/tv/hls/x/sdr.m3u8", HlsAudioLogic.withAudio("/api/tv/hls/x/sdr.m3u8", null))
        assertEquals("/a?v=1&audio=3", HlsAudioLogic.withAudio("/a?v=1", 3))
        assertEquals("", HlsAudioLogic.withAudio("", 3))
    }

    @Test
    fun `familles de codecs, cote lecteur et cote Jellyfin`() {
        assertEquals(HlsAudioLogic.codecFamily("eac3"), HlsAudioLogic.codecFamily("audio/eac3-joc"))
        assertEquals(HlsAudioLogic.codecFamily("dts"), HlsAudioLogic.codecFamily("audio/vnd.dts.hd"))
        assertEquals(HlsAudioLogic.codecFamily("truehd"), HlsAudioLogic.codecFamily("audio/true-hd"))
        assertEquals(HlsAudioLogic.codecFamily("aac"), HlsAudioLogic.codecFamily("audio/mp4a-latm"))
        assertEquals(HlsAudioLogic.codecFamily("pcm_s24le"), HlsAudioLogic.codecFamily("audio/raw"))
        assertEquals(HlsAudioLogic.codecFamily("mp2"), HlsAudioLogic.codecFamily("audio/mpeg-L2"))
        assertEquals("alac", HlsAudioLogic.codecFamily("audio/alac"))
        assertNull(HlsAudioLogic.codecFamily(null))
        assertNull(HlsAudioLogic.codecFamily("  "))
    }
}
