package fr.arrmada.app.data

/**
 * « Son conseillé » : quel décodage demander à l'ampli selon le son du
 * film (Atmos, 5.1, stéréo…) et les enceintes de la pièce.
 *
 * Analogie : comme choisir un pilote selon le matériel détecté. Le film
 * dit ce qu'il envoie (objets Atmos / DTS:X, canaux fixes, stéréo), la
 * pièce dit ce qu'elle a (5.1 au salon, 7.2.2 en salle de cinéma, rien
 * sans ampli), et on en déduit le programme Yamaha :
 *  - Straight : décodage direct, chaque son sur l'enceinte prévue
 *    (Atmos replié sur le 5.1 s'il n'y a pas d'enceintes de plafond) ;
 *  - Surround Decoder (Dolby Surround / DTS Neural:X) : étend un son plus
 *    « petit » que la pièce à toutes les enceintes, plafond compris.
 */
object SoundAdvisor {

    /** Enceintes d'une pièce : « 7.2.2 » = 7 principales, 2 caissons, 2 au plafond. */
    data class Layout(val label: String, val main: Int, val subs: Int, val heights: Int) {
        val hasHeights: Boolean get() = heights > 0
    }

    /** Son de la piste audio en cours. */
    data class Sound(val name: String, val channels: Int, val objects: Boolean)

    /** Programme Yamaha conseillé (null : rien à régler), titre court, explication. */
    data class Advice(val program: String?, val headline: String, val detail: String)

    const val STRAIGHT = "straight"
    const val SURROUND_DECODER = "surr_decoder"

    /** « 5.1 », « 7.2.2 » → disposition ; illisible ou vide → null. */
    fun layout(speakers: String?): Layout? {
        val parts = speakers?.trim()?.split(".")?.map { it.toIntOrNull() ?: return null } ?: return null
        if (parts.isEmpty() || parts[0] <= 0) return null
        return Layout(speakers.trim(), parts[0], parts.getOrElse(1) { 0 }, parts.getOrElse(2) { 0 })
    }

    /**
     * Son d'une piste à partir de son type (mime Media3) et du nombre de
     * canaux. Le TrueHD ne dit pas s'il porte de l'Atmos : on s'appuie
     * alors sur ce que Radarr a lu dans le fichier ([fileAudio], « TrueHD Atmos »).
     */
    fun sound(mime: String?, channels: Int, label: String?, fileAudio: String?): Sound {
        val hint = listOfNotNull(label, fileAudio).joinToString(" ")
        val atmos = "atmos" in hint.lowercase()
        return when (mime) {
            "audio/eac3-joc" -> Sound("Dolby Atmos (DD+)", channels, true)
            "audio/true-hd" -> if (atmos) Sound("Dolby Atmos (TrueHD)", channels, true) else Sound("Dolby TrueHD", channels, false)
            "audio/vnd.dts.uhd" -> Sound("DTS:X", channels, true)
            "audio/vnd.dts.hd" -> if ("dts:x" in hint.lowercase() || "dts-x" in hint.lowercase()) Sound("DTS:X", channels, true) else Sound("DTS-HD", channels, false)
            "audio/vnd.dts" -> Sound("DTS", channels, false)
            "audio/eac3" -> Sound("Dolby Digital Plus", channels, false)
            "audio/ac3" -> Sound("Dolby Digital", channels, false)
            "audio/mp4a-latm" -> Sound("AAC", channels, false)
            else -> Sound(mime?.substringAfter('/')?.uppercase() ?: "Audio", channels, false)
        }
    }

    private fun channelsLabel(channels: Int): String = when (channels) {
        1 -> "mono"
        2 -> "stéréo"
        6 -> "5.1"
        8 -> "7.1"
        else -> "$channels canaux"
    }

    /** [screenName] : ce qui joue le son sans ampli (« la TV », « l’appareil »). */
    fun advise(layout: Layout?, sound: Sound?, screenName: String = "la TV"): Advice {
        if (sound == null) return Advice(null, "Son du film en cours de lecture…", "")
        val source = if (sound.objects) sound.name else "${sound.name} ${channelsLabel(sound.channels)}"
        if (layout == null) {
            val heavy = sound.objects || sound.channels > 6 || "TrueHD" in sound.name || "DTS-HD" in sound.name
            return Advice(
                null,
                "Son de $screenName · stéréo",
                if (heavy) {
                    "Pas d’ampli : $source est réduit en stéréo pour $screenName. Une piste Dolby Digital 5.1 donne le même résultat, plus légère."
                } else {
                    "Pas d’ampli : $source est envoyé en stéréo aux haut-parleurs de $screenName."
                },
            )
        }
        val room = layout.label
        val sourceMain = sound.channels - 1 // canaux principaux du film (sans le caisson)
        return when {
            sound.objects && layout.hasHeights -> Advice(
                STRAIGHT, "${sound.name} natif sur $room",
                "Décodage direct (Straight) : chaque son à sa place, enceintes de plafond comprises.",
            )
            sound.objects -> Advice(
                STRAIGHT, "${sound.name} ramené au $room",
                "Pas d’enceintes de plafond : l’ampli replie les effets en hauteur sur le $room (Straight).",
            )
            sound.channels <= 2 -> Advice(
                SURROUND_DECODER, "Stéréo étendue au $room",
                "Surround Decoder répartit la stéréo sur toutes les enceintes ; les voix restent au centre.",
            )
            // Pièce plus riche que le film (plafond, ou plus d'enceintes) : on l'étend
            layout.hasHeights || sourceMain < layout.main -> Advice(
                SURROUND_DECODER, "${channelsLabel(sound.channels)} étendu au $room",
                "Surround Decoder (Dolby Surround / Neural:X) remplit les enceintes " +
                    if (layout.hasHeights) "arrière et de plafond." else "arrière.",
            )
            sourceMain > layout.main -> Advice(
                STRAIGHT, "${channelsLabel(sound.channels)} ramené au $room",
                "Décodage direct (Straight) : l’ampli répartit les canaux en trop sur les enceintes présentes.",
            )
            else -> Advice(
                STRAIGHT, "${channelsLabel(sound.channels)} natif",
                "Décodage direct (Straight) : chaque canal sur son enceinte, sans traitement.",
            )
        }
    }
}
