package fr.arrmada.app.data

/**
 * Écran noir avec le son : l'appareil n'a pas de décodeur pour l'image du
 * fichier.
 *
 * Le cas réel : un film en AV1 sur une Shield (pas de décodeur AV1), un
 * HEVC 10 bits sur un boîtier d'entrée de gamme, du VC-1 ou du MPEG-4 ASP sur
 * une TV qui ne les a pas. Le lecteur (Media3) ne signale alors AUCUNE
 * erreur : il écarte la piste vidéo et joue le son seul, sur un écran noir.
 * Autre forme : la piste est acceptée, puis son décodeur plante.
 *
 * Remède : Jellyfin réencode l'image dans un format que tout appareil lit.
 * On descend d'un cran à la fois : la version 1080p proposée sur cet écran
 * (HDR10 en HEVC si l'écran est HDR, voir [QualityLogic.reduced]), puis le
 * 1080p SDR en H.264, lisible partout. Le remux ne sert à rien ici : il
 * garde l'image telle quelle.
 *
 * Logique pure (sans Android) : testée sur la JVM.
 */
object VideoRescueLogic {

    /**
     * Le fichier a une image que le lecteur ne montrera pas : au moins une
     * piste vidéo ([videoTracks]), aucune retenue ([anySelected]). Un fichier
     * sans piste vidéo (musique) n'est pas concerné.
     */
    fun noPicture(videoTracks: Int, anySelected: Boolean): Boolean = videoTracks > 0 && !anySelected

    /**
     * Qualité à essayer quand l'image de [current] ne s'affiche pas, ou null
     * s'il n'y a plus rien à tenter (déjà en H.264, ou élément hors Jellyfin).
     * [reduced] : la version 1080p proposée sur cet écran.
     */
    fun next(current: Quality, reduced: Quality?, info: PlayInfo): Quality? = when (current) {
        Quality.ORIGINAL -> reduced ?: Quality.HD_SDR.takeIf { info.sdrStream.isNotBlank() }
        Quality.HD_HDR -> Quality.HD_SDR.takeIf { info.sdrStream.isNotBlank() }
        Quality.HD_SDR -> null
    }

    /** Nom courant du format vidéo d'un type MIME : « video/av01 » → « AV1 ». */
    fun codecName(mime: String?): String = when (mime?.lowercase()) {
        "video/av01" -> "AV1"
        "video/hevc" -> "HEVC"
        "video/avc" -> "H.264"
        "video/dolby-vision" -> "Dolby Vision"
        "video/x-vnd.on2.vp9" -> "VP9"
        "video/x-vnd.on2.vp8" -> "VP8"
        "video/mp4v-es" -> "MPEG-4"
        "video/mpeg2" -> "MPEG-2"
        "video/mpeg" -> "MPEG"
        "video/wvc1" -> "VC-1"
        "video/divx" -> "DivX"
        "video/mjpeg" -> "MJPEG"
        null, "" -> "vidéo"
        else -> mime.orEmpty().substringAfter('/').uppercase()
    }

    /** Message de la bascule : « Image AV1 non décodée par cet appareil : convertie par Jellyfin (1080p) ». */
    fun rescueMessage(mime: String?): String =
        "Image ${codecName(mime)} non décodée par cet appareil : convertie par Jellyfin (1080p)"

    /** Message quand rien ne peut convertir (vidéo hors médiathèque, ou conversion déjà en échec). */
    fun stuckMessage(mime: String?): String =
        "Image ${codecName(mime)} illisible sur cet appareil : pas d’image, le son seul"
}
