package fr.arrmada.app.data

/**
 * Aperçu en image quand on avance / recule (vignettes « trickplay » de
 * Jellyfin), sans écran : testé en JVM.
 *
 * Jellyfin colle ses vignettes en planches (une image JPEG de 10 × 10
 * vignettes, par exemple) : pour un instant donné, on calcule quelle
 * planche télécharger et où y découper la vignette — comme lire un bloc
 * précis dans un fichier à partir d'un décalage.
 */
data class TrickplayFrame(
    val tile: Int, // n° de planche
    val x: Int, // coin haut gauche de la vignette dans la planche (px)
    val y: Int,
)

object TrickplayLogic {
    /** Planche et position de la vignette de l'instant [positionSeconds] ; null si pas d'aperçu. */
    fun frame(info: Trickplay?, positionSeconds: Double): TrickplayFrame? {
        if (info == null || info.interval <= 0.0 || info.count <= 0 || info.url.isBlank()) return null
        if (info.tileWidth <= 0 || info.tileHeight <= 0 || info.width <= 0 || info.height <= 0) return null
        val index = (positionSeconds.coerceAtLeast(0.0) / info.interval).toInt().coerceIn(0, info.count - 1)
        val perTile = info.tileWidth * info.tileHeight
        val inTile = index % perTile
        return TrickplayFrame(
            tile = index / perTile,
            x = (inTile % info.tileWidth) * info.width,
            y = (inTile / info.tileWidth) * info.height,
        )
    }

    /**
     * Instant montré par la vignette d'un chapitre quand Jellyfin n'a pas
     * extrait d'image de chapitre : quelques secondes après son début (la
     * première image est souvent noire, en fondu), sans déborder sur le suivant.
     */
    fun chapterPreviewAt(start: Double, nextStart: Double?): Double {
        val wanted = start.coerceAtLeast(0.0) + CHAPTER_PREVIEW_OFFSET_S
        if (nextStart == null || nextStart <= start) return wanted
        return minOf(wanted, (start + nextStart) / 2)
    }

    private const val CHAPTER_PREVIEW_OFFSET_S = 5.0

    /** Adresse (relative au serveur) d'une planche. */
    fun tileUrl(info: Trickplay, tile: Int): String = "${info.url}/$tile"

    /**
     * Mode « défilement » : chaque appui déplace une position visée, sans
     * relancer la lecture à chaque fois (on ne saute qu'une fois, au
     * relâchement). Bornée au film : jamais avant 0, jamais après la fin.
     */
    fun scrub(fromMs: Long, deltaMs: Long, durationMs: Long): Long {
        val end = if (durationMs > 0) (durationMs - 1_000).coerceAtLeast(0) else Long.MAX_VALUE
        return (fromMs + deltaMs).coerceIn(0, end)
    }

    /**
     * Pas d'un appui : 10 s en arrière, 30 s en avant ; en restant appuyé
     * (répétition de la touche), le pas grandit pour traverser un film
     * en quelques secondes : ×2 après 5 répétitions, ×4 après 15.
     */
    fun step(forward: Boolean, repeat: Int): Long {
        val base = if (forward) 30_000L else 10_000L
        val factor = when {
            repeat >= 15 -> 4
            repeat >= 5 -> 2
            else -> 1
        }
        return (if (forward) base else -base) * factor
    }
}
