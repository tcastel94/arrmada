package fr.arrmada.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Qualité de lecture : Original, 1080p HDR / SDR, proposition après des coupures (ADR-012). */
class QualityLogicTest {

    private val upgrade = PlayInfo(
        status = "ok",
        mode = "direct",
        stream = "/api/tv/stream/x",
        sdrStream = "/api/tv/hls/x/sdr.m3u8",
        videoRange = "DOVIWithHDR10",
        bitrate = 89_700_000,
    )
    private val withLite = upgrade.copy(liteStream = "/api/tv/hls/x/lite.m3u8")

    @Test
    fun `debit arrondi et detail de l'original`() {
        assertEquals(90, QualityLogic.mbps(89_700_000))
        assertEquals(20, QualityLogic.mbps(20_000_000))
        assertNull(QualityLogic.mbps(null))
        assertNull(QualityLogic.mbps(0))
        assertEquals("4K · Dolby Vision · 90 Mb/s", QualityLogic.originalDetail("4K · Dolby Vision", 89_700_000))
        assertEquals("4K · HDR10", QualityLogic.originalDetail("4K · HDR10", null))
        assertEquals("90 Mb/s", QualityLogic.originalDetail("", 89_700_000))
        assertEquals("Fichier d’origine", QualityLogic.originalDetail("", null))
    }

    @Test
    fun `serveur sans lite_stream, Original et 1080p SDR seulement`() {
        val options = QualityLogic.options(upgrade, screenHdr10 = true, originalFormat = "4K · Dolby Vision", doviForcedSdr = false)
        assertEquals(listOf(Quality.ORIGINAL, Quality.HD_SDR), options.map { it.quality })
        assertEquals("Original", options[0].title)
        assertEquals("4K · Dolby Vision · 90 Mb/s", options[0].detail)
        assertEquals("1080p SDR · 20 Mb/s", options[1].title)
        assertTrue(options.all { it.available })
    }

    @Test
    fun `1080p HDR seulement avec un ecran HDR10 et une image HDR`() {
        val hdr = QualityLogic.options(withLite, screenHdr10 = true, originalFormat = "4K", doviForcedSdr = false)
        assertEquals(listOf(Quality.ORIGINAL, Quality.HD_HDR, Quality.HD_SDR), hdr.map { it.quality })
        assertEquals("1080p HDR · 20 Mb/s", hdr[1].title)
        // Écran sans HDR : le SDR suffit
        val sdrScreen = QualityLogic.options(withLite, screenHdr10 = false, originalFormat = "4K", doviForcedSdr = false)
        assertEquals(listOf(Quality.ORIGINAL, Quality.HD_SDR), sdrScreen.map { it.quality })
        // Film SDR : pas de « 1080p HDR »
        val sdrFilm = QualityLogic.options(withLite.copy(videoRange = "SDR"), screenHdr10 = true, originalFormat = "1080p", doviForcedSdr = false)
        assertEquals(listOf(Quality.ORIGINAL, Quality.HD_SDR), sdrFilm.map { it.quality })
    }

    @Test
    fun `Dolby Vision profil 5 deja en SDR, original indisponible`() {
        val tulsa = withLite.copy(doviOnly = true, videoRange = "DOVI")
        val options = QualityLogic.options(tulsa, screenHdr10 = true, originalFormat = "4K · Dolby Vision", doviForcedSdr = true)
        assertEquals(listOf(Quality.ORIGINAL, Quality.HD_SDR), options.map { it.quality })
        assertFalse(options[0].available)
        assertEquals("Dolby Vision : couleurs fausses sur cet écran", options[0].detail)
    }

    @Test
    fun `video hors Jellyfin, l original seul`() {
        val file = PlayInfo(status = "ok", stream = "/api/tv/files/stream/t")
        assertEquals(listOf(Quality.ORIGINAL), QualityLogic.options(file, true, "", false).map { it.quality })
        assertNull(QualityLogic.reduced(file, screenHdr10 = true))
    }

    @Test
    fun `adresse de chaque qualite`() {
        assertEquals("/api/tv/stream/x" to false, QualityLogic.source(withLite, Quality.ORIGINAL))
        assertEquals("/api/tv/hls/x/lite.m3u8" to true, QualityLogic.source(withLite, Quality.HD_HDR))
        assertEquals("/api/tv/hls/x/sdr.m3u8" to true, QualityLogic.source(withLite, Quality.HD_SDR))
        // Remux (.m2ts) : l'original est lui aussi une liste HLS
        val m2ts = withLite.copy(mode = "remux", stream = "/api/tv/hls/x/master.m3u8")
        assertEquals("/api/tv/hls/x/master.m3u8" to true, QualityLogic.source(m2ts, Quality.ORIGINAL))
    }

    @Test
    fun `qualite de depart`() {
        assertEquals(Quality.ORIGINAL, QualityLogic.initial(upgrade, true, false, DefaultQuality.ORIGINAL))
        assertEquals(Quality.HD_SDR, QualityLogic.initial(upgrade, true, false, DefaultQuality.HD_1080))
        assertEquals(Quality.HD_HDR, QualityLogic.initial(withLite, true, false, DefaultQuality.HD_1080))
        assertEquals(Quality.HD_SDR, QualityLogic.initial(withLite, false, false, DefaultQuality.HD_1080))
        // Pas de conversion possible (écran Vidéos) : l'original malgré le réglage
        assertEquals(Quality.ORIGINAL, QualityLogic.initial(PlayInfo(stream = "/f"), true, false, DefaultQuality.HD_1080))
    }

