package fr.arrmada.app.ui.components

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.Glow
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.ui.theme.ArrColors

/*
 * Briques d'interface communes, à la façon des contrôles du skin Kodi :
 * l'élément qui a le focus grossit (108 % pour une affiche, 106 % pour un
 * bouton), s'entoure d'un anneau bleu et d'un halo. C'est la télécommande
 * qui « pointe » : il faut toujours voir où l'on est.
 */

private val PosterShape = RoundedCornerShape(7.dp) // coins de 14 px du skin
private val ButtonShape = RoundedCornerShape(6.dp) // coins de 12 px

/** Affiche 2:3 cliquable (rangées et grilles). */
@Composable
fun PosterCard(
    imageUrl: String?,
    title: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    width: Dp = 112.dp,
    progress: Float? = null,
    seen: Boolean = false,
    onFocus: () -> Unit = {},
) {
    Column(modifier.width(width)) {
        Surface(
            onClick = onClick,
            modifier = Modifier
                .width(width)
                .height(width * 1.5f)
                .onFocusChanged { if (it.isFocused) onFocus() },
            shape = ClickableSurfaceDefaults.shape(PosterShape),
            scale = ClickableSurfaceDefaults.scale(focusedScale = 1.08f),
            border = ClickableSurfaceDefaults.border(
                focusedBorder = Border(BorderStroke(2.dp, ArrColors.Accent), shape = PosterShape),
            ),
            glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(ArrColors.Accent.copy(alpha = 0.65f), 14.dp)),
            colors = ClickableSurfaceDefaults.colors(
                containerColor = ArrColors.Card,
                focusedContainerColor = ArrColors.Card,
            ),
        ) {
            ArtImage(imageUrl, title, Modifier.fillMaxSize())
            if (seen) SeenBadge(Modifier.align(Alignment.TopEnd).padding(5.dp))
            if (progress != null && progress > 0f) {
                ProgressBar(progress, Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(6.dp))
            }
        }
    }
}

/** Vignette paysage 16:9 (rangée « Reprendre »). */
@Composable
fun LandscapeCard(
    imageUrl: String?,
    title: String,
    subtitle: String?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    width: Dp = 200.dp,
    progress: Float? = null,
    onFocus: () -> Unit = {},
) {
    Column(modifier.width(width)) {
        Surface(
            onClick = onClick,
            modifier = Modifier
                .width(width)
                .height(width * 9f / 16f)
                .onFocusChanged { if (it.isFocused) onFocus() },
            shape = ClickableSurfaceDefaults.shape(PosterShape),
            scale = ClickableSurfaceDefaults.scale(focusedScale = 1.06f),
            border = ClickableSurfaceDefaults.border(
                focusedBorder = Border(BorderStroke(2.dp, ArrColors.Accent), shape = PosterShape),
            ),
            glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(ArrColors.Accent.copy(alpha = 0.65f), 14.dp)),
            colors = ClickableSurfaceDefaults.colors(
                containerColor = ArrColors.Card,
                focusedContainerColor = ArrColors.Card,
            ),
        ) {
            ArtImage(imageUrl, title, Modifier.fillMaxSize())
            // Voile bas pour lire le titre sur l'image
            Box(
                Modifier
                    .fillMaxSize()
                    .background(Brush.verticalGradient(0.45f to Color.Transparent, 1f to Color(0xE60A0E16)))
            )
            Column(Modifier.align(Alignment.BottomStart).padding(8.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (!subtitle.isNullOrBlank()) {
                    Text(subtitle, style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, maxLines = 1)
                }
                if (progress != null && progress > 0f) {
                    ProgressBar(progress, Modifier.fillMaxWidth().padding(top = 5.dp))
                }
            }
        }
    }
}

/** Image distante ; fond de carte uni tant qu'elle charge ou si elle manque. */
@Composable
fun ArtImage(url: String?, description: String, modifier: Modifier = Modifier, contentScale: ContentScale = ContentScale.Crop) {
    Box(modifier.background(ArrColors.Card)) {
        if (url != null) {
            AsyncImage(model = url, contentDescription = description, contentScale = contentScale, modifier = Modifier.fillMaxSize())
        } else {
            Text(
                description,
                style = MaterialTheme.typography.labelLarge,
                color = ArrColors.TextSecondary,
                modifier = Modifier.align(Alignment.Center).padding(8.dp),
                maxLines = 3,
            )
        }
    }
}

