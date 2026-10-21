package fr.arrmada.app.data

/**
 * Boîtier affiché sur la fiche d'un film, d'après son fichier (même règle
 * que l'add-on Kodi, `screens_data.case_format`) :
 *  - pas de fichier : boîtier transparent ;
 *  - 4K : boîtier noir « 4K ULTRA HD » ;
 *  - SD (moins de 700 lignes) : boîtier DVD ;
 *  - sinon (720p, 1080p, résolution inconnue) : Blu-ray bleu.
 */
object CaseLogic {
    enum class Format(val label: String?) {
        UHD("4K ULTRA HD"),
        BLURAY("Blu-ray Disc"),
        DVD(null),
        CLEAR(null),
    }

    private val UHD_TEXT = Regex("""2160|\b4k\b|\buhd\b""")

    fun format(hasFile: Boolean, file: FileInfo?): Format {
        if (!hasFile) return Format.CLEAR
        val height = file?.height?.takeIf { it > 0 }
        if (height != null) {
            return when {
                height >= 2000 -> Format.UHD
                height >= 700 -> Format.BLURAY
                else -> Format.DVD
            }
        }
        val quality = file?.quality.orEmpty().lowercase()
        return if (UHD_TEXT.containsMatchIn(quality)) Format.UHD else Format.BLURAY
    }
}
