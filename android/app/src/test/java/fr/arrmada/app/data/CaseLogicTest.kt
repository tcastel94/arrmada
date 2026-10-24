package fr.arrmada.app.data

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test

class CaseLogicTest {
    private fun file(height: Int? = null, quality: String? = null) =
        FileInfo(quality = quality, resolution = height?.let { JsonPrimitive(it) })

    @Test
    fun `boîtier selon le fichier`() {
        assertEquals(CaseLogic.Format.CLEAR, CaseLogic.format(false, file(2160)))
        assertEquals(CaseLogic.Format.UHD, CaseLogic.format(true, file(2160)))
        assertEquals(CaseLogic.Format.BLURAY, CaseLogic.format(true, file(1080)))
        assertEquals(CaseLogic.Format.BLURAY, CaseLogic.format(true, file(720)))
        assertEquals(CaseLogic.Format.DVD, CaseLogic.format(true, file(576)))
    }

    @Test
    fun `résolution inconnue, d'après la qualité`() {
        assertEquals(CaseLogic.Format.UHD, CaseLogic.format(true, file(quality = "Remux-2160p")))
        assertEquals(CaseLogic.Format.BLURAY, CaseLogic.format(true, file(quality = "WEBDL-1080p")))
        assertEquals(CaseLogic.Format.BLURAY, CaseLogic.format(true, null))
    }
}
