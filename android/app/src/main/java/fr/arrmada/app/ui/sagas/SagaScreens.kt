package fr.arrmada.app.ui.sagas

import android.provider.Settings
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.zIndex
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.Saga
import fr.arrmada.app.data.SagaFilm
import fr.arrmada.app.data.SagaList
import fr.arrmada.app.data.SagaRules
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.ChoiceDialog
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.Motion
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.components.PosterGlow
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.tapToClick
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.abs

/*
 * Sagas de films sur la TV (ADR-016).
 *
 * - [SagaGrid] : la vue « Sagas » de l'écran Films (à côté de Récents, A à Z,
 *   Année, 4K). Au focus, les trois affiches d'une saga s'ouvrent en
 *   éventail et le fond prend la couleur de la saga.
 * - [SagaScreen] : une saga. À l'ouverture, l'éventail se referme en pochette
 *   et les films « se distribuent » un par un dans l'ordre de sortie, comme
 *   des cartes ; au Retour, ils se rangent avant de quitter l'écran.
 *
 * Animations courtes (moins d'une demi-seconde) et coupées quand la TV
 * demande de supprimer les animations (accessibilité) : voir [rememberMotion].
 */

private val CardCorner = RoundedCornerShape(12.dp)

/**
 * Animations permises ? Non dans les tests de captures d'écran ([Motion]) ni
 * quand l'échelle des animations d'Android est à 0 (option d'accessibilité
 * « Supprimer les animations », ou réglage développeur).
 */
@Composable
fun rememberMotion(): Boolean {
    val context = LocalContext.current
    return remember {
        Motion.enabled && runCatching {
            Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
        }.getOrDefault(1f) > 0f
    }
}

/** Interpolation linéaire (éventail fermé → ouvert). */
private fun lerp(from: Float, to: Float, t: Float): Float = from + (to - from) * t

/** Toujours trois affiches : une saga de deux films répète la première derrière. */
private fun threePosters(s: Saga): List<String?> {
    val p = s.posters.ifEmpty { listOfNotNull(s.poster) }
    return when {
        p.size >= 3 -> p.take(3)
        p.size == 2 -> listOf(p[1], p[0], p[1])
        p.size == 1 -> listOf(p[0], p[0], p[0])
        else -> listOf(null, null, null)
    }
}

/**
 * Pile de trois affiches. [spread] : 0 = pile serrée, 1 = éventail ouvert.
 * Dessinées hors du cadre de la carte (rotation), sans rognage.
 */
@Composable
private fun PosterFan(
    posters: List<String?>,
    title: String,
    spread: Float,
    focused: Boolean,
    modifier: Modifier = Modifier,
    onColor: (Color?) -> Unit = {},
) {
    Box(modifier) {
        // Gauche et droite d'abord (derrière), le centre par-dessus
        listOf(0, 2, 1).forEach { i ->
            val side = (i - 1).toFloat() // -1 gauche, 0 centre, 1 droite
            Box(
                Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 6.dp)
                    .fillMaxWidth(0.6f)
                    .aspectRatio(2f / 3f)
                    .graphicsLayer {
                        rotationZ = side * lerp(4f, 13f, spread)
                        translationX = side * size.width * lerp(0.12f, 0.52f, spread)
                        translationY = abs(side) * size.height * 0.05f * spread - (1f - abs(side)) * size.height * 0.03f * spread
                    }
                    .clip(CardCorner)
                    .then(if (i == 1 && focused) Modifier.border(BorderStroke(3.dp, Color.White), CardCorner) else Modifier),
            ) {
                ArtImage(posters[i], if (i == 1) title else "", Modifier.fillMaxSize(), onColor = if (i == 1) onColor else null)
            }
        }
    }
}

/** Barre « sur le NAS » : bleu en cours, vert quand la saga est complète. */
@Composable
private fun SagaBar(progress: Float, modifier: Modifier = Modifier) {
    Box(modifier.height(4.dp).clip(RoundedCornerShape(4.dp)).background(Color(0x1FFFFFFF))) {
        Box(
            Modifier
                .fillMaxWidth(progress.coerceIn(0f, 1f))
                .height(4.dp)
                .background(if (progress >= 1f) ArrColors.Seen else ArrColors.Accent),
        )
    }
}

