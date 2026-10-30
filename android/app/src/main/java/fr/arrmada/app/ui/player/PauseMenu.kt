package fr.arrmada.app.ui.player

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.focusGroup
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.focusRestorer
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.media3.common.C
import androidx.media3.common.Tracks
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.data.AmpDevice
import fr.arrmada.app.data.Chapter
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.Quality
import fr.arrmada.app.data.QualityOption
import fr.arrmada.app.data.SoundAdvisor
import fr.arrmada.app.data.SubtitleShiftLogic
import fr.arrmada.app.data.Trickplay
import fr.arrmada.app.data.TrickplayLogic
import fr.arrmada.app.ui.components.Badge
import fr.arrmada.app.ui.components.CardShape
import fr.arrmada.app.ui.components.Dim
import fr.arrmada.app.ui.components.Glass
import fr.arrmada.app.ui.components.GlassButton
import fr.arrmada.app.ui.components.GlassStrong
import fr.arrmada.app.ui.components.Ink
import fr.arrmada.app.ui.components.PauseScrim
import fr.arrmada.app.ui.components.PillShape
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.tapToClick
import fr.arrmada.app.ui.detail.techBadges
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.serialization.json.JsonPrimitive
import java.time.LocalTime
import java.time.format.DateTimeFormatter

/**
 * Bouton « Sous-titres FR » de l'onglet Sous-titres : Bazarr cherche, les
 * sous-titres trouvés s'ajoutent aux pistes. [note] : résultat de la dernière
 * recherche.
 */
data class SubtitleDownload(
    val busy: Boolean,
    val note: String?,
    val onClick: (() -> Unit)?, // « Sous-titres FR » (Bazarr) ; null : vidéo hors médiathèque
    val onSync: (() -> Unit)? = null, // « Resynchro auto » (Bazarr, ffsubsync)
    val onShift: ((Int) -> Unit)? = null, // −/+ 0,5 s sur la piste affichée
    val shiftMs: Int = 0, // décalage en cours
)

/**
 * Bouton « Qualité » (ADR-012) : Original, 1080p HDR, 1080p SDR. [current] :
 * qualité lue (cochée) ; [onSelect] recharge le flux à la même position.
 */
data class QualityChoice(
    val options: List<QualityOption>,
    val current: Quality,
    val onSelect: (Quality) -> Unit,
)

/** Onglets du menu pause ; le contenu suit l'onglet qui a le focus. */
private enum class PauseTab(val label: String) {
    CHAPTERS("Chapitres"), INFO("Infos"), CAST("Distribution"), SUBTITLES("Sous-titres")
}

// Palette « verre », boutons et voiles : ui/components/GlassStyle.kt (communs à toute l'appli)

