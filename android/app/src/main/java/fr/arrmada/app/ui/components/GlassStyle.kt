package fr.arrmada.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.LocalContentColor
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import fr.arrmada.app.ui.theme.ArrColors

/**
 * Style « verre dépoli », commun à toute l'appli (né dans le menu pause du
 * lecteur) : une seule définition, comme un fichier de conf inclus partout,
 * pour que l'appli et le lecteur gardent le même look.
 *
 * Règle unique : focus = pastille ou contour blanc, texte sombre ; l'accent
 * bleu est réservé à ce qui est « en cours » (progression, chapitre lu,
 * réglage coché ✓).
 *
 * Pas de vrai flou (il n'existe qu'à partir d'Android 12 et coûte cher sur
 * un petit boîtier) : le « verre » est du blanc translucide posé sur l'image.
 */
internal val Glass = Color(0x2EFFFFFF) // fond des boutons au repos (blanc 18 %)
internal val GlassStrong = Color(0x47FFFFFF) // onglet choisi, bouton principal, réglage actuel
internal val GlassPanel = Color(0x1AFFFFFF) // fond d'une section (blanc 10 %)
internal val GlassEdge = Color(0x66FFFFFF) // liseré d'une pastille choisie (blanc 40 %)
internal val Dim = Color(0x99FFFFFF) // texte secondaire sur l'image (blanc 60 %)
internal val Ink = Color(0xFF0B0F17) // texte sur une pastille blanche
internal val Pressed = Color(0xE6FFFFFF) // pastille enfoncée (OK appuyé)
internal val CardShape = RoundedCornerShape(12.dp)
internal val PillShape = RoundedCornerShape(50)
internal val PanelShape = RoundedCornerShape(18.dp)

/** Voile du menu pause : haut à peine voilé (image lisible), bas très sombre. */
internal val PauseScrim = Brush.verticalGradient(
    0f to Color(0x80000000),
    0.22f to Color(0x14000000),
    0.42f to Color(0x33000000),
    0.62f to Color(0xB3050810),
    1f to Color(0xF2050810),
)

/** Voile d'un sous-menu : plus couvrant (il y a du texte partout), l'image reste devinable. */
internal val SubMenuScrim = Brush.verticalGradient(
    0f to Color(0xB3000000),
    0.5f to Color(0xD9050810),
    1f to Color(0xF2050810),
)

/**
 * Bouton pastille du lecteur : c'est [ArrButton], le bouton de toute
 * l'appli (une seule définition). `glyph` = le petit symbole à gauche (▶, ♪…),
 * `selected` = sous-menu ouvert (même fond que le bouton principal).
 */
@Composable
internal fun GlassButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    glyph: String? = null,
    primary: Boolean = false,
    selected: Boolean = false,
) {
    ArrButton(text, onClick, modifier, primary = primary || selected, leading = glyph)
}

/**
 * Pastille de réglage (programme sonore, mode nuit…) : verre au repos,
 * plus claire et cochée ✓ quand c'est le réglage actuel, blanche au focus.
 */
@Composable
internal fun GlassChip(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = modifier.height(38.dp).tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(PillShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.07f),
        border = ClickableSurfaceDefaults.border(
            border = if (selected) Border(BorderStroke(1.dp, GlassEdge), shape = PillShape) else Border.None,
        ),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) GlassStrong else Glass,
            contentColor = Color.White,
            focusedContainerColor = Color.White,
            focusedContentColor = Ink,
            pressedContainerColor = Pressed,
            pressedContentColor = Ink,
        ),
    ) {
        Row(
            Modifier.fillMaxHeight().padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            if (selected) Text("✓", style = MaterialTheme.typography.labelLarge, color = ArrColors.AccentText)
            Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 1)
        }
    }
}

/**
 * Onglet texte (onglets du menu pause, sections de la barre du haut) :
 * transparent au repos, verre léger quand il est choisi, blanc au focus.
 * [current] ajoute le petit trait bleu de la section où l'on est.
 * [onFocus] : appelé quand il prend le focus (le menu pause change d'onglet
 * dès le focus ; la barre du haut, elle, attend OK).
 */
@Composable
internal fun GlassTab(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    current: Boolean = false,
    onFocus: () -> Unit = {},
) {
    Surface(
        onClick = onClick,
        modifier = modifier.height(36.dp).onFocusChanged { if (it.isFocused) onFocus() }.tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(PillShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.05f),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) Color(0x24FFFFFF) else Color.Transparent,
            contentColor = if (selected) Color.White else Dim,
            focusedContainerColor = Color.White,
            focusedContentColor = Ink,
        ),
    ) {
        // Largeur = celle du texte (fillMaxSize étirerait l'onglet sur toute la rangée)
        Box(Modifier.fillMaxHeight().padding(horizontal = 16.dp), contentAlignment = Alignment.Center) {
            Text(label, style = MaterialTheme.typography.titleMedium, maxLines = 1)
            if (current) {
                Box(
                    Modifier
                        .align(Alignment.BottomCenter)
                        .padding(bottom = 3.dp)
                        .size(width = 14.dp, height = 3.dp)
                        .background(ArrColors.Accent, PillShape)
                )
            }
        }
    }
}

/**
 * Bouton rond à pictogramme (outils de la barre du haut) : discret au
 * repos, pastille blanche au focus. Son nom s'affiche alors dessous, pour
 * ne jamais avoir à deviner ce que fait un pictogramme.
 */
@Composable
internal fun GlassIconButton(icon: ImageVector, label: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    var focused by remember { mutableStateOf(false) }
    // zIndex : le nom, qui déborde sous le bouton, passe au-dessus du contenu de l'écran
    Box(modifier.size(36.dp).zIndex(if (focused) 1f else 0f)) {
        Surface(
            onClick = onClick,
            modifier = Modifier.fillMaxSize().onFocusChanged { focused = it.isFocused }.tapToClick(onClick),
            shape = ClickableSurfaceDefaults.shape(PillShape),
            scale = ClickableSurfaceDefaults.scale(focusedScale = 1.1f),
            colors = ClickableSurfaceDefaults.colors(
                containerColor = Color.Transparent,
                contentColor = Dim,
                focusedContainerColor = Color.White,
                focusedContentColor = Ink,
                pressedContainerColor = Pressed,
                pressedContentColor = Ink,
            ),
        ) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Image(
                    imageVector = icon,
                    contentDescription = label,
                    colorFilter = ColorFilter.tint(LocalContentColor.current),
                    modifier = Modifier.size(19.dp),
                )
            }
        }
        if (focused) {
            // Bulle du nom, centrée sous le bouton ; elle peut être plus large que lui
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                color = Ink,
                maxLines = 1,
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .offset(y = 44.dp)
                    .wrapContentWidth(unbounded = true)
                    .background(Color(0xEBFFFFFF), PillShape)
                    .padding(horizontal = 9.dp, vertical = 3.dp),
            )
        }
    }
}

/** Section d'un sous-menu : carte de verre arrondie, titre discret, contenu. */
@Composable
internal fun GlassSection(title: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(
        modifier
            .fillMaxWidth()
            .background(GlassPanel, PanelShape)
            .border(1.dp, Color(0x14FFFFFF), PanelShape)
            .padding(horizontal = 18.dp, vertical = 14.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(title, style = MaterialTheme.typography.labelLarge, color = Dim, maxLines = 1)
        content()
    }
}
