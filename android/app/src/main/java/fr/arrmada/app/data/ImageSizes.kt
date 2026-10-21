package fr.arrmada.app.data

/**
 * Taille des images TMDB à télécharger.
 *
 * Radarr et Sonarr donnent les affiches et les fonds en taille d'origine
 * (« /t/p/original/ ») : 2000 × 3000 pour une affiche, jusqu'à 3840 × 2160
 * pour un fond, soit 1 à 3 Mo chacune. Une affiche de grille fait ~220 px de
 * large à l'écran : on demande à TMDB la taille juste au-dessus (w342), dix
 * fois plus légère. C'est ce qui rendait les écrans lents à s'afficher.
 */
object ImageSizes {
    // Largeurs que TMDB sait servir pour tous les types d'images
    private val WIDTHS = listOf(185, 342, 500, 780, 1280)
    private val TMDB = Regex("""^(https?://image\.tmdb\.org/t/p/)(original|w\d+)(/.+)$""")

    /**
     * Adresse TMDB redimensionnée pour [widthPx] pixels de large, ou null si
     * [url] n'est pas une image TMDB (fanart.tv, images servies par ArrMada…)
     * ou si la taille demandée est déjà la bonne.
     * Au-delà de 1280 px (fond plein écran), w1280 suffit : le fond est voilé
     * et animé, la différence ne se voit pas.
     */
    fun tmdb(url: String, widthPx: Int?): String? {
        val match = TMDB.matchEntire(url) ?: return null
        val wanted = widthPx?.takeIf { it > 0 } ?: return null
        val width = WIDTHS.firstOrNull { it >= wanted } ?: WIDTHS.last()
        val current = match.groupValues[2]
        // Déjà plus petite que la cible (ex. w342 du serveur) : on ne grossit pas
        if (current != "original" && current.removePrefix("w").toInt() <= width) return null
        return match.groupValues[1] + "w$width" + match.groupValues[3]
    }
}
