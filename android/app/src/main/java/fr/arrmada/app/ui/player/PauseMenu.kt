package fr.arrmada.app.ui.player

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
import androidx.compose.ui.unit.dp
import androidx.media3.common.C
import androidx.media3.common.Tracks
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.data.Chapter
import fr.arrmada.app.data.MovieDetail
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

/** Onglets du menu pause ; le contenu suit l'onglet qui a le focus. */
private enum class PauseTab(val label: String) {
    CHAPTERS("Chapitres"), INFO("Infos"), CAST("Distribution"), AUDIO("Audio"), SUBTITLES("Sous-titres")
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
    detail: MovieDetail?,
    position: Long,
    duration: Long,
    tracks: Tracks,
    absolute: (String?) -> String?, // « /api/… » → adresse complète du serveur
    onResume: () -> Unit,
    onSeek: (seconds: Double) -> Unit,
    onSelectTrack: (type: Int, choice: TrackChoice?) -> Unit,
    initialTab: String? = null, // libellé de l'onglet affiché d'abord (tests)
) {
    val tabs = PauseTab.entries.filter { tab ->
        when (tab) {
            PauseTab.CHAPTERS -> info.chapters.isNotEmpty()
            PauseTab.CAST -> !detail?.cast.isNullOrEmpty()
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
        Column(Modifier.align(Alignment.TopStart).padding(start = 48.dp, top = 32.dp).widthIn(max = 520.dp)) {
            val logo = absolute(detail?.images?.bestLogo)
            if (logo != null) {
                AsyncImage(
                    model = logo,
                    contentDescription = detail?.title,
                    contentScale = ContentScale.Fit,
                    alignment = Alignment.CenterStart,
                    modifier = Modifier.heightIn(max = 70.dp).widthIn(max = 300.dp),
                )
            } else {
                Text(detail?.title ?: info.title.orEmpty(), style = MaterialTheme.typography.displayMedium, maxLines = 2)
            }
            if (detail == null && !info.title.isNullOrBlank()) {
                // Épisode : son titre propre
                Text(info.title, style = MaterialTheme.typography.titleLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 6.dp))
            }
            Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                techBadges(detail?.file).forEach { Badge(it, highlight = true) }
            }
        }

        // ── En haut à droite : heure de fin ──
        Column(Modifier.align(Alignment.TopEnd).padding(end = 48.dp, top = 36.dp), horizontalAlignment = Alignment.End) {
            Text("Fin à $endsAt", style = MaterialTheme.typography.titleLarge)
            Text("encore ${formatClock(remaining)}", style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
        }

        // ── En bas : progression, onglets, contenu ──
        Column(Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(bottom = 22.dp)) {
            Column(Modifier.padding(horizontal = 48.dp)) {
                ProgressBar(if (duration > 0) position.toFloat() / duration else 0f, Modifier.fillMaxWidth(), height = 5.dp)
                Row(Modifier.fillMaxWidth().padding(top = 6.dp, bottom = 14.dp)) {
                    Text(formatClock(position / 1000), style = MaterialTheme.typography.labelLarge)
                    Spacer(Modifier.weight(1f))
                    Text(formatClock(duration / 1000), style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                    ArrButton("Reprendre", onResume, primary = true, leading = "▶", modifier = Modifier.focusRequester(resumeFocus))
                    Spacer(Modifier.width(8.dp))
                    tabs.forEach { option ->
                        TabButton(option.label, selected = option == tab, onFocus = { tab = option })
                    }
                    Spacer(Modifier.weight(1f))
                    Text("Retour : quitter la lecture", style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, maxLines = 1)
                }
            }

            Box(Modifier.fillMaxWidth().height(150.dp).padding(top = 14.dp)) {
                when (tab) {
                    PauseTab.CHAPTERS -> ChaptersPanel(info.chapters, position, absolute, onSeek)
                    PauseTab.INFO -> InfoPanel(detail, info)
                    PauseTab.CAST -> CastPanel(detail)
                    PauseTab.AUDIO -> TracksPanel(trackChoices(tracks, C.TRACK_TYPE_AUDIO), allowOff = false) {
                        onSelectTrack(C.TRACK_TYPE_AUDIO, it)
                    }
                    PauseTab.SUBTITLES -> TracksPanel(trackChoices(tracks, C.TRACK_TYPE_TEXT), allowOff = true) {
                        onSelectTrack(C.TRACK_TYPE_TEXT, it)
                    }
                }
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { resumeFocus.requestFocus() } }
}

/** Onglet : il s'active dès qu'il reçoit le focus (pas besoin de valider). */
@Composable
private fun TabButton(label: String, selected: Boolean, onFocus: () -> Unit) {
    Surface(
        onClick = onFocus,
        modifier = Modifier.height(36.dp).onFocusChanged { if (it.isFocused) onFocus() },
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
    LazyRow(
        state = listState,
        contentPadding = PaddingValues(horizontal = 48.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        items(chapters, key = { it.index }) { chapter ->
            val isCurrent = chapter.index == chapters.getOrNull(current)?.index
            Column(Modifier.width(168.dp)) {
                Surface(
                    onClick = { onSeek(chapter.start) },
                    modifier = Modifier.width(168.dp).height(94.dp),
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
private fun InfoPanel(detail: MovieDetail?, info: PlayInfo) {
    Column(Modifier.padding(horizontal = 48.dp).widthIn(max = 760.dp)) {
        val meta = listOfNotNull(
            detail?.year?.toString(),
            detail?.genres?.take(3)?.joinToString(", ")?.ifBlank { null },
            detail?.crew?.firstOrNull { it.job == "Director" }?.let { "Réalisé par ${it.name}" },
        ).joinToString("  ·  ")
        if (meta.isNotBlank()) Text(meta, style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
        Text(
            detail?.overview ?: info.overview.orEmpty(),
            style = MaterialTheme.typography.bodyLarge,
            maxLines = 5,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

@Composable
private fun CastPanel(detail: MovieDetail?) {
    LazyRow(contentPadding = PaddingValues(horizontal = 48.dp), horizontalArrangement = Arrangement.spacedBy(18.dp)) {
        items(detail?.cast.orEmpty().take(20)) { person ->
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
private fun TracksPanel(choices: List<TrackChoice>, allowOff: Boolean, onSelect: (TrackChoice?) -> Unit) {
    if (choices.isEmpty() && !allowOff) {
        Text("Aucune piste", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(horizontal = 48.dp))
        return
    }
    LazyRow(contentPadding = PaddingValues(horizontal = 48.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
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
        modifier = Modifier.width(220.dp).height(64.dp),
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
