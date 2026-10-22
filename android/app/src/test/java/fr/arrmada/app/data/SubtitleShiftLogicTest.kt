package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Menu pause › Sous-titres › −/+ 0,5 s. */
class SubtitleShiftLogicTest {

    private val fileFr = SideSubtitle("/api/tv/subtitle/x/5.srt", "Français · fichier", "fr", "application/x-subrip")
    private val inMkvFr = SideSubtitle("/api/tv/subtitle/x/3.ass", "Français", "fr", "text/x-ssa")
    private val inMkvForced = SideSubtitle("/api/tv/subtitle/x/4.ass", "Français (forcés)", "fr", "text/x-ssa")

    @Test
    fun `libelles et adresses`() {
        assertEquals("+1,5 s", SubtitleShiftLogic.format(1500))
        assertEquals("−0,5 s", SubtitleShiftLogic.format(-500))
        assertEquals("Français · fichier (décalé +1,0 s)", SubtitleShiftLogic.shiftedLabel("Français · fichier (décalé +0,5 s)", 1000))
        assertEquals("/a/5.srt?shift=-500", SubtitleShiftLogic.shiftedUrl("/a/5.srt?shift=1000", -500))
        assertEquals("/a/5.srt", SubtitleShiftLogic.shiftedUrl("/a/5.srt?shift=1000", 0))
        assertEquals("/a/5.srt?v=2&shift=500", SubtitleShiftLogic.shiftedUrl("/a/5.srt?v=2", 500))
    }

    @Test
    fun `piste a decaler`() {
        val side = listOf(fileFr)
        val embedded = listOf(inMkvFr, inMkvForced)
        // Sous-titre posé à côté : lui-même (même après un premier décalage)
        assertEquals(fileFr, SubtitleShiftLogic.source("Français · fichier (décalé +0,5 s)", "fr", false, side, embedded))
        // Piste du MKV : la piste intégrée de même langue, forcés si besoin
        assertEquals(inMkvFr, SubtitleShiftLogic.source("Français", "fre", false, side, embedded))
        assertEquals(inMkvForced, SubtitleShiftLogic.source("Français", "fr", true, side, embedded))
        // PGS anglais : rien d'extractible
        assertNull(SubtitleShiftLogic.source("Anglais", "en", false, side, embedded))
    }
}
