package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Décodage conseillé : son du film × enceintes de la pièce. */
class SoundAdvisorTest {
    private val salon = SoundAdvisor.layout("5.1")!!
    private val cinema = SoundAdvisor.layout("7.2.2")!!
    private val atmos = SoundAdvisor.sound("audio/true-hd", 8, null, "TrueHD Atmos")
    private val dd51 = SoundAdvisor.sound("audio/ac3", 6, null, null)
    private val ddp71 = SoundAdvisor.sound("audio/eac3", 8, null, null)
    private val stereo = SoundAdvisor.sound("audio/mp4a-latm", 2, null, null)

    @Test
    fun `dispositions`() {
        assertEquals(SoundAdvisor.Layout("7.2.2", 7, 2, 2), cinema)
        assertEquals(false, salon.hasHeights)
        assertNull(SoundAdvisor.layout(""))
        assertNull(SoundAdvisor.layout("salon"))
    }

    @Test
    fun `atmos selon la pièce`() {
        assertEquals("Dolby Atmos (TrueHD)", atmos.name)
        val c = SoundAdvisor.advise(cinema, atmos)
        assertEquals(SoundAdvisor.STRAIGHT, c.program)
        assertEquals("Dolby Atmos (TrueHD) natif sur 7.2.2", c.headline)
        assertEquals("Dolby Atmos (TrueHD) ramené au 5.1", SoundAdvisor.advise(salon, atmos).headline)
        assertEquals("Dolby TrueHD", SoundAdvisor.sound("audio/true-hd", 8, null, "TrueHD").name)
    }

    @Test
    fun `canaux fixes et stéréo`() {
        assertEquals(SoundAdvisor.STRAIGHT to "5.1 natif", SoundAdvisor.advise(salon, dd51).let { it.program to it.headline })
        assertEquals(SoundAdvisor.SURROUND_DECODER to "5.1 étendu au 7.2.2", SoundAdvisor.advise(cinema, dd51).let { it.program to it.headline })
        assertEquals("7.1 ramené au 5.1", SoundAdvisor.advise(salon, ddp71).headline)
        assertEquals(SoundAdvisor.SURROUND_DECODER, SoundAdvisor.advise(salon, stereo).program)
        assertEquals("Stéréo étendue au 7.2.2", SoundAdvisor.advise(cinema, stereo).headline)
    }

    @Test
    fun `sans ampli`() {
        val advice = SoundAdvisor.advise(null, atmos)
        assertNull(advice.program)
        assertEquals("Son de la TV · stéréo", advice.headline)
        assertEquals(true, "Dolby Digital 5.1" in advice.detail)
        assertNull(SoundAdvisor.advise(salon, null).program)
    }
}
