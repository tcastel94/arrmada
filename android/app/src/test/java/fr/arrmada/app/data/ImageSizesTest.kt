package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ImageSizesTest {
    private val poster = "https://image.tmdb.org/t/p/original/abc.jpg"

    @Test
    fun `affiche de grille en w342`() {
        assertEquals("https://image.tmdb.org/t/p/w342/abc.jpg", ImageSizes.tmdb(poster, 216))
    }

    @Test
    fun `fond plein écran plafonné à w1280`() {
        assertEquals("https://image.tmdb.org/t/p/w1280/abc.jpg", ImageSizes.tmdb(poster, 1920))
    }

    @Test
    fun `image déjà petite, autre source ou taille inconnue`() {
        assertNull(ImageSizes.tmdb("https://image.tmdb.org/t/p/w342/abc.jpg", 300))
        assertEquals("https://image.tmdb.org/t/p/w185/abc.jpg", ImageSizes.tmdb("https://image.tmdb.org/t/p/w500/abc.jpg", 120))
        assertNull(ImageSizes.tmdb("https://assets.fanart.tv/fanart/movies/1/x.jpg", 300))
        assertNull(ImageSizes.tmdb(poster, null))
    }
}