/**
 * Menu pause « façon Apple TV » : l'image figée reste visible, assombrie
 * vers le bas. De haut en bas, tout en bas de l'écran :
 *  - le titre (logo) et l'épisode, avec les boutons à droite ;
 *  - la barre de lecture fine et blanche, repères de chapitres, temps
 *    écoulé, temps restant et heure de fin ;
 *  - les onglets (texte, pastille blanche au focus) ;
 *  - la rangée de l'onglet : chapitres en vignettes (image du chapitre,
 *    sinon l'aperçu « trickplay » de Jellyfin à cet instant), résumé,
 *    distribution, sous-titres.
 *
 * Télécommande : le focus part sur « Reprendre » ; ↓ descend vers les
 * onglets puis la rangée, ↑ remonte. En revenant sur une rangée, le focus
 * retrouve l'élément quitté (pas de saut d'onglet par géométrie).
 *
 * Limite assumée (ADR-007 § 4) : « les acteurs à l'écran à cet instant »
 * n'existent dans aucune source de données accessible ; l'onglet
 * Distribution montre la distribution principale.
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
fun PauseMenu(
    info: PlayInfo,
    meta: PlaybackMeta?,
    position: Long,
    duration: Long,
    tracks: Tracks,
    absolute: (String?) -> String?, // « /api/… » → adresse complète du serveur
    onResume: () -> Unit,
    onSeek: (seconds: Double) -> Unit,
    onSelectTrack: (type: Int, choice: TrackChoice?) -> Unit,
    initialTab: String? = null, // libellé de l'onglet affiché d'abord (tests)
    audio: AudioContext? = null, // pièce, son conseillé, décodage auto
    amp: AmpDevice? = null, // ampli de la pièce (null : pas d'ampli)
    onAmp: (action: String, value: JsonPrimitive) -> Unit = { _, _ -> },
    onAuto: (Boolean) -> Unit = {},
    onApplyAdvice: () -> Unit = {},
    audioOpen: Boolean = false, // écran Réglages audio ouvert d'emblée (tests)
    onQuit: () -> Unit = {}, // tactile : bouton « Quitter » (à la TV, c'est la touche Retour)
    onSkip: (seconds: Int) -> Unit = {}, // tactile : −10 s / +30 s
    subtitleDownload: SubtitleDownload? = null, // null : pas de recherche (vidéo hors médiathèque)
    quality: QualityChoice? = null, // null, ou original seul : pas de bouton « Qualité »
) {
    val screen = LocalScreen.current
    val touch = screen.isTouch
    val phone = screen.isPhone
    // Bouton « Audio » → écran Réglages audio par-dessus le menu ; Retour y revient
    var showAudio by remember { mutableStateOf(audioOpen) }
    var backFromAudio by remember { mutableStateOf(false) } // au retour, le focus revient sur « Audio »
    val audioFocus = remember { FocusRequester() }
    if (showAudio) {
        BackHandler { showAudio = false }
        AudioSettings(
            audio = audio ?: AudioContext("", false, SoundAdvisor.advise(null, null), false),
            tracks = tracks,
            amp = amp,
            onSelectTrack = { onSelectTrack(C.TRACK_TYPE_AUDIO, it) },
            onAmp = onAmp,
            onAuto = onAuto,
            onApplyAdvice = onApplyAdvice,
            onClose = { showAudio = false },
        )
        LaunchedEffect(Unit) { backFromAudio = true }
        return
    }

    val tabs = PauseTab.entries.filter { tab ->
        when (tab) {
            PauseTab.CHAPTERS -> info.chapters.isNotEmpty()
            PauseTab.CAST -> !meta?.cast.isNullOrEmpty()
            else -> true
        }
    }
    var tab by remember { mutableStateOf(tabs.firstOrNull { it.label == initialTab } ?: tabs.first()) }
    // Un « point d'accroche » par onglet : en descendant des boutons, le focus
    // arrive sur l'onglet affiché (et non sur le plus proche à l'écran)
    val tabFocus = remember { PauseTab.entries.associateWith { FocusRequester() } }
    // Bouton « Qualité » : son panneau remplace celui de l'onglet, jusqu'au prochain onglet visité
    var showQuality by remember { mutableStateOf(false) }
    val qualityChoice = quality?.takeIf { it.options.size > 1 }
    val resumeFocus = remember { FocusRequester() }
    val remaining = ((duration - position) / 1000).coerceAtLeast(0)
    val endsAt = LocalTime.now().plusSeconds(remaining).format(DateTimeFormatter.ofPattern("HH:mm"))
    val progress = if (duration > 0) (position.toFloat() / duration).coerceIn(0f, 1f) else 0f

    Box(
        Modifier
            .fillMaxSize()
            .background(PauseScrim) // haut à peine voilé, bas très sombre sous les rangées
    ) {
        // ── En haut à droite (TV) : rappel discret de la touche Retour ──
        if (!touch) {
            Text(
                "Retour pour quitter la lecture",
                style = MaterialTheme.typography.labelMedium,
                color = Dim,
                modifier = Modifier.align(Alignment.TopEnd).padding(end = gutter, top = 28.dp),
            )
        }

        Column(Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(bottom = if (phone) 12.dp else 26.dp)) {
            // ── Titre + boutons ──
            val buttons: @Composable () -> Unit = {
                Row(
                    Modifier
                        .focusRestorer { resumeFocus }
                        .focusGroup()
                        .then(if (touch) Modifier.horizontalScroll(rememberScrollState()) else Modifier),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (touch) GlassButton("10 s", onClick = { onSkip(-10) }, glyph = "↺")
                    GlassButton("Reprendre", onResume, glyph = "▶", primary = true, modifier = Modifier.focusRequester(resumeFocus))
                    if (touch) GlassButton("30 s", onClick = { onSkip(30) }, glyph = "↻")
                    GlassButton("Audio", { showAudio = true }, glyph = "♪", modifier = Modifier.focusRequester(audioFocus))
                    if (qualityChoice != null) GlassButton("Qualité", { showQuality = true }, glyph = "◐", selected = showQuality)
                    if (touch) GlassButton("Quitter", onQuit, glyph = "✕")
                }
            }
            if (phone) {
                // Téléphone : peu de largeur, les boutons passent sous le titre
                Column(Modifier.padding(horizontal = gutter)) {
                    TitleBlock(meta, info, absolute, compact = true)
                    Spacer(Modifier.height(8.dp))
                    buttons()
                }
            } else {
                Row(Modifier.fillMaxWidth().padding(horizontal = gutter), verticalAlignment = Alignment.Bottom) {
                    Box(Modifier.weight(1f)) { TitleBlock(meta, info, absolute, compact = false) }
                    Spacer(Modifier.width(24.dp))
                    buttons()
                }
            }

            // ── Barre de lecture : fine, blanche, repères de chapitres ──
            Column(Modifier.padding(horizontal = gutter).padding(top = if (phone) 10.dp else 18.dp)) {
                val total = duration / 1000.0
                val marks = remember(info.chapters, duration) {
                    if (total <= 0) emptyList() else info.chapters.map { (it.start / total).toFloat() }.filter { it > 0.005f && it < 0.995f }
                }
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(if (touch) 28.dp else 14.dp)
                        .then(
                            if (touch) {
                                // Au doigt : toucher la barre y saute
                                Modifier.pointerInput(duration) {
                                    detectTapGestures { offset ->
                                        if (duration > 0) onSeek(offset.x / size.width * duration / 1000.0)
                                    }
                                }
                            } else {
                                Modifier
                            }
                        ),
                    contentAlignment = Alignment.Center,
                ) {
                    Scrubber(progress, marks, Modifier.fillMaxWidth().height(if (touch) 6.dp else 5.dp))
                }
                Row(Modifier.fillMaxWidth().padding(top = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(formatClock(position / 1000), style = MaterialTheme.typography.labelLarge, color = Color.White)
                    Spacer(Modifier.weight(1f))
                    Text("Fin à $endsAt", style = MaterialTheme.typography.labelLarge, color = Dim)
                    Spacer(Modifier.width(14.dp))
                    Text("−" + formatClock(remaining), style = MaterialTheme.typography.labelLarge, color = Color.White)
                }
            }

            // ── Onglets ──
            Row(
                Modifier
                    .padding(horizontal = gutter)
                    .padding(top = if (phone) 8.dp else 14.dp)
                    .focusRestorer { tabFocus.getValue(tab) }
                    .focusGroup()
                    .then(if (touch) Modifier.horizontalScroll(rememberScrollState()) else Modifier),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                tabs.forEach { option ->
                    TabPill(
                        option.label,
                        selected = option == tab && !showQuality,
                        modifier = Modifier.focusRequester(tabFocus.getValue(option)),
                        onFocus = {
                            tab = option
                            showQuality = false
                        },
                    )
                }
            }

            // ── Contenu de l'onglet ──
            Box(Modifier.fillMaxWidth().height(if (phone) 112.dp else 158.dp).padding(top = if (phone) 6.dp else 12.dp)) {
                if (showQuality && qualityChoice != null) {
                    QualityPanel(qualityChoice)
                } else when (tab) {
                    PauseTab.CHAPTERS -> ChaptersPanel(info.chapters, info.trickplay, position, duration, absolute, onSeek)
                    PauseTab.INFO -> InfoPanel(meta, info)
                    PauseTab.CAST -> CastPanel(meta)
                    PauseTab.SUBTITLES -> TracksPanel(trackChoices(tracks, C.TRACK_TYPE_TEXT), allowOff = true, download = subtitleDownload) {
                        onSelectTrack(C.TRACK_TYPE_TEXT, it)
                    }
                }
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { (if (backFromAudio) audioFocus else resumeFocus).requestFocus() } }
}

/** Logo du titre (sinon son nom), puis l'épisode « S02E03 · Static ». */
@Composable
private fun TitleBlock(meta: PlaybackMeta?, info: PlayInfo, absolute: (String?) -> String?, compact: Boolean) {
    Column(Modifier.widthIn(max = 560.dp)) {
        val logo = absolute(meta?.logo)
        if (logo != null) {
            AsyncImage(
                model = logo,
                contentDescription = meta?.title,
                contentScale = ContentScale.Fit,
                alignment = Alignment.BottomStart,
                modifier = Modifier.heightIn(max = if (compact) 40.dp else 64.dp).widthIn(max = if (compact) 200.dp else 300.dp),
            )
        } else {
            Text(
                meta?.title ?: info.title.orEmpty(),
                style = if (compact) MaterialTheme.typography.titleLarge else MaterialTheme.typography.headlineMedium,
                color = Color.White,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        meta?.subtitle?.let {
            Text(
                it,
                style = MaterialTheme.typography.titleMedium,
                color = Dim,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 4.dp),
            )
        }
    }
}

/**
 * Barre de lecture tvOS : piste blanche translucide, partie lue blanche,
 * petits creux aux débuts de chapitres ([marks] : 0..1).
 */
@Composable
private fun Scrubber(progress: Float, marks: List<Float>, modifier: Modifier) {
    Canvas(modifier) {
        val radius = CornerRadius(size.height / 2, size.height / 2)
        drawRoundRect(Color(0x40FFFFFF), cornerRadius = radius)
        if (progress > 0f) drawRoundRect(Color.White, size = Size(size.width * progress, size.height), cornerRadius = radius)
        // Creux de 2 px : on « voit » les chapitres sans surcharger la barre
        val gap = 2.dp.toPx()
        marks.forEach { mark ->
            drawRect(Color(0xCC05080F), topLeft = Offset(size.width * mark - gap / 2, 0f), size = Size(gap, size.height))
        }
    }
}

/** Onglet texte : il s'active dès qu'il reçoit le focus (pas besoin de valider). */
@Composable
private fun TabPill(label: String, selected: Boolean, modifier: Modifier = Modifier, onFocus: () -> Unit) {
    Surface(
        onClick = onFocus,
        modifier = modifier.height(36.dp).onFocusChanged { if (it.isFocused) onFocus() }.tapToClick(onFocus),
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
        }
    }
}

