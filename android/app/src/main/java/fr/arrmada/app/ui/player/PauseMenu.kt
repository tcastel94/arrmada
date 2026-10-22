package fr.arrmada.app.ui.player

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.tapToClick
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
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
import kotlinx.serialization.json.JsonPrimitive
import fr.arrmada.app.data.AmpDevice
import fr.arrmada.app.data.SoundAdvisor
import fr.arrmada.app.data.Chapter
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.Badge
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.detail.techBadges
import fr.arrmada.app.ui.theme.ArrColors
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

/** Onglets du menu pause ; le contenu suit l'onglet qui a le focus. */
private enum class PauseTab(val label: String) {
    CHAPTERS("Chapitres"), INFO("Infos"), CAST("Distribution"), SUBTITLES("Sous-titres")
}

private val ChipShape = RoundedCornerShape(8.dp)

/**
 * Menu pause « façon Apple TV » : par-dessus l'image figée, le logo du
 * titre, la progression et l'heure de fin, puis des onglets — chapitres
 * (avec vignettes, choisir un chapitre y saute), résumé, distribution,
 * pistes audio et sous-titres.
 *
 * Limite assumée (ADR-007 § 4) : « les acteurs à l'écran à cet instant »
 * n'existent dans aucune source de données accessible ; l'onglet
 * Distribution montre la distribution principale.
 */
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
) {
    val touch = LocalScreen.current.isTouch
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
    val resumeFocus = remember { FocusRequester() }
    val remaining = ((duration - position) / 1000).coerceAtLeast(0)
    val endsAt = LocalTime.now().plusSeconds(remaining).format(DateTimeFormatter.ofPattern("HH:mm"))

    Box(
        Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    0f to Color(0xD90A0E16),
                    0.35f to Color(0x660A0E16),
                    0.55f to Color(0x990A0E16),
                    1f to Color(0xF50A0E16),
                )
            )
    ) {
        // ── En haut : logo / titre, méta ──
        Column(Modifier.align(Alignment.TopStart).padding(start = gutter, top = 32.dp).widthIn(max = 520.dp)) {
            val logo = absolute(meta?.logo)
            if (logo != null) {
                AsyncImage(
                    model = logo,
                    contentDescription = meta?.title,
                    contentScale = ContentScale.Fit,
                    alignment = Alignment.CenterStart,
                    modifier = Modifier.heightIn(max = 70.dp).widthIn(max = 300.dp),
                )
            } else {
                Text(meta?.title ?: info.title.orEmpty(), style = MaterialTheme.typography.displayMedium, maxLines = 2)
            }
            // Épisode : « S02E03 · Static »
            meta?.subtitle?.let {
                Text(it, style = MaterialTheme.typography.titleLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 6.dp))
            }
            Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                techBadges(meta?.file).forEach { Badge(it, highlight = true) }
            }
        }

        // ── En haut à droite : heure de fin ──
        Column(Modifier.align(Alignment.TopEnd).padding(end = gutter, top = 36.dp), horizontalAlignment = Alignment.End) {
            Text("Fin à $endsAt", style = MaterialTheme.typography.titleLarge)
            Text("encore ${formatClock(remaining)}", style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
        }

        // ── En bas : progression, onglets, contenu ──
        Column(Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(bottom = 22.dp)) {
            Column(Modifier.padding(horizontal = gutter)) {
                val progress = if (duration > 0) position.toFloat() / duration else 0f
                if (touch) {
                    // Au doigt : toucher la barre y saute
                    Box(
                        Modifier.fillMaxWidth().height(28.dp).pointerInput(duration) {
                            detectTapGestures { offset ->
                                if (duration > 0) onSeek(offset.x / size.width * duration / 1000.0)
                            }
                        },
                        contentAlignment = Alignment.Center,
                    ) {
                        ProgressBar(progress, Modifier.fillMaxWidth(), height = 6.dp)
                    }
                } else {
                    ProgressBar(progress, Modifier.fillMaxWidth(), height = 5.dp)
                }
                Row(Modifier.fillMaxWidth().padding(top = 6.dp, bottom = 14.dp)) {
                    Text(formatClock(position / 1000), style = MaterialTheme.typography.labelLarge)
                    Spacer(Modifier.weight(1f))
                    Text(formatClock(duration / 1000), style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
                }
                Row(
                    Modifier.then(if (touch) Modifier.horizontalScroll(rememberScrollState()) else Modifier),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (touch) ArrButton("−10 s", { onSkip(-10) })
                    ArrButton("Reprendre", onResume, primary = true, leading = "▶", modifier = Modifier.focusRequester(resumeFocus))
                    if (touch) ArrButton("+30 s", { onSkip(30) })
                    ArrButton("Audio", { showAudio = true }, leading = "♪", modifier = Modifier.focusRequester(audioFocus))
                    Spacer(Modifier.width(8.dp))
                    tabs.forEach { option ->
                        TabButton(option.label, selected = option == tab, onFocus = { tab = option })
                    }
                    if (touch) {
                        Spacer(Modifier.width(8.dp))
                        ArrButton("Quitter", onQuit, leading = "✕")
                    } else {
                        Spacer(Modifier.weight(1f))
                        Text("Retour : quitter la lecture", style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, maxLines = 1)
                    }
                }
            }

            Box(Modifier.fillMaxWidth().height(if (LocalScreen.current.isPhone) 128.dp else 150.dp).padding(top = 14.dp)) {
                when (tab) {
                    PauseTab.CHAPTERS -> ChaptersPanel(info.chapters, position, absolute, onSeek)
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

/** Onglet : il s'active dès qu'il reçoit le focus (pas besoin de valider). */
@Composable
private fun TabButton(label: String, selected: Boolean, onFocus: () -> Unit) {
    Surface(
        onClick = onFocus,
        modifier = Modifier.height(36.dp).onFocusChanged { if (it.isFocused) onFocus() }.tapToClick(onFocus),
        shape = ClickableSurfaceDefaults.shape(ChipShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.06f),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) Color(0x33FFFFFF) else Color.Transparent,
            contentColor = if (selected) ArrColors.Text else ArrColors.TextSecondary,
            focusedContainerColor = ArrColors.Accent,
            focusedContentColor = ArrColors.Night,
        ),
    ) {
        // Largeur = celle du texte (fillMaxSize étirerait l'onglet sur toute la rangée)
        Box(Modifier.fillMaxHeight().padding(horizontal = 14.dp), contentAlignment = Alignment.Center) {
            Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 1)
        }
    }
}

@Composable
private fun ChaptersPanel(chapters: List<Chapter>, position: Long, absolute: (String?) -> String?, onSeek: (Double) -> Unit) {
    val seconds = position / 1000.0
    val current = chapters.indexOfLast { it.start <= seconds }.coerceAtLeast(0)
    val listState = rememberLazyListState(initialFirstVisibleItemIndex = (current - 1).coerceAtLeast(0))
    // Téléphone : vignette 16:9 plus petite, pour que le nom tienne sous la vignette
    val phone = LocalScreen.current.isPhone
    val thumbWidth = if (phone) 128.dp else 168.dp
    val thumbHeight = if (phone) 72.dp else 94.dp
    LazyRow(
        state = listState,
        contentPadding = PaddingValues(horizontal = gutter),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        items(chapters, key = { it.index }) { chapter ->
            val isCurrent = chapter.index == chapters.getOrNull(current)?.index
            Column(Modifier.width(thumbWidth)) {
                Surface(
                    onClick = { onSeek(chapter.start) },
                    modifier = Modifier.width(thumbWidth).height(thumbHeight).tapToClick({ onSeek(chapter.start) }),
                    shape = ClickableSurfaceDefaults.shape(ChipShape),
                    scale = ClickableSurfaceDefaults.scale(focusedScale = 1.08f),
                    border = ClickableSurfaceDefaults.border(
                        border = if (isCurrent) Border(BorderStroke(2.dp, ArrColors.AccentText), shape = ChipShape) else Border.None,
                        focusedBorder = Border(BorderStroke(2.dp, ArrColors.Accent), shape = ChipShape),
                    ),
                    colors = ClickableSurfaceDefaults.colors(containerColor = ArrColors.Card, focusedContainerColor = ArrColors.Card),
                ) {
                    // Vignette relayée par le serveur (le jeton est ajouté par le client HTTP)
                    ArtImage(absolute(chapter.image), chapter.name, Modifier.fillMaxSize())
                }
                Text(
                    chapter.name,
                    style = MaterialTheme.typography.labelLarge,
                    color = if (isCurrent) ArrColors.AccentText else ArrColors.Text,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Text(formatClock(chapter.start.toLong()), style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary)
            }
        }
    }
}

@Composable
private fun InfoPanel(meta: PlaybackMeta?, info: PlayInfo) {
    Column(Modifier.padding(horizontal = gutter).widthIn(max = 760.dp)) {
        meta?.metaLine?.takeIf { it.isNotBlank() }?.let {
            Text(it, style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
        }
        Text(
            meta?.overview ?: info.overview.orEmpty(),
            style = MaterialTheme.typography.bodyLarge,
            maxLines = 5,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

@Composable
private fun CastPanel(meta: PlaybackMeta?) {
    LazyRow(contentPadding = PaddingValues(horizontal = gutter), horizontalArrangement = Arrangement.spacedBy(18.dp)) {
        items(meta?.cast.orEmpty().take(20)) { person ->
            Column(Modifier.width(92.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                // Focusable (sans action) : c'est ce qui fait défiler la rangée à la télécommande
                Surface(
                    onClick = {},
                    modifier = Modifier.size(72.dp),
                    shape = ClickableSurfaceDefaults.shape(CircleShape),
                    scale = ClickableSurfaceDefaults.scale(focusedScale = 1.1f),
                    border = ClickableSurfaceDefaults.border(focusedBorder = Border(BorderStroke(2.dp, ArrColors.Accent), shape = CircleShape)),
                    colors = ClickableSurfaceDefaults.colors(containerColor = ArrColors.Card, focusedContainerColor = ArrColors.Card),
                ) {
                    if (person.photo != null) {
                        AsyncImage(model = person.photo, contentDescription = person.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize().clip(CircleShape))
                    }
                }
                Text(person.name, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 6.dp))
                Text(person.character, style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
            }
        }
    }
}

@Composable
internal fun TracksPanel(
    choices: List<TrackChoice>,
    allowOff: Boolean,
    sidePadding: Dp = gutter,
    download: SubtitleDownload? = null,
    onSelect: (TrackChoice?) -> Unit,
) {
    if (choices.isEmpty() && !allowOff) {
        Text("Aucune piste", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(horizontal = sidePadding))
        return
    }
    LazyRow(contentPadding = PaddingValues(horizontal = sidePadding), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
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
                val now = if (download.shiftMs == 0) "Pas de décalage" else "Décalage ${fr.arrmada.app.data.SubtitleShiftLogic.format(download.shiftMs)}"
                item {
                    OptionChip("− 0,5 s", "$now · plus tôt", selected = false, supported = true) {
                        onShift(-fr.arrmada.app.data.SubtitleShiftLogic.STEP_MS)
                    }
                }
                item {
                    OptionChip("+ 0,5 s", "$now · plus tard", selected = false, supported = true) {
                        onShift(fr.arrmada.app.data.SubtitleShiftLogic.STEP_MS)
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

@Composable
private fun OptionChip(title: String, detail: String, selected: Boolean, supported: Boolean, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        modifier = Modifier.width(220.dp).height(64.dp).tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(ChipShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.05f),
        border = ClickableSurfaceDefaults.border(
            border = if (selected) Border(BorderStroke(2.dp, ArrColors.Accent), shape = ChipShape) else Border.None,
        ),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) ArrColors.Accent.copy(alpha = 0.22f) else Color(0x26FFFFFF),
            contentColor = if (supported) ArrColors.Text else ArrColors.TextSecondary,
            focusedContainerColor = ArrColors.Accent,
            focusedContentColor = ArrColors.Night,
        ),
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (selected) {
                    Box(Modifier.size(8.dp).clip(CircleShape).background(ArrColors.Seen))
                    Spacer(Modifier.width(6.dp))
                }
                Text(title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Text(detail, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}
