package fr.arrmada.app.ui.components

import android.content.pm.PackageManager
import android.content.res.Configuration
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Sur quoi tourne l'appli : la même APK sert la TV, la tablette et le téléphone. */
enum class FormFactor { TV, TABLET, PHONE }

/**
 * Format de l'écran, lu une fois en haut de l'appli et transmis à tous les
 * écrans (comme une variable d'environnement exportée à tout un arbre de
 * processus) : marges, nombre de colonnes, navigation, tactile ou télécommande.
 */
@Immutable
data class ScreenLayout(val form: FormFactor, val widthDp: Int) {
    val isTv: Boolean get() = form == FormFactor.TV
    val isTouch: Boolean get() = form != FormFactor.TV
    val isPhone: Boolean get() = form == FormFactor.PHONE

    /** Marge gauche / droite des écrans (48 dp à la TV, comme le skin de l'add-on). */
    val gutter: Dp
        get() = when (form) {
            FormFactor.TV -> 48.dp
            FormFactor.TABLET -> 32.dp
            FormFactor.PHONE -> 16.dp
        }

    /** Assez large pour une colonne à droite (boîtier de la fiche film, deux colonnes). */
    val wide: Boolean get() = widthDp >= 700
}

/** Valeur par défaut : la TV (c'est aussi ce que voient les captures d'écran de test). */
val LocalScreen = staticCompositionLocalOf { ScreenLayout(FormFactor.TV, 960) }

/** Marge latérale de l'écran courant. */
val gutter: Dp
    @Composable @ReadOnlyComposable
    get() = LocalScreen.current.gutter

/**
 * Format de l'appareil : TV (Android TV / leanback), tablette (plus petit côté
 * ≥ 600 dp) ou téléphone. Recalculé quand on tourne l'appareil.
 */
@Composable
fun rememberScreenLayout(): ScreenLayout {
    val config = LocalConfiguration.current
    val context = LocalContext.current
    val tv = (config.uiMode and Configuration.UI_MODE_TYPE_MASK) == Configuration.UI_MODE_TYPE_TELEVISION ||
        context.packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)
    val form = when {
        tv -> FormFactor.TV
        config.smallestScreenWidthDp >= 600 -> FormFactor.TABLET
        else -> FormFactor.PHONE
    }
    return remember(form, config.screenWidthDp) { ScreenLayout(form, config.screenWidthDp) }
}

/**
 * Appui au doigt sur un composant TV. Les cartes et boutons de Compose for
 * TV ne réagissent qu'à la télécommande (touche OK) : sur un téléphone ou une
 * tablette, on ajoute la détection du tap (et de l'appui long). Sans effet à
 * la TV.
 */
@Composable
fun Modifier.tapToClick(onClick: () -> Unit, onLongClick: (() -> Unit)? = null): Modifier {
    if (!LocalScreen.current.isTouch) return this
    val click by rememberUpdatedState(onClick)
    val longClick by rememberUpdatedState(onLongClick)
    val hasLong = onLongClick != null
    return this.pointerInput(hasLong) {
        detectTapGestures(
            onTap = { click() },
            onLongPress = if (hasLong) ({ longClick?.invoke() }) else null,
        )
    }
}

/** Part de la largeur d'un bloc dans un [AdaptiveRow] (poids en ligne, toute la largeur en colonne). */
fun interface Share {
    fun of(weight: Float): Modifier
}

/**
 * Blocs côte à côte sur TV et tablette, les uns sous les autres sur
 * téléphone (en colonne qui défile si [scroll]). [content] reçoit de quoi
 * dimensionner chaque bloc : `share.of(1.4f)`.
 */
@Composable
fun AdaptiveRow(
    modifier: Modifier = Modifier,
    spacing: Dp = 14.dp,
    scroll: Boolean = true,
    content: @Composable (Share) -> Unit,
) {
    if (LocalScreen.current.isPhone) {
        androidx.compose.foundation.layout.Column(
            modifier.then(if (scroll) Modifier.verticalScroll(androidx.compose.foundation.rememberScrollState()) else Modifier),
            verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(spacing),
        ) {
            content(Share { Modifier.fillMaxWidth() })
        }
    } else {
        androidx.compose.foundation.layout.Row(
            modifier,
            horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(spacing),
        ) {
            val row = this
            content(Share { weight -> with(row) { Modifier.weight(weight) } })
        }
    }
}

/** Défilement vertical au doigt (téléphone, tablette) ; à la TV, c'est le focus qui fait défiler. */
@Composable
fun Modifier.touchScroll(): Modifier =
    if (LocalScreen.current.isTouch) verticalScroll(androidx.compose.foundation.rememberScrollState()) else this
