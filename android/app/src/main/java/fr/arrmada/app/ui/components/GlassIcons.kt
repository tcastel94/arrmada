package fr.arrmada.app.ui.components

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

/**
 * Pictogrammes au trait de la barre du haut (outils de l'accueil TV).
 * Dessinés ici en quelques lignes plutôt que d'ajouter une bibliothèque
 * d'icônes : 5 dessins, 0 dépendance. Tracés en blanc ; la couleur réelle
 * (blanc au repos, sombre au focus) est appliquée à l'affichage.
 *
 * Chaque tracé suit la syntaxe SVG (« M » = aller à, « L » = ligne,
 * « a » = arc…) sur une grille de 24 × 24.
 */
object GlassIcons {
    val Search: ImageVector = stroke(
        "search",
        "M5,11a6,6 0 1,0 12,0a6,6 0 1,0 -12,0",
        "M16,16L20,20",
    )
    val Download: ImageVector = stroke(
        "download",
        "M12,4V15",
        "M7,10L12,15L17,10",
        "M5,20H19",
    )
    val Apps: ImageVector = stroke(
        "apps",
        "M4,4h7v7h-7z",
        "M13,4h7v7h-7z",
        "M4,13h7v7h-7z",
        "M13,13h7v7h-7z",
    )
    val Board: ImageVector = stroke(
        "board",
        "M4,17a8,8 0 1,1 16,0",
        "M12,17L16,12",
    )
    val Settings: ImageVector = stroke(
        "settings",
        "M9,12a3,3 0 1,0 6,0a3,3 0 1,0 -6,0",
        "M12,3v3M12,18v3M3,12h3M18,12h3",
        "M5.6,5.6l2.1,2.1M16.3,16.3l2.1,2.1M5.6,18.4l2.1,-2.1M16.3,7.7l2.1,-2.1",
    )

    /** Pictogramme 24 × 24 fait de traits arrondis de 2 d'épaisseur, sans remplissage. */
    private fun stroke(name: String, vararg paths: String): ImageVector {
        val builder = ImageVector.Builder(
            name = name,
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f,
        )
        paths.forEach { data ->
            builder.addPath(
                pathData = addPathNodes(data),
                fill = null,
                stroke = SolidColor(Color.White),
                strokeLineWidth = 2f,
                strokeLineCap = StrokeCap.Round,
                strokeLineJoin = StrokeJoin.Round,
            )
        }
        return builder.build()
    }
}
