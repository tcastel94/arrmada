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


    // ── Barre du menu pause (façon tvOS) ──
    val Play: ImageVector = stroke(
        "play",
        "M8,5L19,12L8,19Z",
    )
    val Back10: ImageVector = stroke( // flèche en arc vers l'arrière (−10 s)
        "back10",
        "M4,12a8,8 0 1,0 2.3,-5.6",
        "M4,4v5h5",
    )
    val Forward30: ImageVector = stroke( // flèche en arc vers l'avant (+30 s)
        "forward30",
        "M20,12a8,8 0 1,1 -2.3,-5.6",
        "M20,4v5h-5",
    )
    val Audio: ImageVector = stroke( // haut-parleur et ondes
        "audio",
        "M4,9h4l5,-4v14l-5,-4h-4z",
        "M16,9a4,4 0 0,1 0,6",
        "M18.5,6.5a7.5,7.5 0 0,1 0,11",
    )
    val Subtitles: ImageVector = stroke( // bulle avec deux lignes de texte
        "subtitles",
        "M4,5h16v11h-9l-4,3v-3h-3z",
        "M7,9h10",
        "M7,12h6",
    )
    val Quality: ImageVector = stroke( // deux curseurs de réglage
        "quality",
        "M4,7h10M18,7h2",
        "M14,7a2,2 0 1,0 4,0a2,2 0 1,0 -4,0",
        "M4,17h4M12,17h8",
        "M8,17a2,2 0 1,0 4,0a2,2 0 1,0 -4,0",
    )
    val Close: ImageVector = stroke(
        "close",
        "M6,6L18,18",
        "M18,6L6,18",
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
