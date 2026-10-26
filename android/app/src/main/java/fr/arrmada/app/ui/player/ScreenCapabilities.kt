package fr.arrmada.app.ui.player

import android.content.Context
import android.hardware.display.DisplayManager
import android.media.MediaCodecList
import android.view.Display
import fr.arrmada.app.data.DolbyVisionLogic

/**
 * Ce que l'écran et l'appareil savent afficher en HDR.
 *
 * Même règle que le lecteur (Media3) : si l'écran n'annonce pas le Dolby
 * Vision, une piste Dolby Vision est confiée au décodeur HEVC ordinaire. Pour
 * un profil 5, c'est l'image violette ; l'appli demande donc la conversion
 * SDR à Jellyfin avant même de lancer la lecture.
 *
 * Shield : l'écran n'annonce ses formats HDR que si *Paramètres › Appareil ›
 * Écran et son › Réglages avancés d'affichage › Faire correspondre la plage
 * dynamique du contenu* est activé (et le Dolby Vision coché).
 */
object ScreenCapabilities {

    /** Écran Dolby Vision ET décodeur Dolby Vision dans l'appareil. */
    fun dolbyVision(context: Context): Boolean =
        Display.HdrCapabilities.HDR_TYPE_DOLBY_VISION in hdrTypes(context) && hasDolbyVisionDecoder()

    /**
     * Écran HDR10 : condition pour proposer le 1080p HDR (ADR-012) ; sinon
     * la qualité réduite est le 1080p SDR.
     */
    fun hdr10(context: Context): Boolean = Display.HdrCapabilities.HDR_TYPE_HDR10 in hdrTypes(context)

    /** Libellé des Réglages : « HDR10 · HLG · Dolby Vision », ou « SDR… ». */
    fun label(context: Context): String =
        DolbyVisionLogic.screenLabel(hdrTypes(context).mapNotNull(NAMES::get), hasDolbyVisionDecoder())

    /** Formats HDR annoncés par l'écran principal (vide si l'écran n'est pas HDR). */
    @Suppress("DEPRECATION") // getHdrCapabilities : toujours la seule lecture valable jusqu'à Android 13
    private fun hdrTypes(context: Context): List<Int> {
        val display = (context.getSystemService(Context.DISPLAY_SERVICE) as? DisplayManager)
            ?.getDisplay(Display.DEFAULT_DISPLAY) ?: return emptyList()
        return runCatching {
            if (display.isHdr) display.hdrCapabilities?.supportedHdrTypes?.toList().orEmpty() else emptyList()
        }.getOrDefault(emptyList())
    }

    /** Un décodeur matériel accepte-t-il le Dolby Vision (« video/dolby-vision ») ? */
    private fun hasDolbyVisionDecoder(): Boolean = runCatching {
        MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos.any { codec ->
            !codec.isEncoder && codec.supportedTypes.any { it.equals(DolbyVisionLogic.MIME, ignoreCase = true) }
        }
    }.getOrDefault(false)

    private val NAMES = mapOf(
        Display.HdrCapabilities.HDR_TYPE_HDR10 to "HDR10",
        Display.HdrCapabilities.HDR_TYPE_HLG to "HLG",
        HDR_TYPE_HDR10_PLUS to "HDR10+",
        Display.HdrCapabilities.HDR_TYPE_DOLBY_VISION to "Dolby Vision",
    )

    /** Display.HdrCapabilities.HDR_TYPE_HDR10_PLUS (constante d'Android 10, l'appli démarre à Android 8). */
    private const val HDR_TYPE_HDR10_PLUS = 4
}
