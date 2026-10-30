package fr.arrmada.app.ui.components

import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
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
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.Glow
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import android.graphics.drawable.Drawable
import androidx.core.graphics.drawable.toBitmap
import coil.compose.AsyncImage
import coil.request.ImageRequest
import fr.arrmada.app.data.MenuKeyLogic
import fr.arrmada.app.data.PosterColorLogic
import fr.arrmada.app.ui.theme.ArrColors

/*
 * Briques d'interface communes, au style « verre » du lecteur (GlassStyle.kt).
 * Une seule règle avec la télécommande, dans toute l'appli :
 *  - focus = blanc : pastille blanche à texte sombre pour un bouton, contour
 *    blanc de 3 dp pour une image, avec un léger zoom (105 %) ;
 *  - bleu = « en cours » : progression, réglage coché, élément actif.
 * Il faut toujours voir où l'on est, et le bleu ne veut dire qu'une chose.
 */

/** Contour blanc d'une image au focus (affiche, vignette, panneau). */
private val FocusRing = BorderStroke(3.dp, Color.White)

/** Halo discret autour d'une image au focus : la décolle du fond sans colorer. */
private val FocusGlow = Glow(Color.White.copy(alpha = 0.22f), 10.dp)

/**
 * Halo d'une carte au focus : la teinte vive de son affiche quand elle en a
 * une (voir [PosterGlow]), sinon le halo blanc discret.
 */
internal fun focusGlow(tint: Color?): Glow = if (tint != null) Glow(tint.copy(alpha = 0.6f), 16.dp) else FocusGlow

/**
 * Couleur de halo de chaque affiche, gardée en mémoire : une affiche n'est
 * analysée qu'une fois, même en faisant défiler la rangée dans tous les sens
 * (comme un cache, limité aux 400 dernières).
 */
object PosterGlow {
    private const val NO_COLOR = 0 // affiche sans teinte nette (jamais renvoyé par l'analyse : alpha 0)