/**
 * Chapitres en vignettes 16:9. Image du chapitre extraite par Jellyfin
 * si elle existe ; sinon (cas le plus courant : extraction désactivée
 * par défaut dans Jellyfin) l'aperçu « trickplay » à cet instant ; sinon
 * une carte sobre avec le numéro du chapitre.
 */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
private fun ChaptersPanel(
    chapters: List<Chapter>,
    trickplay: Trickplay?,
    position: Long,
    duration: Long,
    absolute: (String?) -> String?,
    onSeek: (Double) -> Unit,
) {
    val seconds = position / 1000.0
    val sorted = remember(chapters) { chapters.sortedBy { it.start } }
    val current = sorted.indexOfLast { it.start <= seconds }.coerceAtLeast(0)
    val listState = rememberLazyListState(initialFirstVisibleItemIndex = (current - 1).coerceAtLeast(0))
    val tiles = rememberTrickplayTiles(trickplay)
    // Téléphone : vignette plus petite, pour que le nom tienne sous la vignette
    val phone = LocalScreen.current.isPhone
    val thumbWidth = if (phone) 120.dp else 176.dp
    val thumbHeight = thumbWidth * 9 / 16
    LazyRow(
        state = listState,
        modifier = Modifier.focusRestorer(),
        contentPadding = PaddingValues(horizontal = gutter, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(if (phone) 12.dp else 18.dp),
    ) {
        items(sorted.size, key = { sorted[it].index }) { i ->
            val chapter = sorted[i]
            val next = sorted.getOrNull(i + 1)?.start
            val isCurrent = i == current
            // Avancement dans le chapitre en cours (petite barre bleue sous l'image)
            val end = next ?: (duration / 1000.0)
            val within = if (isCurrent && end > chapter.start) ((seconds - chapter.start) / (end - chapter.start)).toFloat().coerceIn(0f, 1f) else 0f
            Column(Modifier.width(thumbWidth)) {
                Surface(
                    onClick = { onSeek(chapter.start) },
                    modifier = Modifier.width(thumbWidth).height(thumbHeight).tapToClick({ onSeek(chapter.start) }),
                    shape = ClickableSurfaceDefaults.shape(CardShape),
                    scale = ClickableSurfaceDefaults.scale(focusedScale = 1.1f),
                    border = ClickableSurfaceDefaults.border(
                        focusedBorder = Border(BorderStroke(3.dp, Color.White), shape = CardShape),
                    ),
                    colors = ClickableSurfaceDefaults.colors(containerColor = ArrColors.Card, focusedContainerColor = ArrColors.Card),
                ) {
                    ChapterThumb(chapter, i + 1, trickplay, next, absolute, tiles)
                    if (isCurrent) {
                        Box(Modifier.align(Alignment.BottomStart).fillMaxWidth().height(4.dp).background(Color(0x66000000))) {
                            Box(Modifier.fillMaxHeight().fillMaxWidth(within).background(ArrColors.Accent))
                        }
                    }
                }
                Text(
                    chapter.name,
                    style = MaterialTheme.typography.labelLarge,
                    color = if (isCurrent) ArrColors.AccentText else Color.White,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 8.dp),
                )
                Text(formatClock(chapter.start.toLong()), style = MaterialTheme.typography.labelMedium, color = Dim)
            }
        }
    }
}