/** Barre de progression du skin : piste blanche 12 %, remplissage bleu → cyan. */
@Composable
fun ProgressBar(progress: Float, modifier: Modifier = Modifier, height: Dp = 3.dp) {
    Box(modifier.height(height).clip(RoundedCornerShape(height)).background(ArrColors.Track)) {
        Box(
            Modifier
                .fillMaxHeight()
                .fillMaxWidth(progress.coerceIn(0f, 1f))
                .background(ArrColors.Progress)
        )
    }
}

@Composable
fun SeenBadge(modifier: Modifier = Modifier) {
    Box(
        modifier
            .size(20.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(ArrColors.Seen),
        contentAlignment = Alignment.Center,
    ) {
        Text("VU", style = MaterialTheme.typography.labelSmall, color = ArrColors.Night)
    }
}

/** Pastille d'information (4K, Dolby Vision, Atmos…). */
@Composable
fun Badge(text: String, modifier: Modifier = Modifier, highlight: Boolean = false) {
    Box(
        modifier
            .clip(RoundedCornerShape(4.dp))
            .background(if (highlight) ArrColors.Accent.copy(alpha = 0.25f) else Color(0x33FFFFFF))
            .padding(horizontal = 6.dp, vertical = 2.dp)
    ) {
        Text(text, style = MaterialTheme.typography.labelSmall, color = if (highlight) ArrColors.AccentText else ArrColors.Text)
    }
}

/**
 * Bouton du skin : teinté au repos, bleu plein et texte sombre au focus,
 * zoom de 106 %.
 */
@Composable
fun ArrButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    primary: Boolean = false,
    leading: String? = null,
    compact: Boolean = false, // menu du haut : 11 entrées sur la largeur de l'écran
) {
    Surface(
        onClick = onClick,
        modifier = modifier.height(if (compact) 34.dp else 40.dp),
        shape = ClickableSurfaceDefaults.shape(ButtonShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.06f),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (primary) ArrColors.Accent.copy(alpha = 0.30f) else Color(0x26FFFFFF),
            contentColor = ArrColors.Text,
            focusedContainerColor = ArrColors.Accent,
            focusedContentColor = ArrColors.Night,
        ),
    ) {
        Row(
            Modifier.fillMaxHeight().padding(horizontal = if (compact) 11.dp else 18.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (leading != null) Text(leading, style = MaterialTheme.typography.labelLarge)
            Text(text, style = MaterialTheme.typography.labelLarge)
        }
    }
}

/** Titre de rangée + défilement horizontal (rangées de l'accueil). */
@Composable
fun <T> ContentRow(
    title: String,
    items: List<T>,
    modifier: Modifier = Modifier,
    key: (T) -> Any,
    itemContent: @Composable (T) -> Unit,
) {
    if (items.isEmpty()) return
    Column(modifier) {
        Text(
            title,
            style = MaterialTheme.typography.titleMedium,
            color = ArrColors.TextSecondary,
            modifier = Modifier.padding(start = 48.dp, bottom = 8.dp),
        )
        LazyRow(
            contentPadding = PaddingValues(horizontal = 48.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            items(items, key = key) { itemContent(it) }
        }
    }
}

/**
 * Fond d'écran : l'image de l'élément sélectionné, avec le lent zoom du skin
 * (« Ken Burns », 100 → 108 % en 26 s) et des voiles en dégradé pour que le
 * texte reste lisible par-dessus.
 */
@Composable
fun KenBurnsBackdrop(
    url: String?,
    modifier: Modifier = Modifier,
    video: (@Composable () -> Unit)? = null, // bande-annonce par-dessus l'image, sous les voiles
    content: @Composable BoxScope.() -> Unit = {},
) {
    val zoom = if (Motion.enabled) {
        val transition = rememberInfiniteTransition(label = "ken-burns")
        transition.animateFloat(
            initialValue = 1f,
            targetValue = 1.08f,
            animationSpec = infiniteRepeatable(tween(26_000, easing = LinearEasing), RepeatMode.Reverse),
            label = "zoom",
        ).value
    } else {
        1f
    }
    Box(modifier.fillMaxSize().background(ArrColors.Night)) {
        if (url != null) {
            AsyncImage(
                model = url,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize().graphicsLayer { scaleX = zoom; scaleY = zoom },
            )
        }
        video?.invoke()
        // Voile gauche (texte du héros) et voile bas (rangées)
        Box(Modifier.fillMaxSize().background(Brush.horizontalGradient(0f to Color(0xF20A0E16), 0.65f to Color(0x660A0E16), 1f to Color(0x1A0A0E16))))
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(0.35f to Color.Transparent, 1f to ArrColors.Night)))
        content()
    }
}

