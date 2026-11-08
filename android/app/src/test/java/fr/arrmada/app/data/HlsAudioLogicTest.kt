package fr.arrmada.app.data

import fr.arrmada.app.data.HlsAudioLogic.Heard
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
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

    // Noms de langues du lecteur (Tracks.kt, qui dépend de Media3) : remplacés ici
    private val names: (String?) -> String? = { code ->
        when (code) { "eng" -> "Anglais"; "fre" -> "Français"; "jpn" -> "Japonais"; else -> null }
    }

    @Test
    fun `panneau Audio d'un flux converti, les pistes du serveur avec la piste lue marquee`() {
        // Lecture convertie dès le départ (réglage « 1080p ») : rien de demandé, Jellyfin a pris la piste par défaut
        val choices = HlsAudioLogic.choices(multi, requested = null, languageName = names)
        assertEquals(listOf(1, 2, 3), choices.map { it.index })
        assertEquals(listOf("Anglais", "Français", "Français"), choices.map { it.label })
        assertEquals(listOf("Dolby TrueHD · 7.1", "Dolby Digital Plus · 5.1", "Audiodescription · Dolby Digital · Stéréo"), choices.map { it.detail })
        assertEquals(listOf(true, false, false), choices.map { it.selected })
        // VF demandée (« ?audio=2 ») : c'est elle qui est cochée
        assertEquals(listOf(false, true, false), HlsAudioLogic.choices(multi, 2, names).map { it.selected })
        // Index demandé inconnu du fichier : Jellyfin l'a ignoré, la piste par défaut est cochée
        assertEquals(listOf(true, false, false), HlsAudioLogic.choices(multi, 9, names).map { it.selected })
    }

    @Test
    fun `piste lue par Jellyfin sans demande, la piste par defaut sinon la premiere`() {
        assertEquals(1, HlsAudioLogic.playedIndex(multi, null))
        val noDefault = multi.map { it.copy(isDefault = false) }
        assertEquals(1, HlsAudioLogic.playedIndex(noDefault, null))
        val defaultLast = listOf(multi[1], multi[2], multi[0]) // VO par défaut en 3e position
        assertEquals(1, HlsAudioLogic.playedIndex(defaultLast, null))
        assertEquals(3, HlsAudioLogic.playedIndex(multi, 3))
        assertNull(HlsAudioLogic.playedIndex(emptyList(), 2))
    }

    @Test
    fun `piste sans langue connue, son titre puis un numero`() {
        val tracks = listOf(
            AudioTrack(index = 1, language = "", codec = "aac", channels = 2, title = "Commentaire du réalisateur"),
            AudioTrack(index = 2, language = "und", codec = "opus", channels = 0),
            AudioTrack(index = 3, language = "jpn", codec = "pcm_s16le", channels = 2, title = ""),
        )
        val choices = HlsAudioLogic.choices(tracks, null, names)
        assertEquals(listOf("Commentaire du réalisateur", "Piste 2", "Japonais"), choices.map { it.label })
        assertEquals(listOf("AAC · Stéréo", "Opus", "PCM · Stéréo"), choices.map { it.detail })
        assertTrue(HlsAudioLogic.choices(emptyList(), null, names).isEmpty())
    }

    @Test
    fun `changer de piste recharge le flux, sauf pour la piste deja lue ou une piste inconnue`() {
        // Lecture convertie dès le départ, VO par défaut : passer en VF recharge
        assertTrue(HlsAudioLogic.switchNeeded(multi, requested = null, chosen = 2))
        // Reprendre la piste lue : rien à faire
        assertFalse(HlsAudioLogic.switchNeeded(multi, requested = null, chosen = 1))
        assertFalse(HlsAudioLogic.switchNeeded(multi, requested = 2, chosen = 2))
        // Déjà en VF, retour à la VO
        assertTrue(HlsAudioLogic.switchNeeded(multi, requested = 2, chosen = 1))
        // Index inconnu du fichier, ou pas de liste : rien à demander
        assertFalse(HlsAudioLogic.switchNeeded(multi, requested = null, chosen = 7))
        assertFalse(HlsAudioLogic.switchNeeded(emptyList(), requested = null, chosen = 1))
    }

    @Test
    fun `noms des formats de Jellyfin, comme ceux du lecteur`() {
        assertEquals("Dolby TrueHD", HlsAudioLogic.codecName("truehd"))
        assertEquals("Dolby Digital Plus", HlsAudioLogic.codecName("eac3"))
        assertEquals("Dolby Digital", HlsAudioLogic.codecName("ac3"))
        assertEquals("DTS", HlsAudioLogic.codecName("dts"))
        assertEquals("AAC", HlsAudioLogic.codecName("aac"))
        assertEquals("MP3", HlsAudioLogic.codecName("mp2"))
        assertEquals("PCM", HlsAudioLogic.codecName("pcm_s24le"))
        assertEquals("ALAC", HlsAudioLogic.codecName("alac"))
        assertNull(HlsAudioLogic.codecName(""))
        assertNull(HlsAudioLogic.codecName(null))
        assertEquals("5.1", HlsAudioLogic.channelsName(6))
        assertEquals("Mono", HlsAudioLogic.channelsName(1))
        assertEquals("4 canaux", HlsAudioLogic.channelsName(4))
        assertNull(HlsAudioLogic.channelsName(0))
    }
}
