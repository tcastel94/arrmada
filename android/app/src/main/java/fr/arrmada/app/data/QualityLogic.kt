package fr.arrmada.app.data

/** Qualité de lecture choisie dans le menu pause (ADR-012). */
enum class Quality {
    ORIGINAL, // fichier d'origine en direct (ou remux, image intacte)
    HD_HDR, // 1080p HDR10 réencodé par Jellyfin (flux `lite_stream`, si le serveur l'a)
    HD_SDR, // 1080p SDR réencodé par Jellyfin (flux `sdr_stream`, mappage tonal)
}

/** Réglage « Qualité de lecture par défaut » de cette TV. */
enum class DefaultQuality { ORIGINAL, HD_1080 }

/** Une ligne du panneau Qualité : libellés, flux à charger, choisissable ou non ici. */
data class QualityOption(
    val quality: Quality,
    val title: String,
    val detail: String,
    val url: String,
    val hls: Boolean,
    val available: Boolean = true,
)

/**
 * Qualité de lecture : fichier d'origine, ou version 1080p allégée.
 *
 * Le cas réel : une Shield sur un câble abîmé, liée à 100 Mb/s, et un remux
 * 4K à 90 Mb/s de moyenne (pointes bien au-delà). Le lecteur se fige, repart,
 * se refige ; rien ne dit à l'utilisateur que c'est son réseau. Jellyfin
 * peut convertir à la volée en 1080p à 20 Mb/s (NVENC), qui passe partout.
 *
 * Deux portes d'entrée : le choix à la main (menu pause › Qualité, réglage
 * par défaut de la TV), et la proposition automatique quand les coupures
 * s'enchaînent ([shouldSuggest]).
 *
 * Logique pure (sans Android) : testée sur la JVM.
 */
object QualityLogic {

    /** Débit visé par la conversion 1080p (préréglage « sdr » du serveur). */
    const val REDUCED_MBPS = 20

    /** Coupures qui déclenchent la proposition, dans la fenêtre glissante… */
    const val REBUFFER_COUNT = 3

    /** … de 5 minutes : une coupure isolée (Wi-Fi qui hoquette) ne compte pas. */
    const val REBUFFER_WINDOW_MS = 5 * 60_000L

    /**
     * Après un saut (avance rapide, chapitre) ou un changement de flux, le
     * lecteur remplit forcément sa mémoire tampon : 3 s pendant lesquelles
     * une attente n'est pas une coupure.
     */
    const val SEEK_GRACE_MS = 3_000L

    /**
     * En dessous de ce débit, passer en 1080p à 20 Mb/s ne soulagerait guère
     * le réseau : les coupures ont une autre cause (serveur, Wi-Fi mort…).
     */
    const val MIN_SUGGEST_BITRATE = 25_000_000L

    /** Débit en Mb/s arrondi (89 700 000 → 90), null s'il est inconnu. */
    fun mbps(bitrate: Long?): Int? =
        bitrate?.takeIf { it > 0 }?.let { ((it + 500_000) / 1_000_000).toInt() }

    /** « 4K · Dolby Vision » + débit → « 4K · Dolby Vision · 90 Mb/s ». */
    fun originalDetail(format: String, bitrate: Long?): String =
        listOfNotNull(format.ifBlank { null }, mbps(bitrate)?.let { "$it Mb/s" })
            .joinToString(" · ")
            .ifBlank { "Fichier d’origine" }

    /** Le flux 1080p HDR a-t-il un sens ici ? Serveur qui le fournit, écran HDR10, image HDR. */
    private fun hdrAvailable(info: PlayInfo, screenHdr10: Boolean): Boolean =
        info.liteStream.isNotBlank() && screenHdr10 && !info.videoRange.equals("SDR", ignoreCase = true)

    /**
     * Options du panneau Qualité, dans l'ordre affiché.
     *
     * [originalFormat] : format de l'image d'origine (« 4K · Dolby Vision ») ;
     * [doviForcedSdr] : le Dolby Vision profil 5 a imposé la conversion SDR
     * (écran sans DV) — l'original reste listé, mais indisponible.
     * Élément hors Jellyfin (écran Vidéos, pas de `sdr_stream`) : l'original seul.
     */
    fun options(info: PlayInfo, screenHdr10: Boolean, originalFormat: String, doviForcedSdr: Boolean): List<QualityOption> {
        val original = QualityOption(
            Quality.ORIGINAL,
            "Original",
            if (doviForcedSdr) "Dolby Vision : couleurs fausses sur cet écran" else originalDetail(originalFormat, info.bitrate),
            info.stream,
            hls = info.mode == "remux",
            available = !doviForcedSdr,
        )
        val hdr = QualityOption(
            Quality.HD_HDR,
            "1080p HDR · $REDUCED_MBPS Mb/s",
            "Converti par Jellyfin, HDR10 gardé",
            info.liteStream,
            hls = true,
        ).takeIf { hdrAvailable(info, screenHdr10) && !doviForcedSdr }
        val sdr = QualityOption(
            Quality.HD_SDR,
            "1080p SDR · $REDUCED_MBPS Mb/s",
            "Converti par Jellyfin, pour un réseau lent",
            info.sdrStream,
            hls = true,
        ).takeIf { info.sdrStream.isNotBlank() }
        return listOfNotNull(original, hdr, sdr)
    }