/** Fond teinté de la couleur de la saga au focus (halo des affiches). */
private fun Modifier.sagaTint(color: Color): Modifier = drawBehind {
    drawRect(
        Brush.radialGradient(
            listOf(color.copy(alpha = color.alpha * 0.42f), Color.Transparent),
            center = Offset(size.width * 0.72f, size.height * 0.12f),
            radius = size.width * 0.7f,
        ),
    )
}

// ─────────────────────────────────────────────────────────────────────
// Vue « Sagas » de l'écran Films
// ─────────────────────────────────────────────────────────────────────

/**
 * Grille des sagas. [onOpen] ouvre une saga ; au retour, le focus revient
 * sur [focusedId], la saga d'où l'on vient (gardée par l'écran Films).
 */
@Composable
fun SagaGrid(repository: Repository, onOpen: (Saga) -> Unit, focusedId: Int = -1, onFocused: (Int) -> Unit = {}) {
    var list by remember { mutableStateOf<SagaList?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var tint by remember { mutableStateOf<Color?>(null) }
    val motion = rememberMotion()
    val restore = remember { FocusRequester() }
    val background by animateColorAsState(
        tint ?: ArrColors.Accent.copy(alpha = 0.4f),
        animationSpec = if (motion) tween(600) else snap(),
        label = "teinte-saga",
    )

    LaunchedEffect(Unit) {
        runCatching { repository.sagas() }
            .onSuccess { list = it; error = null }
            .onFailure { error = it.message ?: "Radarr ne répond pas" }
    }

    val current = list
    when {
        current == null && error != null -> MessageScreen("Sagas indisponibles", error)
        current == null -> MessageScreen("Chargement des sagas…")
        current.sagas.isEmpty() -> MessageScreen("Aucune saga pour l'instant", "Une saga apparaît dès qu'un de ses films est dans Radarr.")
        else -> {
            val target = current.sagas.indexOfFirst { it.id == focusedId }.takeIf { it >= 0 } ?: 0
            Box(Modifier.fillMaxSize().sagaTint(background)) {
                LazyVerticalGrid(
                    columns = GridCells.Fixed(6),
                    contentPadding = PaddingValues(start = gutter, end = gutter, top = 22.dp, bottom = 32.dp),
                    horizontalArrangement = Arrangement.spacedBy(26.dp),
                    verticalArrangement = Arrangement.spacedBy(30.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    itemsIndexed(current.sagas, key = { _, s -> s.id }) { index, saga ->
                        SagaCard(
                            saga = saga,
                            motion = motion,
                            onClick = { onOpen(saga) },
                            onFocus = { color -> onFocused(saga.id); tint = color },
                            modifier = if (index == target) Modifier.focusRequester(restore) else Modifier,
                        )
                    }
                }
            }
            LaunchedEffect(current) { runCatching { restore.requestFocus() } }
        }
    }
}

@Composable
private fun SagaCard(
    saga: Saga,
    motion: Boolean,
    onClick: () -> Unit,
    onFocus: (Color?) -> Unit,
    modifier: Modifier = Modifier,
) {
    val posters = remember(saga) { threePosters(saga) }
    var focused by remember { mutableStateOf(false) }
    var color by remember(saga) { mutableStateOf(PosterGlow.cached(posters[1])) }
    val spread by animateFloatAsState(
        if (focused) 1f else 0f,
        animationSpec = if (motion) tween(320, easing = FastOutSlowInEasing) else snap(),
        label = "eventail",
    )
    // La carte ouverte passe devant ses voisines (l'éventail les déborde)
    Column(modifier.zIndex(if (focused) 1f else 0f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.fillMaxWidth().aspectRatio(1f / 1.05f)) {
            PosterFan(
                posters, saga.title, spread, focused,
                Modifier.fillMaxSize().graphicsLayer { val s = lerp(1f, 1.07f, spread); scaleX = s; scaleY = s },
                onColor = { c -> color = c; if (focused) onFocus(c) },
            )
            // Surface transparente par-dessus : elle porte le focus et OK
            Surface(
                onClick = onClick,
                modifier = Modifier
                    .matchParentSize()
                    .onFocusChanged { if (it.isFocused != focused) { focused = it.isFocused; if (it.isFocused) onFocus(color) } }
                    .tapToClick(onClick),
                shape = ClickableSurfaceDefaults.shape(CardCorner),
                scale = ClickableSurfaceDefaults.scale(focusedScale = 1f),
                colors = ClickableSurfaceDefaults.colors(
                    containerColor = Color.Transparent,
                    focusedContainerColor = Color.Transparent,
                    pressedContainerColor = Color.Transparent,
                ),
            ) {}
        }
        Text(saga.title, style = MaterialTheme.typography.titleSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
        SagaBar(SagaRules.progress(saga), Modifier.fillMaxWidth())
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("${saga.available}/${saga.total} films", style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary)
            Text(
                SagaRules.badge(saga),
                style = MaterialTheme.typography.labelSmall,
                color = when {
                    saga.missing > 0 -> ArrColors.Accent
                    saga.upcoming > 0 -> ArrColors.Warning
                    else -> ArrColors.Seen
                },
                maxLines = 1,
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────
// Écran d'une saga
// ─────────────────────────────────────────────────────────────────────

/**
 * Une saga : pochette (éventail refermé), titre, ce qui est sur le NAS,
 * « Compléter la saga », puis les films distribués dans l'ordre de sortie.
 * OK sur un film du NAS ouvre sa fiche ; sur un film manquant, propose de
 * l'ajouter à Radarr.
 */
@Composable
fun SagaScreen(
    repository: Repository,
    id: Int,
    onMovie: (SagaFilm) -> Unit,
    onBack: () -> Unit,
    onPlay: (SagaFilm) -> Unit = onMovie, // « Reprendre la saga » : lance le prochain film
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val motion = rememberMotion()
    var saga by remember { mutableStateOf<Saga?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableStateOf(0) }
    var dealt by remember { mutableStateOf(false) } // films distribués (vrai) ou rangés dans la pile (faux)
    var leaving by remember { mutableStateOf(false) }
    var askComplete by remember { mutableStateOf(false) }
    var askFilm by remember { mutableStateOf<SagaFilm?>(null) }
    val first = remember { FocusRequester() }

    LaunchedEffect(id, reload) {
        runCatching { repository.saga(id) }
            .onSuccess { saga = it; error = null }
            .onFailure { error = it.message ?: "Radarr ne répond pas" }
    }

    fun follow(on: Boolean) {
        scope.launch {
            runCatching { repository.sagaFollow(id, on) }
                .onSuccess { Toast.makeText(context, it.message, Toast.LENGTH_LONG).show(); reload++ }
                .onFailure { Toast.makeText(context, it.message ?: "Radarr ne répond pas", Toast.LENGTH_LONG).show() }
        }
    }

    fun complete(tmdbIds: List<Long>?) {
        scope.launch {
            runCatching { repository.sagaComplete(id, tmdbIds) }
                .onSuccess { Toast.makeText(context, it.message, Toast.LENGTH_LONG).show(); reload++ }
                .onFailure { Toast.makeText(context, it.message ?: "Radarr ne répond pas", Toast.LENGTH_LONG).show() }
        }
    }

    // Retour : les films se rangent dans la pile, puis on quitte l'écran
    BackHandler(enabled = !leaving) { leaving = true }
    LaunchedEffect(leaving) {
        if (leaving) {
            dealt = false
            if (motion) delay(380)
            onBack()
        }
    }

    val current = saga
    when {
        current == null && error != null -> MessageScreen("Saga indisponible", error, "Réessayer") { reload++ }
        current == null -> MessageScreen("Chargement de la saga…")
        else -> {
            val posters = remember(current) { threePosters(current) }
            val tint = remember(current) { PosterGlow.cached(posters[1]) ?: ArrColors.Accent.copy(alpha = 0.4f) }
            // Éventail ouvert à l'arrivée (comme sur la grille), refermé en pochette
            val spread by animateFloatAsState(
                if (dealt) 0.15f else 1f,
                animationSpec = if (motion) tween(500, easing = FastOutSlowInEasing) else snap(),
                label = "pochette",
            )
            val progress by animateFloatAsState(
                if (dealt) SagaRules.progress(current) else 0f,
                animationSpec = if (motion) tween(700, delayMillis = 250, easing = FastOutSlowInEasing) else snap(),
                label = "progression",
            )
            Column(Modifier.fillMaxSize().background(ArrColors.Night).sagaTint(tint).padding(top = 24.dp)) {
                Text("Films › Sagas", style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(horizontal = gutter))
                Row(
                    Modifier.padding(horizontal = gutter).padding(top = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(28.dp),
                    verticalAlignment = Alignment.Bottom,
                ) {
                    PosterFan(posters, current.title, spread, focused = false, Modifier.width(150.dp).aspectRatio(1f / 1.05f))
                    Column(Modifier.widthIn(max = 640.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(current.title, style = MaterialTheme.typography.displayMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(SagaRules.facts(current), style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
                        SagaBar(progress, Modifier.width(320.dp))
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(top = 6.dp)) {
                            // Prochain film à voir (vu partagé des TV) : le premier bouton
                            val next = current.next
                            val nextLabel = SagaRules.nextLabel(current)
                            if (next != null && nextLabel != null) {
                                ArrButton(nextLabel, { onPlay(next) }, leading = "▶", primary = true, modifier = Modifier.focusRequester(first))
                            }
                            if (current.missing > 0) {
                                ArrButton(
                                    "Compléter la saga (${current.missing})",
                                    { askComplete = true },
                                    leading = "+",
                                    modifier = if (next == null) Modifier.focusRequester(first) else Modifier,
                                )
                            } else if (next == null) {
                                Text(SagaRules.badge(current), style = MaterialTheme.typography.titleSmall, color = if (current.upcoming > 0) ArrColors.Warning else ArrColors.Seen)
                            }
                            // Suivre : Radarr ajoutera seul les prochains films de la saga
                            ArrButton(
                                if (current.monitored) "Suivie ✓" else "Suivre les nouveaux films",
                                { follow(!current.monitored) },
                                leading = if (current.monitored) null else "☆",
                            )
                        }
                    }
                }
                LazyRow(
                    contentPadding = PaddingValues(horizontal = gutter, vertical = 24.dp),
                    horizontalArrangement = Arrangement.spacedBy(18.dp),
                ) {
                    itemsIndexed(current.films, key = { _, f -> f.tmdbId }) { index, film ->
                        // Distribution : chaque film part de la pochette, l'un après l'autre
                        val p by animateFloatAsState(
                            if (dealt) 1f else 0f,
                            animationSpec = if (motion) {
                                tween(520, delayMillis = if (dealt) 120 + index * 70 else (current.films.size - index) * 35, easing = FastOutSlowInEasing)
                            } else {
                                snap()
                            },
                            label = "distribution",
                        )
                        Column(
                            Modifier.graphicsLayer {
                                alpha = p
                                translationX = (1f - p) * -(220f + index * 150f)
                                translationY = (1f - p) * -260f
                                rotationZ = (1f - p) * -14f
                                val s = lerp(0.6f, 1f, p)
                                scaleX = s; scaleY = s
                            },
                            verticalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Text(SagaRules.position(index, film), style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary)
                            PosterCard(
                                imageUrl = film.poster,
                                title = film.title,
                                width = 128.dp,
                                tag = SagaRules.tag(film),
                                dimmed = SagaRules.dimmed(film),
                                seen = film.watched,
                                progress = film.progress?.let { it / 100f },
                                onClick = {
                                    when (film.state) {
                                        "available", "wanted" -> onMovie(film)
                                        "missing" -> askFilm = film
                                        "upcoming" -> Toast.makeText(context, "Pas encore sorti : rien à télécharger pour l'instant", Toast.LENGTH_SHORT).show()
                                        else -> Toast.makeText(context, "Film écarté dans Radarr (liste d'exclusions)", Toast.LENGTH_SHORT).show()
                                    }
                                },
                                modifier = if (current.missing == 0 && current.next == null && index == 0) Modifier.focusRequester(first) else Modifier,
                            )
                            Text(film.title, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.width(128.dp))
                        }
                    }
                }
            }
            LaunchedEffect(current) {
                dealt = true
                runCatching { first.requestFocus() }
            }
        }
    }

    if (askComplete) {
        val s = saga
        val missing = s?.films?.filter { it.state == "missing" }.orEmpty()
        ChoiceDialog(
            title = "Compléter la saga",
            subtitle = missing.joinToString(", ") { it.title },
            choices = listOf("Ajouter ${if (missing.size > 1) "les ${missing.size} films" else "le film"} à Radarr" to { complete(null) }),
            onDismiss = { askComplete = false },
        )
    }
    askFilm?.let { film ->
        ChoiceDialog(
            title = film.title,
            subtitle = "Pas sur le NAS : Radarr l'ajoute et le cherche tout de suite.",
            choices = listOf("Ajouter à Radarr" to { complete(listOf(film.tmdbId)) }),
            onDismiss = { askFilm = null },
        )
    }
}