    @Test
    fun `Dolby Vision profil 5 prioritaire sur le reglage`() {
        val tulsa = withLite.copy(doviOnly = true, videoRange = "DOVI")
        // Même réglé sur « Original », et même avec un écran HDR10 : SDR (sinon image violette)
        assertEquals(Quality.HD_SDR, QualityLogic.initial(tulsa, true, screenDolbyVision = false, default = DefaultQuality.ORIGINAL))
        assertEquals(Quality.HD_SDR, QualityLogic.initial(tulsa, true, screenDolbyVision = false, default = DefaultQuality.HD_1080))
        // Écran Dolby Vision : le réglage s'applique normalement
        assertEquals(Quality.ORIGINAL, QualityLogic.initial(tulsa, true, screenDolbyVision = true, default = DefaultQuality.ORIGINAL))
    }

    @Test
    fun `messages`() {
        assertEquals("Qualité réduite : 1080p · 20 Mb/s", QualityLogic.switchMessage(Quality.HD_SDR))
        assertEquals("Qualité d’origine", QualityLogic.switchMessage(Quality.ORIGINAL))
        assertEquals("Le réseau ne suit pas ce fichier (90 Mb/s). Passer en 1080p ?", QualityLogic.suggestMessage(89_700_000))
        assertEquals("Le réseau ne suit pas ce fichier. Passer en 1080p ?", QualityLogic.suggestMessage(null))
    }

    // ── Coupures ──

    @Test
    fun `attentes apres un saut ou avant la premiere image ignorees`() {
        val now = 100_000L
        assertTrue(QualityLogic.isRebuffer(playWhenReady = true, readyOnce = true, nowMs = now, lastSeekMs = now - 10_000))
        // Moins de 3 s après un saut (ou un changement de flux) : pas une coupure
        assertFalse(QualityLogic.isRebuffer(true, true, now, lastSeekMs = now - 2_999))
        assertTrue(QualityLogic.isRebuffer(true, true, now, lastSeekMs = now - 3_000))
        // Démarrage (pas encore d'image) ou pause : pas une coupure
        assertFalse(QualityLogic.isRebuffer(true, readyOnce = false, nowMs = now, lastSeekMs = 0))
        assertFalse(QualityLogic.isRebuffer(playWhenReady = false, readyOnce = true, nowMs = now, lastSeekMs = 0))
    }

    @Test
    fun `trois coupures en cinq minutes`() {
        val min = 60_000L
        var times = emptyList<Long>()
        times = QualityLogic.record(times, 0)
        times = QualityLogic.record(times, 2 * min)
        assertFalse(QualityLogic.shouldSuggest(times, 2 * min, Quality.ORIGINAL, Quality.HD_SDR, declined = false, bitrate = 89_700_000))
        times = QualityLogic.record(times, 4 * min)
        assertTrue(QualityLogic.shouldSuggest(times, 4 * min, Quality.ORIGINAL, Quality.HD_SDR, declined = false, bitrate = 89_700_000))
    }

    @Test
    fun `fenetre glissante, les vieilles coupures sortent`() {
        val min = 60_000L
        var times = emptyList<Long>()
        for (t in listOf(0L, 3 * min, 6 * min)) times = QualityLogic.record(times, t)
        // La première a 6 min à la troisième : elle ne compte plus
        assertEquals(listOf(3 * min, 6 * min), times)
        assertFalse(QualityLogic.shouldSuggest(times, 6 * min, Quality.ORIGINAL, Quality.HD_SDR, false, null))
        times = QualityLogic.record(times, 7 * min)
        assertTrue(QualityLogic.shouldSuggest(times, 7 * min, Quality.ORIGINAL, Quality.HD_SDR, false, null))
        // Plus rien pendant 5 min : la fenêtre se vide
        assertFalse(QualityLogic.shouldSuggest(times, 12 * min + 1, Quality.ORIGINAL, Quality.HD_SDR, false, null))
    }

    @Test
    fun `pas de proposition deja en 1080p, apres un refus, ou sans conversion`() {
        val times = listOf(0L, 1_000L, 2_000L)
        val now = 3_000L
        assertFalse(QualityLogic.shouldSuggest(times, now, Quality.HD_SDR, Quality.HD_SDR, false, 89_700_000))
        assertFalse(QualityLogic.shouldSuggest(times, now, Quality.HD_HDR, Quality.HD_HDR, false, 89_700_000))
        assertFalse(QualityLogic.shouldSuggest(times, now, Quality.ORIGINAL, Quality.HD_SDR, declined = true, bitrate = 89_700_000))
        assertFalse(QualityLogic.shouldSuggest(times, now, Quality.ORIGINAL, reduced = null, declined = false, bitrate = 89_700_000))
    }

    @Test
    fun `fichier leger, le 1080p n aiderait pas`() {
        val times = listOf(0L, 1_000L, 2_000L)
        assertFalse(QualityLogic.shouldSuggest(times, 3_000L, Quality.ORIGINAL, Quality.HD_SDR, false, bitrate = 8_000_000))
        assertTrue(QualityLogic.shouldSuggest(times, 3_000L, Quality.ORIGINAL, Quality.HD_SDR, false, bitrate = 25_000_000))
        // Débit inconnu (serveur ancien) : on se fie aux coupures
        assertTrue(QualityLogic.shouldSuggest(times, 3_000L, Quality.ORIGINAL, Quality.HD_SDR, false, bitrate = null))
    }
}
