package fr.arrmada.app.data

/**
 * Couleur du halo d'une carte au focus, tirée de son affiche : l'affiche
 * est réduite à quelques dizaines de pixels, on garde la teinte la plus
 * vive (saturée et lumineuse), éclaircie pour bien « briller » sur le fond
 * sombre. Sans bibliothèque (pas de androidx.palette) : quelques lignes de
 * calcul, testables sans appareil.
 *
 * Une affiche grise, noire ou presque blanche n'a pas de teinte nette :
 * null, et la carte garde le halo blanc discret.
 *
 * Pixels au format ARGB d'Android (0xAARRGGBB), comme Bitmap.getPixels.
 */
object PosterColorLogic {

    /** En dessous, l'affiche est jugée « sans couleur » (gris, noir, blanc). */
    private const val MIN_SCORE = 0.18f

    /** Pixels retenus pour la moyenne : ceux au moins aussi vifs que 70 % du plus vif. */
    private const val KEEP_RATIO = 0.7f

    fun accent(pixels: IntArray): Int? {
        val scores = FloatArray(pixels.size) { score(pixels[it]) }
        val best = scores.maxOrNull() ?: return null
        if (best < MIN_SCORE) return null
        // Moyenne des pixels les plus vifs : moins sensible à un pixel isolé
        var r = 0L
        var g = 0L
        var b = 0L
        var n = 0
        pixels.forEachIndexed { i, p ->
            if (scores[i] >= best * KEEP_RATIO) {
                r += (p shr 16) and 0xFF
                g += (p shr 8) and 0xFF
                b += p and 0xFF
                n++
            }
        }
        return brighten((r / n).toInt(), (g / n).toInt(), (b / n).toInt())
    }

    /** Vivacité d'un pixel : saturation × luminosité (0 à 1) ; pixel transparent ou sombre : 0. */
    private fun score(pixel: Int): Float {
        if (((pixel ushr 24) and 0xFF) < 128) return 0f
        val r = (pixel shr 16) and 0xFF
        val g = (pixel shr 8) and 0xFF
        val b = pixel and 0xFF
        val max = maxOf(r, g, b)
        val min = minOf(r, g, b)
        if (max < 64) return 0f // trop sombre : le halo serait invisible
        val saturation = (max - min).toFloat() / max
        val value = max / 255f
        return saturation * value
    }

    /** Pousse la composante la plus forte à 255 (même teinte, plus lumineuse), opaque. */
    private fun brighten(r: Int, g: Int, b: Int): Int {
        val max = maxOf(r, g, b, 1)
        // En entiers : la composante la plus forte tombe pile sur 255 (pas d'arrondi flottant à 254)
        fun c(v: Int) = (v * 255 / max).coerceIn(0, 255)
        return (0xFF shl 24) or (c(r) shl 16) or (c(g) shl 8) or c(b)
    }
}