/**
 * Animations permanentes (zoom lent du fond). Coupées dans les tests de
 * captures d'écran : une animation sans fin empêcherait l'écran d'être
 * « au repos » au moment de la photo.
 */
object Motion {
    var enabled = true
}

/** Texte centré d'attente ou d'erreur, avec une action facultative. */
@Composable
fun MessageScreen(title: String, detail: String? = null, action: String? = null, onAction: () -> Unit = {}) {
    val actionFocus = remember { FocusRequester() }
    Column(
        Modifier.fillMaxSize().background(ArrColors.Night).padding(48.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(title, style = MaterialTheme.typography.headlineMedium)
        if (detail != null) {
            Text(detail, style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 8.dp))
        }
        if (action != null) {
            ArrButton(action, onAction, primary = true, modifier = Modifier.padding(top = 24.dp).focusRequester(actionFocus))
            // Focus d'office sur le bouton : la télécommande n'a rien d'autre à viser
            LaunchedEffect(action) { runCatching { actionFocus.requestFocus() } }
        }
    }
}

/**
 * Menu de choix (OK sur un élément) : titre, sous-titre facultatif, une
 * ligne de boutons par action, « Annuler » en dernier. Le premier choix a le
 * focus. Équivalent du `Dialog().select()` de l'add-on.
 */
@Composable
fun ChoiceDialog(
    title: String,
    choices: List<Pair<String, () -> Unit>>,
    onDismiss: () -> Unit,
    subtitle: String? = null,
) {
    val first = remember { FocusRequester() }
    androidx.compose.ui.window.Dialog(onDismissRequest = onDismiss) {
        Column(
            Modifier
                .width(420.dp)
                .background(ArrColors.CardDeep, RoundedCornerShape(16.dp))
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(title, style = MaterialTheme.typography.titleLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
            if (!subtitle.isNullOrBlank()) {
                Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary)
            }
            choices.forEachIndexed { index, (label, action) ->
                ArrButton(
                    label,
                    { onDismiss(); action() },
                    primary = index == 0,
                    modifier = Modifier.fillMaxWidth().then(if (index == 0) Modifier.focusRequester(first) else Modifier),
                )
            }
            ArrButton("Annuler", onDismiss, modifier = Modifier.fillMaxWidth().then(if (choices.isEmpty()) Modifier.focusRequester(first) else Modifier))
        }
    }
    LaunchedEffect(title) { runCatching { first.requestFocus() } }
}

/** En-tête d'un écran de la coquille : titre, ligne de résumé, boutons à droite. */
@Composable
fun ScreenHeader(title: String, summary: String?, modifier: Modifier = Modifier, actions: @Composable () -> Unit = {}) {
    Row(modifier.fillMaxWidth().padding(start = 48.dp, end = 48.dp, top = 28.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.headlineMedium)
            if (!summary.isNullOrBlank()) {
                Text(summary, style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { actions() }
    }
}

/**
 * Panneau cliquable (carte « Pour ce soir », ligne de la file, tuile) :
 * fond de carte, anneau bleu et léger zoom au focus, comme le skin.
 */
@Composable
fun FocusPanel(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onFocus: (Boolean) -> Unit = {},
    ring: Color = ArrColors.Accent,
    container: Color = ArrColors.CardDeep.copy(alpha = 0.92f),
    scale: Float = 1.03f,
    onLongClick: (() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    val shape = RoundedCornerShape(12.dp)
    Surface(
        onClick = onClick,
        onLongClick = onLongClick,
        modifier = modifier.onFocusChanged { onFocus(it.isFocused) },
        shape = ClickableSurfaceDefaults.shape(shape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = scale),
        border = ClickableSurfaceDefaults.border(
            border = Border(BorderStroke(1.dp, Color(0x14FFFFFF)), shape = shape),
            focusedBorder = Border(BorderStroke(2.dp, ring), shape = shape),
        ),
        glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(ring.copy(alpha = 0.45f), 12.dp)),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = container,
            contentColor = ArrColors.Text,
            focusedContainerColor = ArrColors.Card,
            focusedContentColor = ArrColors.Text,
        ),
        content = content,
    )
}

/** Petite pastille de couleur (état d'un téléchargement, étape, service). */
@Composable
fun Pill(text: String, color: Color, modifier: Modifier = Modifier, textColor: Color = ArrColors.Text) {
    Box(
        modifier
            .clip(RoundedCornerShape(50))
            .background(color)
            .padding(horizontal = 9.dp, vertical = 3.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = MaterialTheme.typography.labelSmall, color = textColor, maxLines = 1)
    }
}