/** Image d'un chapitre : la sienne, l'aperçu trickplay, ou une carte numérotée. */
@Composable
private fun ChapterThumb(
    chapter: Chapter,
    number: Int,
    trickplay: Trickplay?,
    nextStart: Double?,
    absolute: (String?) -> String?,
    tiles: TrickplayTiles,
) {
    val url = absolute(chapter.image)
    var imageFailed by remember(url) { mutableStateOf(false) }
    Box(Modifier.fillMaxSize()) {
        // Fond : dégradé sombre et numéro du chapitre (visible tant que rien n'est chargé)
        Box(
            Modifier
                .fillMaxSize()
                .background(Brush.linearGradient(listOf(ArrColors.Card, ArrColors.CardDeep))),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                number.toString(),
                style = MaterialTheme.typography.displayMedium,
                color = Color(0x33FFFFFF),
            )
        }
        if (url != null && !imageFailed) {
            AsyncImage(
                model = url,
                contentDescription = chapter.name,
                contentScale = ContentScale.Crop,
                onError = { imageFailed = true }, // image annoncée mais introuvable : l'aperçu prend le relais
                modifier = Modifier.fillMaxSize(),
            )
        } else if (trickplay != null) {
            TrickplayImage(
                trickplay,
                TrickplayLogic.chapterPreviewAt(chapter.start, nextStart),
                absolute,
                tiles,
                Modifier.fillMaxSize(),
                crop = true,
            )
        }
    }
}

