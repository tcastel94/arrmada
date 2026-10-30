package fr.arrmada.app.data

import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Carte technique de la fiche film : Vidéo, Audio, Sous-titres en clair. */
class TechSpecLogicTest {

    @Test
    fun uhdBluRay() {
        val file = FileInfo(
            quality = "Remux-2160p",
            resolution = JsonPrimitive(2160),
            videoCodec = "x265",
            dynamicRangeType = "DV HDR10",
            audioCodec = "TrueHD Atmos",
            audioChannels = 7.1,
            audioLanguages = "French / English",
            subtitleLanguages = "French/English/French",
        )
        assertEquals(
            listOf(
                TechSpecLogic.Line("Vidéo", "2160p · Dolby Vision · HEVC"),
                TechSpecLogic.Line("Audio", "TrueHD Atmos · 7.1 · Français, Anglais"),
                TechSpecLogic.Line("Sous-titres", "Français, Anglais"),
            ),
            TechSpecLogic.lines(file),
        )
    }

    @Test
    fun webDlStereoWithoutSubtitles() {
        val file = FileInfo(quality = "WEBDL-1080p", videoCodec = "h264", audioCodec = "EAC3", audioChannels = 2.0, audioLanguages = "eng")
        assertEquals(
            listOf(
                TechSpecLogic.Line("Vidéo", "1080p · H.264"),
                TechSpecLogic.Line("Audio", "Dolby Digital Plus · Stéréo · Anglais"),
            ),
            TechSpecLogic.lines(file),
        )
    }

    @Test
    fun emptyFile() {
        assertEquals(emptyList<TechSpecLogic.Line>(), TechSpecLogic.lines(null))
        assertEquals(emptyList<TechSpecLogic.Line>(), TechSpecLogic.lines(FileInfo()))
    }

    @Test
    fun unknownLanguageKept() {
        assertEquals("Français, Tagalog", TechSpecLogic.languages("fre/tagalog"))
        assertNull(TechSpecLogic.languages(" "))
    }
}
