package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Dolby Vision profil 5 : conversion SDR quand l'écran ne gère pas le Dolby Vision. */
class DolbyVisionLogicTest {

    @Test
    fun `profil lu dans la chaine codecs`() {
        assertEquals(5, DolbyVisionLogic.profile("dvhe.05.06"))
        assertEquals(8, DolbyVisionLogic.profile("dvh1.08.06"))
        assertEquals(5, DolbyVisionLogic.profile("DVHE.05.09"))
        assertNull(DolbyVisionLogic.profile("hvc1.2.4.L153.B0"))
        assertNull(DolbyVisionLogic.profile(null))
        assertNull(DolbyVisionLogic.profile("dvhe"))
    }

    @Test
    fun `seul le profil 5 n'a pas d'image de secours`() {
        assertTrue(DolbyVisionLogic.withoutFallback("video/dolby-vision", "dvhe.05.06"))
        assertFalse(DolbyVisionLogic.withoutFallback("video/dolby-vision", "dvhe.08.06"))
        assertFalse(DolbyVisionLogic.withoutFallback("video/hevc", "dvhe.05.06"))
    }

    @Test
    fun `conversion SDR seulement sans ecran Dolby Vision`() {
        val tulsa = PlayInfo(doviOnly = true, sdrStream = "/api/tv/hls/x/sdr.m3u8")
        assertTrue(DolbyVisionLogic.startWithSdr(tulsa, screenHasDolbyVision = false))
        assertFalse(DolbyVisionLogic.startWithSdr(tulsa, screenHasDolbyVision = true))
        // Fichier de l'écran Vidéos : Jellyfin ne peut pas le convertir
        assertFalse(DolbyVisionLogic.startWithSdr(tulsa.copy(sdrStream = ""), screenHasDolbyVision = false))
        assertFalse(DolbyVisionLogic.startWithSdr(PlayInfo(), screenHasDolbyVision = false))
    }

    @Test
    fun `libelle des reglages`() {
        assertEquals("SDR (pas de HDR annoncé)", DolbyVisionLogic.screenLabel(emptyList(), dolbyVisionDecoder = true))
        assertEquals("HDR10 · HLG", DolbyVisionLogic.screenLabel(listOf("HDR10", "HLG"), dolbyVisionDecoder = false))
        assertEquals(
            "HDR10 · Dolby Vision (pas de décodeur Dolby Vision)",
            DolbyVisionLogic.screenLabel(listOf("HDR10", "Dolby Vision"), dolbyVisionDecoder = false),
        )
    }
}
