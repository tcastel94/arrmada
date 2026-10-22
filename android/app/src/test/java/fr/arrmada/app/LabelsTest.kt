package fr.arrmada.app

import fr.arrmada.app.data.FileInfo
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.detail.techBadges
import fr.arrmada.app.ui.player.channelsName
import fr.arrmada.app.ui.player.languageName
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Textes affichés : pistes, pastilles techniques, durées. */
class LabelsTest {

    @Test
    fun `langues en français`() {
        assertEquals("Français", languageName("fr"))
        assertEquals("Anglais", languageName("en"))
        assertNull(languageName("und"))
        assertNull(languageName(null))
    }

    @Test
    fun `canaux audio`() {
        assertEquals("Stéréo", channelsName(2))
        assertEquals("5.1", channelsName(6))
        assertEquals("7.1", channelsName(8))
        assertNull(channelsName(0))
    }

    @Test
    fun `pastilles 4K Dolby Vision Atmos`() {
        val file = FileInfo(resolution = JsonPrimitive(2160), dynamicRangeType = "DV HDR10", audioCodec = "TrueHD Atmos", audioChannels = 7.1)
        assertEquals(listOf("4K", "Dolby Vision", "Atmos", "7.1"), techBadges(file))
    }

    @Test
    fun `resolution absente lue dans la qualite`() {
        // Radarr renvoie "" quand il ne connaît pas la résolution
        val file = FileInfo(quality = "WEBDL-1080p", resolution = JsonPrimitive(""), audioCodec = "EAC3", audioChannels = 2.0)
        assertEquals(listOf("1080p"), techBadges(file))
    }

    @Test
    fun `horloge`() {
        assertEquals("42:10", formatClock(2530))
        assertEquals("1:02:05", formatClock(3725))
        assertEquals("0:00", formatClock(-5))
    }
}