    /** La version 1080p à proposer : HDR si l'écran et le serveur le permettent, sinon SDR ; null si aucune. */
    fun reduced(info: PlayInfo, screenHdr10: Boolean): Quality? = when {
        hdrAvailable(info, screenHdr10) -> Quality.HD_HDR
        info.sdrStream.isNotBlank() -> Quality.HD_SDR
        else -> null
    }

    /**
     * Qualité au lancement. Le Dolby Vision profil 5 sur un écran sans DV
     * passe avant tout (sinon image violette) ; ensuite le réglage de la TV.
     */
    fun initial(info: PlayInfo, screenHdr10: Boolean, screenDolbyVision: Boolean, default: DefaultQuality): Quality = when {
        DolbyVisionLogic.startWithSdr(info, screenDolbyVision) -> Quality.HD_SDR
        default == DefaultQuality.HD_1080 -> reduced(info, screenHdr10) ?: Quality.ORIGINAL
        else -> Quality.ORIGINAL
    }

    /** Adresse et nature (HLS ?) du flux d'une qualité. */
    fun source(info: PlayInfo, quality: Quality): Pair<String, Boolean> = when (quality) {
        Quality.ORIGINAL -> info.stream to (info.mode == "remux")
        Quality.HD_HDR -> info.liteStream to true
        Quality.HD_SDR -> info.sdrStream to true
    }

    /** Toast du changement : « Qualité réduite : 1080p · 20 Mb/s ». */
    fun switchMessage(quality: Quality): String = when (quality) {
        Quality.ORIGINAL -> "Qualité d’origine"
        Quality.HD_HDR -> "Qualité réduite : 1080p HDR · $REDUCED_MBPS Mb/s"
        Quality.HD_SDR -> "Qualité réduite : 1080p · $REDUCED_MBPS Mb/s"
    }

    // ── Détection des coupures ─────────────────────────────────────────

    /**
     * Une attente de chargement est-elle une vraie coupure ? Oui seulement en
     * pleine lecture ([playWhenReady]), après la première image ([readyOnce]),
     * et pas juste après un saut ou un changement de flux ([lastSeekMs]).
     */
    fun isRebuffer(playWhenReady: Boolean, readyOnce: Boolean, nowMs: Long, lastSeekMs: Long): Boolean =
        playWhenReady && readyOnce && nowMs - lastSeekMs >= SEEK_GRACE_MS

    /** Coupures gardées après celle de [nowMs] : celles de la fenêtre glissante. */
    fun record(times: List<Long>, nowMs: Long): List<Long> =
        (times + nowMs).filter { nowMs - it < REBUFFER_WINDOW_MS }

    /**
     * Proposer le 1080p ? [REBUFFER_COUNT] coupures dans la fenêtre, en
     * lecture « Original », une version 1080p disponible ([reduced]), pas de
     * refus pendant cette séance, et un fichier assez lourd pour que la
     * conversion aide (débit inconnu : on se fie aux coupures).
     */
    fun shouldSuggest(
        times: List<Long>,
        nowMs: Long,
        current: Quality,
        reduced: Quality?,
        declined: Boolean,
        bitrate: Long?,
    ): Boolean {
        if (current != Quality.ORIGINAL || reduced == null || declined) return false
        if (bitrate != null && bitrate in 1 until MIN_SUGGEST_BITRATE) return false
        return times.count { nowMs - it < REBUFFER_WINDOW_MS } >= REBUFFER_COUNT
    }

    /** Texte de la carte : « Le réseau ne suit pas ce fichier (90 Mb/s). Passer en 1080p ? » */
    fun suggestMessage(bitrate: Long?): String =
        "Le réseau ne suit pas ce fichier" + (mbps(bitrate)?.let { " ($it Mb/s)" } ?: "") + ". Passer en 1080p ?"
}