    private val cache = object : LinkedHashMap<String, Int>(64, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Int>?): Boolean = size > 400
    }

    /** Couleur déjà connue de cette affiche (null : sans teinte, ou pas encore analysée). */
    @Synchronized
    fun cached(url: String?): Color? = url?.let { cache[it] }?.takeIf { it != NO_COLOR }?.let { Color(it) }

    /** Analyse l'image chargée (réduite à 6 × 9 pixels) et retient le résultat. */
    @Synchronized
    fun learn(url: String, image: Drawable): Color? {
        cache[url]?.let { return it.takeIf { c -> c != NO_COLOR }?.let { c -> Color(c) } }
        val argb = runCatching {
            val small = image.toBitmap(6, 9)
            val pixels = IntArray(6 * 9)
            small.getPixels(pixels, 0, 6, 0, 0, 6, 9)
            PosterColorLogic.accent(pixels)
        }.getOrNull()
        cache[url] = argb ?: NO_COLOR
        return argb?.let { Color(it) }
    }
}

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
    onLongClick: (() -> Unit)? = null, // appui long (OK maintenu) : menu du titre
    tag: String? = null, // étiquette en haut à gauche (« Hier », « Il y a 3 j »…)
) {
    var tint by remember(imageUrl) { mutableStateOf(PosterGlow.cached(imageUrl)) }
    Column(modifier.width(width)) {
        Surface(
            onClick = onClick,
            onLongClick = onLongClick,
            modifier = Modifier
                .width(width)
                .height(width * 1.5f)
                .tapToClick(onClick, onLongClick)
                .onFocusChanged { if (it.isFocused) onFocus() },
            shape = ClickableSurfaceDefaults.shape(CardShape),
            scale = ClickableSurfaceDefaults.scale(focusedScale = 1.05f),
            border = ClickableSurfaceDefaults.border(focusedBorder = Border(FocusRing, shape = CardShape)),
            glow = ClickableSurfaceDefaults.glow(focusedGlow = focusGlow(tint)),
            colors = ClickableSurfaceDefaults.colors(
                containerColor = ArrColors.Card,
                focusedContainerColor = ArrColors.Card,
            ),
        ) {
            ArtImage(imageUrl, title, Modifier.fillMaxSize(), onColor = { tint = it })
            if (tag != null) CardTag(tag, Modifier.align(Alignment.TopStart).padding(6.dp))
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
    onLongClick: (() -> Unit)? = null, // appui long (OK maintenu) : menu du titre
) {
    var tint by remember(imageUrl) { mutableStateOf(PosterGlow.cached(imageUrl)) }
    Column(modifier.width(width)) {
        Surface(
            onClick = onClick,
            onLongClick = onLongClick,
            modifier = Modifier
                .width(width)
                .height(width * 9f / 16f)
                .tapToClick(onClick, onLongClick)
                .onFocusChanged { if (it.isFocused) onFocus() },
            shape = ClickableSurfaceDefaults.shape(CardShape),
            scale = ClickableSurfaceDefaults.scale(focusedScale = 1.05f),
            border = ClickableSurfaceDefaults.border(focusedBorder = Border(FocusRing, shape = CardShape)),
            glow = ClickableSurfaceDefaults.glow(focusedGlow = focusGlow(tint)),
            colors = ClickableSurfaceDefaults.colors(
                containerColor = ArrColors.Card,
                focusedContainerColor = ArrColors.Card,
            ),
        ) {
            ArtImage(imageUrl, title, Modifier.fillMaxSize(), onColor = { tint = it })
            // Voile bas pour lire le titre sur l'image
            Box(
                Modifier
                    .fillMaxSize()
                    .background(Brush.verticalGradient(0.45f to Color.Transparent, 1f to Color(0xE6050810)))
            )
            Column(Modifier.align(Alignment.BottomStart).padding(8.dp)) {
                Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (!subtitle.isNullOrBlank()) {
                    Text(subtitle, style = MaterialTheme.typography.labelMedium, color = Dim, maxLines = 1)
                }
                if (progress != null && progress > 0f) {
                    ProgressBar(progress, Modifier.fillMaxWidth().padding(top = 5.dp))
                }
            }
        }
    }
}

/**
 * Image distante ; fond de carte uni tant qu'elle charge ou si elle manque.
 * [onColor] : reçoit la teinte de l'image une fois chargée (halo des cartes) ;
 * l'image est alors gardée lisible par l'appli (pas en mémoire graphique seule).
 */
@Composable
fun ArtImage(
    url: String?,
    description: String,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Crop,
    onColor: ((Color?) -> Unit)? = null,
) {
    Box(modifier.background(ArrColors.Card)) {
        if (url != null && onColor != null) {
            val context = LocalContext.current
            val request = remember(url) { ImageRequest.Builder(context).data(url).allowHardware(false).build() }
            AsyncImage(
                model = request,
                contentDescription = description,
                contentScale = contentScale,
                modifier = Modifier.fillMaxSize(),
                onSuccess = { state -> onColor(PosterGlow.learn(url, state.result.drawable)) },
            )
        } else if (url != null) {
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

/** Barre de progression : piste blanche 12 %, remplissage bleu (« en cours »), comme dans le lecteur. */
@Composable
fun ProgressBar(progress: Float, modifier: Modifier = Modifier, height: Dp = 3.dp) {
    Box(modifier.height(height).clip(RoundedCornerShape(height)).background(ArrColors.Track)) {
        Box(
            Modifier
                .fillMaxHeight()
                .fillMaxWidth(progress.coerceIn(0f, 1f))
                .background(ArrColors.Accent)
        )
    }
}

/** Étiquette d'une carte : pastille sombre et translucide, lisible sur n'importe quelle affiche. */
@Composable
fun CardTag(text: String, modifier: Modifier = Modifier) {
    Box(
        modifier
            .clip(PillShape)
            .background(Color(0xB3050810))
            .padding(horizontal = 7.dp, vertical = 2.dp)
    ) {
        Text(text, style = MaterialTheme.typography.labelSmall, color = Color.White, maxLines = 1)
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

/**
 * Pastille d'information (4K, Dolby Vision, Atmos…) en verre. `highlight` =
 * information technique du fichier : liseré blanc en plus (plus de bleu ici,
 * le bleu est réservé à ce qui est « en cours »).
 */
@Composable
fun Badge(text: String, modifier: Modifier = Modifier, highlight: Boolean = false) {
    Box(
        modifier
            .clip(PillShape)
            .background(Glass)
            .then(if (highlight) Modifier.border(1.dp, GlassEdge, PillShape) else Modifier)
            .padding(horizontal = 8.dp, vertical = 2.dp)
    ) {
        Text(text, style = MaterialTheme.typography.labelSmall, color = Color.White, maxLines = 1)
    }
}

/**
 * Bouton pastille de toute l'appli (et du lecteur, via GlassButton) : verre
 * au repos, plus clair pour l'action principale, blanc à texte sombre au
 * focus, zoom de 108 %.
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
        modifier = modifier.height(if (compact) 34.dp else 42.dp).tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(PillShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.08f),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (primary) GlassStrong else Glass,
            contentColor = Color.White,
            focusedContainerColor = Color.White,
            focusedContentColor = Ink,
            pressedContainerColor = Pressed,
            pressedContentColor = Ink,
        ),
    ) {
        Row(
            Modifier.fillMaxHeight().padding(horizontal = if (compact) 13.dp else 18.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (leading != null) Text(leading, style = MaterialTheme.typography.titleMedium)
            Text(text, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis)
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
            color = Dim,
            modifier = Modifier.padding(start = gutter, bottom = 8.dp),
        )
        LazyRow(
            contentPadding = PaddingValues(horizontal = gutter, vertical = 10.dp),
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
        Modifier.fillMaxSize().background(ArrColors.Night).padding(gutter),
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
 * À poser sur le contenu d'un menu qu'un appui long peut ouvrir : ignore la
 * fin de l'appui sur OK qui l'a ouvert, sinon le relâchement validait le
 * choix qui a le focus (voir [MenuKeyLogic.Gate]). Un nouvel appui sur OK
 * marche normalement ; sans effet au doigt.
 */
@Composable
fun Modifier.ignoreHeldOk(): Modifier {
    val gate = remember { MenuKeyLogic.Gate() }
    return this.onPreviewKeyEvent { event ->
        val key = event.nativeKeyEvent
        gate.blocks(key.keyCode, key.action, key.repeatCount)
    }
}

/**
 * Menu de choix (OK sur un élément) : titre, sous-titre facultatif, une
 * ligne de boutons par action, « Annuler » en dernier. Le premier choix a le
 * focus. Équivalent du `Dialog().select()` de l'add-on. Panneau sombre aux
 * coins arrondis et liseré discret, comme les sections du lecteur.
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
                .widthIn(max = 420.dp)
                .fillMaxWidth()
                .background(ArrColors.CardDeep, PanelShape)
                .border(1.dp, Color(0x14FFFFFF), PanelShape)
                .padding(24.dp)
                .ignoreHeldOk(), // ouvert à l'appui long : le relâchement de OK ne valide rien
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
    if (LocalScreen.current.isPhone) {
        // Téléphone : les boutons passent sous le titre
        Column(modifier.fillMaxWidth().padding(start = gutter, end = gutter, top = 20.dp)) {
            Text(title, style = MaterialTheme.typography.headlineMedium)
            if (!summary.isNullOrBlank()) {
                Text(summary, style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary, maxLines = 2, overflow = TextOverflow.Ellipsis)
            }
            Row(Modifier.padding(top = 10.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) { actions() }
        }
        return
    }
    Row(modifier.fillMaxWidth().padding(start = gutter, end = gutter, top = 28.dp), verticalAlignment = Alignment.CenterVertically) {
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
 * fond de carte, contour blanc et léger zoom au focus. `ring` ne change que
 * pour signaler un état (vert « prêt », rouge « bloqué »).
 */
@Composable
fun FocusPanel(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    onFocus: (Boolean) -> Unit = {},
    ring: Color = Color.White,
    container: Color = ArrColors.CardDeep.copy(alpha = 0.92f),
    scale: Float = 1.03f,
    onLongClick: (() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    Surface(
        onClick = onClick,
        onLongClick = onLongClick,
        modifier = modifier.onFocusChanged { onFocus(it.isFocused) }.tapToClick(onClick, onLongClick),
        shape = ClickableSurfaceDefaults.shape(CardShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = scale),
        border = ClickableSurfaceDefaults.border(
            border = Border(BorderStroke(1.dp, Color(0x14FFFFFF)), shape = CardShape),
            focusedBorder = Border(BorderStroke(3.dp, ring), shape = CardShape),
        ),
        glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(ring.copy(alpha = 0.25f), 10.dp)),
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
            .clip(PillShape)
            .background(color)
            .padding(horizontal = 9.dp, vertical = 3.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(text, style = MaterialTheme.typography.labelSmall, color = textColor, maxLines = 1)
    }
}
