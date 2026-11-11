package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Écran noir avec le son (image que l'appareil ne décode pas) : bascule vers une conversion Jellyfin. */
class VideoRescueLogicTest {

    private val film = PlayInfo(
        status = "ok",
        mode = "direct",
        stream = "/api/tv/stream/x",
        sdrStream = "/api/tv/hls/x/sdr.m3u8",
        liteStream = "/api/tv/hls/x/lite.m3u8",
        videoRange = "HDR10",
    )

    @Test
    fun `piste video ecartee par le lecteur, pas d'image`() {
        assertTrue(VideoRescueLogic.noPicture(videoTracks = 1, anySelected = false))
        assertFalse(VideoRescueLogic.noPicture(videoTracks = 1, anySelected = true))
        // Musique, ou pistes pas encore connues : rien à sauver
        assertFalse(VideoRescueLogic.noPicture(videoTracks = 0, anySelected = false))
    }

    @Test
    fun `AV1 sur un ecran HDR, 1080p HDR d'abord puis le H264`() {
        val reduced = QualityLogic.reduced(film, screenHdr10 = true)
        assertEquals(Quality.HD_HDR, VideoRescueLogic.next(Quality.ORIGINAL, reduced, film))
        assertEquals(Quality.HD_SDR, VideoRescueLogic.next(Quality.HD_HDR, reduced, film))
        assertNull(VideoRescueLogic.next(Quality.HD_SDR, reduced, film))
    }

    @Test
    fun `ecran SDR ou film SDR, directement le H264`() {
        assertEquals(Quality.HD_SDR, VideoRescueLogic.next(Quality.ORIGINAL, QualityLogic.reduced(film, screenHdr10 = false), film))
        val sdr = film.copy(videoRange = "SDR")
        assertEquals(Quality.HD_SDR, VideoRescueLogic.next(Quality.ORIGINAL, QualityLogic.reduced(sdr, screenHdr10 = true), sdr))
    }

    @Test
    fun `video hors mediatheque, rien a tenter`() {
        val file = PlayInfo(status = "ok", mode = "direct", stream = "/api/tv/file/x")
        assertNull(VideoRescueLogic.next(Quality.ORIGINAL, QualityLogic.reduced(file, screenHdr10 = true), file))
        assertNull(VideoRescueLogic.next(Quality.HD_HDR, null, file))
    }

    @Test
    fun `nom du format dans le message`() {
        assertEquals("AV1", VideoRescueLogic.codecName("video/av01"))
        assertEquals("HEVC", VideoRescueLogic.codecName("video/hevc"))
        assertEquals("VC-1", VideoRescueLogic.codecName("video/wvc1"))
        assertEquals("THEORA", VideoRescueLogic.codecName("video/theora"))
        assertEquals("vidéo", VideoRescueLogic.codecName(null))
        assertEquals(
            "Image AV1 non décodée par cet appareil : convertie par Jellyfin (1080p)",
            VideoRescueLogic.rescueMessage("video/av01"),
        )
    }
}
