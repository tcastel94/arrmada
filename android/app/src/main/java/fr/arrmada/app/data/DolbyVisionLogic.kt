package fr.arrmada.app.data

/**
 * Dolby Vision « profil 5 » : le cas qui donne une image violette et verte.
 *
 * Le profil 5 code l'image dans un espace de couleurs propre à Dolby (IPT),
 * sans image de secours HDR10 : seul un écran Dolby Vision sait l'afficher.
 * Ailleurs, le lecteur le décode comme un HEVC ordinaire et les couleurs
 * partent en violet / vert. Les profils 7 et 8 (Blu-ray, la plupart des
 * WEB-DL) portent une image HDR10 de secours, lisible partout.
 *
 * Remède quand l'écran n'a pas le Dolby Vision : Jellyfin convertit l'image
 * en SDR avec son « mappage tonal » (flux `sdr_stream` du serveur).
 *
 * Logique pure (sans Android) : testée sur la JVM.
 */
object DolbyVisionLogic {

    /** Type MIME que le lecteur donne à une piste Dolby Vision (MKV ou MP4). */
    const val MIME = "video/dolby-vision"

    /** Préfixes de la chaîne « codecs » d'une piste Dolby Vision (RFC 6381). */
    private val PREFIXES = setOf("dvhe", "dvh1", "dvav", "dva1")

    /** Profil Dolby Vision d'une chaîne « codecs » : « dvhe.05.06 » → 5 ; autre chose → null. */
    fun profile(codecs: String?): Int? {
        val parts = codecs?.trim()?.lowercase()?.split('.') ?: return null
        if (parts.size < 2 || parts[0] !in PREFIXES) return null
        return parts[1].toIntOrNull()
    }

    /** Piste en Dolby Vision sans image de secours (profil 5) ? */
    fun withoutFallback(mime: String?, codecs: String?): Boolean =
        mime == MIME && profile(codecs) == 5

    /**
     * Démarrer directement sur la conversion SDR ? Oui si le serveur annonce
     * un Dolby Vision sans secours, que cet écran ne le gère pas et que
     * Jellyfin peut convertir (élément Jellyfin, pas un fichier de l'écran Vidéos).
     */
    fun startWithSdr(info: PlayInfo, screenHasDolbyVision: Boolean): Boolean =
        info.doviOnly && !screenHasDolbyVision && info.sdrStream.isNotBlank()

    /**
     * Libellé des formats HDR de l'écran pour les Réglages : « HDR10 · HLG ·
     * Dolby Vision », ou « SDR » quand l'écran n'annonce aucun HDR.
     */
    fun screenLabel(hdrTypes: List<String>, dolbyVisionDecoder: Boolean): String {
        if (hdrTypes.isEmpty()) return "SDR (pas de HDR annoncé)"
        val label = hdrTypes.joinToString(" · ")
        return if ("Dolby Vision" in hdrTypes && !dolbyVisionDecoder) "$label (pas de décodeur Dolby Vision)" else label
    }
}
