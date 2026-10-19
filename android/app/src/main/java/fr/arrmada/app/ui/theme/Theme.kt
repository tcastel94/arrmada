package fr.arrmada.app.ui.theme

import android.graphics.Typeface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import androidx.tv.material3.LocalContentColor
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Typography
import androidx.tv.material3.darkColorScheme

/*
 * Charte de l'add-on Kodi (skin « 1080i », inventaire du 19/10/2026),
 * reprise à l'identique : mêmes couleurs, même police condensée.
 *
 * Repère : l'add-on est dessiné en 1920×1080 pixels ; une TV 1080p fait
 * 960×540 « dp » (unité Android). Une cote du skin divisée par 2 donne la
 * cote en dp (affiche 204×306 px → 102×153 dp).
 */
object ArrColors {
    val Night = Color(0xFF0A0E16) // fond
    val Card = Color(0xFF1A2233) // cartes
    val CardDeep = Color(0xFF121826) // bulles, panneaux
    val Accent = Color(0xFF4A9EFF)
    val AccentText = Color(0xFF8CC4FF)
    val Cyan = Color(0xFF22E0EE)
    val Seen = Color(0xFF34D399) // « vu », ok
    val Error = Color(0xFFF87171)
    val Warning = Color(0xFFFBBF24)
    val Text = Color(0xFFF5F7FA)
    val TextSecondary = Color(0xFFC9D3E0)
    val Track = Color(0x1FFFFFFF) // piste des barres de progression (blanc 12 %)

    /** Dégradé des barres de progression : bleu → cyan. */
    val Progress = Brush.horizontalGradient(listOf(Accent, Cyan))
}

/** Police condensée d'Android (celle du skin : Roboto Condensed). */
private val Condensed = FontFamily(Typeface.create("sans-serif-condensed", Typeface.NORMAL))

private val ArrTypography = Typography(
    displayMedium = TextStyle(fontFamily = Condensed, fontWeight = FontWeight.Bold, fontSize = 34.sp),
    headlineMedium = TextStyle(fontFamily = Condensed, fontWeight = FontWeight.Bold, fontSize = 26.sp),
    titleLarge = TextStyle(fontFamily = Condensed, fontWeight = FontWeight.Bold, fontSize = 20.sp),
    titleMedium = TextStyle(fontFamily = Condensed, fontWeight = FontWeight.Bold, fontSize = 16.sp),
    bodyLarge = TextStyle(fontFamily = Condensed, fontSize = 15.sp, lineHeight = 21.sp),
    bodyMedium = TextStyle(fontFamily = Condensed, fontSize = 13.sp, lineHeight = 18.sp),
    labelLarge = TextStyle(fontFamily = Condensed, fontWeight = FontWeight.Bold, fontSize = 14.sp),
    labelMedium = TextStyle(fontFamily = Condensed, fontSize = 12.sp),
    labelSmall = TextStyle(fontFamily = Condensed, fontWeight = FontWeight.Bold, fontSize = 11.sp),
)

@Composable
fun ArrMadaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = ArrColors.Accent,
            onPrimary = ArrColors.Night,
            secondary = ArrColors.Cyan,
            background = ArrColors.Night,
            onBackground = ArrColors.Text,
            surface = ArrColors.Card,
            onSurface = ArrColors.Text,
            onSurfaceVariant = ArrColors.TextSecondary,
            error = ArrColors.Error,
        ),
        typography = ArrTypography,
    ) {
        // Couleur de texte par défaut (sinon : noir hors des « Surface » de la bibliothèque TV)
        CompositionLocalProvider(LocalContentColor provides ArrColors.Text, content = content)
    }
}
