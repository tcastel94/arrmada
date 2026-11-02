package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Halo des cartes : la teinte vive de l'affiche, ou rien si elle n'en a pas. */
class PosterColorLogicTest {

    private fun argb(r: Int, g: Int, b: Int, a: Int = 0xFF) = (a shl 24) or (r shl 16) or (g shl 8) or b

    @Test
    fun vividColorWinsOverDarkBackground() {
        // Affiche surtout sombre avec un coucher de soleil orange : le halo est orange, éclairci
        val pixels = IntArray(40) { argb(20, 24, 40) } + IntArray(6) { argb(200, 100, 40) }
        assertEquals(argb(255, 127, 51), PosterColorLogic.accent(pixels))
    }

    @Test
    fun averagesTheMostVividPixels() {
        // Deux rouges proches : moyenne des deux, puis éclaircie
        val pixels = intArrayOf(argb(200, 20, 20), argb(180, 20, 20), argb(90, 90, 90))
        assertEquals(argb(255, 26, 26), PosterColorLogic.accent(pixels))
    }

    @Test
    fun greyBlackWhiteOrTransparentGiveNoColor() {
        assertNull(PosterColorLogic.accent(IntArray(30) { argb(128, 128, 128) })) // gris
        assertNull(PosterColorLogic.accent(IntArray(30) { argb(10, 5, 30) })) // presque noir
        assertNull(PosterColorLogic.accent(IntArray(30) { argb(250, 248, 245) })) // presque blanc
        assertNull(PosterColorLogic.accent(IntArray(30) { argb(255, 0, 0, a = 0) })) // transparent
        assertNull(PosterColorLogic.accent(IntArray(0)))
    }
}