@Composable
private fun InfoPanel(meta: PlaybackMeta?, info: PlayInfo) {
    Column(Modifier.padding(horizontal = gutter).widthIn(max = 820.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            techBadges(meta?.file).forEach { Badge(it, highlight = true) }
            meta?.metaLine?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.labelLarge, color = Dim, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        Text(
            meta?.overview ?: info.overview.orEmpty(),
            style = MaterialTheme.typography.bodyLarge,
            color = Color.White,
            maxLines = 4,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}

@OptIn(ExperimentalComposeUiApi::class)
@Composable
private fun CastPanel(meta: PlaybackMeta?) {
    LazyRow(
        modifier = Modifier.focusRestorer(),
        contentPadding = PaddingValues(horizontal = gutter, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        items(meta?.cast.orEmpty().take(20)) { person ->
            Column(Modifier.width(96.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                // Focusable (sans action) : c'est ce qui fait défiler la rangée à la télécommande
                Surface(
                    onClick = {},
                    modifier = Modifier.size(78.dp),
                    shape = ClickableSurfaceDefaults.shape(CircleShape),
                    scale = ClickableSurfaceDefaults.scale(focusedScale = 1.1f),
                    border = ClickableSurfaceDefaults.border(focusedBorder = Border(BorderStroke(3.dp, Color.White), shape = CircleShape)),
                    colors = ClickableSurfaceDefaults.colors(containerColor = ArrColors.Card, focusedContainerColor = ArrColors.Card),
                ) {
                    if (person.photo != null) {
                        AsyncImage(model = person.photo, contentDescription = person.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize().clip(CircleShape))
                    } else {
                        // Pas de photo : initiales
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(initials(person.name), style = MaterialTheme.typography.titleLarge, color = Dim)
                        }
                    }
                }
                Text(person.name, style = MaterialTheme.typography.labelLarge, color = Color.White, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 8.dp))
                Text(person.character, style = MaterialTheme.typography.labelMedium, color = Dim, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
            }
        }
    }
}

/** « Timothée Chalamet » → « TC ». */
private fun initials(name: String): String =
    name.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }

@OptIn(ExperimentalComposeUiApi::class)
@Composable
internal fun TracksPanel(
    choices: List<TrackChoice>,
    allowOff: Boolean,
    sidePadding: Dp = gutter,
    download: SubtitleDownload? = null,
    onSelect: (TrackChoice?) -> Unit,
) {
    if (choices.isEmpty() && !allowOff) {
        Text("Aucune piste", style = MaterialTheme.typography.bodyLarge, color = Dim, modifier = Modifier.padding(horizontal = sidePadding))
        return
    }
    LazyRow(
        modifier = Modifier.focusRestorer(),
        contentPadding = PaddingValues(horizontal = sidePadding, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        // Outils en tête : visibles même quand le fichier n'a aucune piste
        if (download != null) {
            download.onClick?.let { onClick ->
                item {
                    OptionChip(
                        if (download.busy) "Bazarr…" else "⬇ Sous-titres FR",
                        download.note ?: if (download.busy) "Bazarr travaille (30 s à 1 min)" else "Chercher avec Bazarr",
                        selected = false,
                        supported = !download.busy,
                    ) { if (!download.busy) onClick() }
                }
            }
            download.onSync?.let { onSync ->
                item {
                    OptionChip("⟲ Resynchro auto", "Recaler sur le son (Bazarr)", selected = false, supported = !download.busy) {
                        if (!download.busy) onSync()
                    }
                }
            }
            download.onShift?.let { onShift ->
                val now = if (download.shiftMs == 0) "Pas de décalage" else "Décalage ${SubtitleShiftLogic.format(download.shiftMs)}"
                item {
                    OptionChip("− 0,5 s", "$now · plus tôt", selected = false, supported = true) {
                        onShift(-SubtitleShiftLogic.STEP_MS)
                    }
                }
                item {
                    OptionChip("+ 0,5 s", "$now · plus tard", selected = false, supported = true) {
                        onShift(SubtitleShiftLogic.STEP_MS)
                    }
                }
            }
        }
        if (allowOff) {
            item {
                OptionChip("Aucun", "Sous-titres désactivés", selected = choices.none { it.selected }, supported = true) { onSelect(null) }
            }
        }
        items(choices) { choice ->
            OptionChip(
                choice.label,
                if (choice.supported) choice.detail else (choice.detail + " · non lisible ici").trimStart(' ', '·'),
                selected = choice.selected,
                supported = choice.supported,
            ) { if (choice.supported) onSelect(choice) }
        }
    }
}

/** Panneau du bouton « Qualité » : la qualité lue est cochée, l'indisponible grisée. */
@OptIn(ExperimentalComposeUiApi::class)
@Composable
private fun QualityPanel(choice: QualityChoice) {
    LazyRow(
        modifier = Modifier.focusRestorer(),
        contentPadding = PaddingValues(horizontal = gutter, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        items(choice.options, key = { it.quality }) { option ->
            OptionChip(
                option.title,
                option.detail,
                selected = option.quality == choice.current,
                supported = option.available,
            ) { if (option.available) choice.onSelect(option.quality) }
        }
    }
}

/** Carte de choix « verre » : coche ✓ sur le choix en cours, blanche au focus. */
@Composable
private fun OptionChip(title: String, detail: String, selected: Boolean, supported: Boolean, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = Modifier.width(230.dp).height(66.dp).tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(CardShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.06f),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) GlassStrong else Glass,
            contentColor = if (supported) Color.White else Color(0x66FFFFFF),
            focusedContainerColor = Color.White,
            focusedContentColor = Ink,
        ),
    ) {
        Row(Modifier.fillMaxSize().padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(detail, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            if (selected) {
                Spacer(Modifier.width(8.dp))
                Text("✓", style = MaterialTheme.typography.titleLarge, color = ArrColors.AccentText)
            }
        }
    }
}
