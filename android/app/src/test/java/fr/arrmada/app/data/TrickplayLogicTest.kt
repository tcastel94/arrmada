package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Aperçu en image : planche et position de la vignette, défilement borné. */
class TrickplayLogicTest {

    private val info = Trickplay(width = 320, height = 180, tileWidth = 10, tileHeight = 10, count = 250, interval = 10.0, url = "/api/tv/trickplay/x/320")

    @Test
    fun frameInTheRightTileAndCell() {
        assertEquals(TrickplayFrame(0, 0, 0), TrickplayLogic.frame(info, 0.0))
        assertEquals(TrickplayFrame(0, 3 * 320, 1 * 180), TrickplayLogic.frame(info, 135.0)) // vignette 13
        assertEquals(TrickplayFrame(1, 0, 0), TrickplayLogic.frame(info, 1000.0)) // vignette 100 : planche 2
        // Au-delà de la dernière vignette : la dernière (pas de planche inexistante)
        assertEquals(TrickplayFrame(2, 9 * 320, 4 * 180), TrickplayLogic.frame(info, 99_999.0))
        assertEquals("/api/tv/trickplay/x/320/2", TrickplayLogic.tileUrl(info, 2))
    }

    @Test
    fun noPreviewWithoutUsableInfo() {
        assertNull(TrickplayLogic.frame(null, 10.0))
        assertNull(TrickplayLogic.frame(info.copy(interval = 0.0), 10.0))
        assertNull(TrickplayLogic.frame(info.copy(tileWidth = 0), 10.0))
        assertNull(TrickplayLogic.frame(info.copy(url = ""), 10.0))
    }

    @Test
    fun scrubStaysInsideTheFilm() {
        assertEquals(0L, TrickplayLogic.scrub(5_000, -10_000, 60_000))
        assertEquals(59_000L, TrickplayLogic.scrub(50_000, 30_000, 60_000))
        assertEquals(40_000L, TrickplayLogic.scrub(10_000, 30_000, 0)) // durée encore inconnue
    }

    @Test
    fun holdingTheKeySpeedsUp() {
        assertEquals(30_000L, TrickplayLogic.step(true, 0))
        assertEquals(-10_000L, TrickplayLogic.step(false, 0))
        assertEquals(60_000L, TrickplayLogic.step(true, 5))
        assertEquals(-40_000L, TrickplayLogic.step(false, 20))
    }
}
