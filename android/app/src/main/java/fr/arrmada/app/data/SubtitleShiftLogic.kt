package fr.arrmada.app.data

import java.util.Locale

/**
 * Décalage manuel des sous-titres (menu pause › Sous-titres › −/+ 0,5 s).
 *
 * Le lecteur (Media3) ne sait pas retarder une piste de sous-titres : le
 * serveur en sert une copie décalée (`?shift=1500`), ajoutée à côté des
 * pistes du fichier sous le nom « Français (décalé +1,5 s) » et choisie
 * aussitôt. Pour une piste intégrée au MKV, c'est Jellyfin qui l'extrait.
 *
 * Logique pure : testée sur la JVM.
 */
object SubtitleShiftLogic {

    const val STEP_MS = 500
    private const val MARK = " (décalé "

    /** « +1,5 s », « −0,5 s ». */
    fun format(ms: Int): String {
        val sign = if (ms < 0) "−" else "+"
        return sign + String.format(Locale.FRENCH, "%.1f s", kotlin.math.abs(ms) / 1000.0)
    }

    /** Nom de la piste sans la mention du décalage. */
    fun baseLabel(label: String): String = label.substringBefore(MARK)

    /** Nom de la copie décalée. */
    fun shiftedLabel(base: String, ms: Int): String = baseLabel(base) + MARK + format(ms) + ")"

    /** Adresse de la copie décalée (remplace un décalage précédent ; 0 : l'original). */
    fun shiftedUrl(url: String, ms: Int): String {
        val clean = url.replace(Regex("""[?&]shift=-?\d+"""), "")
        if (ms == 0) return clean
        return clean + (if ('?' in clean) "&" else "?") + "shift=$ms"
    }

    /**
     * Fichier de sous-titres à décaler pour la piste affichée : la même piste
     * posée à côté (même nom), sinon la piste intégrée de même langue (et
     * « forcés » si la piste affichée l'est). null : rien à décaler (piste
     * image PGS, par exemple).
     */
    fun source(
        selectedLabel: String,
        selectedLanguage: String?,
        forced: Boolean,
        side: List<SideSubtitle>,
        embedded: List<SideSubtitle>,
    ): SideSubtitle? {
        val base = baseLabel(selectedLabel)
        side.firstOrNull { baseLabel(it.label) == base && MARK !in it.label }?.let { return it }
        val lang = selectedLanguage?.lowercase()?.take(2).orEmpty()
        val sameLanguage = embedded.filter { it.language.isNotBlank() && it.language == lang }
        return sameLanguage.firstOrNull { ("forcés" in it.label) == forced } ?: sameLanguage.firstOrNull()
    }
}
