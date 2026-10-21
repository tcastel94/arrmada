package fr.arrmada.app.ui.detail

import fr.arrmada.app.data.PlayOnTv
import fr.arrmada.app.ui.request.SendToTvDialog
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.touchScroll
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.tapToClick
import android.widget.Toast
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.Glow
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.data.EpisodeRow
import fr.arrmada.app.data.EpisodeStatus
import fr.arrmada.app.data.JellyfinEpisode
import fr.arrmada.app.data.NextUp
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.SeasonInfo
import fr.arrmada.app.data.SeriesDetail
import fr.arrmada.app.data.SeriesLogic
import fr.arrmada.app.data.WatchState
import fr.arrmada.app.data.WatchStateUpdate
import fr.arrmada.app.data.shortDate
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.Badge
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.SeenBadge
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.components.formatDuration
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch

/**
 * Écran Série (comme celui de l'add-on) : saisons en pastilles, épisodes en
 * vignettes (vu, barre de reprise, manquant, à venir), bouton « Lire la
 * suite ». OK sur un épisode : lecture (reprise si commencé). Appui long :
 * depuis le début, marquer vu / non vu. OK sur un épisode manquant : Sonarr
 * le cherche.
 *
 * [onPlay] reçoit (série, saison, épisode, position de départ en secondes).
 */
@Composable
fun SeriesScreen(
    sonarrId: String,
    repository: Repository,
    absolute: (String?) -> String?,
    onPlay: (series: SeriesDetail, season: Int, episode: Int, start: Int) -> Unit,
    onDownload: (SeriesDetail) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var series by remember { mutableStateOf<SeriesDetail?>(null) }
    var states by remember { mutableStateOf<List<WatchState>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var chosenSeason by remember { mutableIntStateOf(-1) } // -1 : pas encore choisie
    var sendTo by remember { mutableStateOf<EpisodeRow?>(null) } // « Sur la TV »
    val jellyfin = remember { mutableStateMapOf<Int, List<JellyfinEpisode>>() }

    LaunchedEffect(sonarrId) {
        try {
            val detail = repository.series(sonarrId)
            if (detail.error != null) {
                error = detail.error
                return@LaunchedEffect
            }
            states = runCatching { repository.watchStates() }.getOrDefault(emptyList())
            series = detail
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    val s = series
    if (error != null) return MessageScreen("Série indisponible", error)
    if (s == null) return MessageScreen("Chargement…")

    val byEpisode = SeriesLogic.statesBySeries(states, s.tvdbId)
    val nextUp = SeriesLogic.nextUp(s, byEpisode)
    // Saison affichée : celle choisie, sinon celle du prochain épisode à voir
    val season = if (chosenSeason >= 0) chosenSeason else SeriesLogic.initialSeason(s, nextUp)

    // Vignettes Jellyfin de la saison affichée (chargées à la demande)
    LaunchedEffect(season, s.tvdbId) {
        val tvdb = s.tvdbId ?: return@LaunchedEffect
        if (season !in jellyfin) {
            jellyfin[season] = runCatching { repository.seasonEpisodes(tvdb, season).episodes }.getOrDefault(emptyList())
        }
    }

    fun mark(row: EpisodeRow, watched: Boolean) {
        val tvdb = s.tvdbId ?: return
        val update = WatchStateUpdate(
            mediaType = "episode", idType = "tvdb", id = tvdb.toString(),
            season = row.season, episode = row.episode, title = row.title,
            watched = watched, position = 0, total = row.total, lastPlayed = Repository.nowLastPlayed(),
        )
        scope.launch {
            runCatching { repository.saveWatchState(update) }
                .onSuccess { states = runCatching { repository.watchStates() }.getOrDefault(states) }
                .onFailure { Toast.makeText(context, it.message ?: "Échec", Toast.LENGTH_SHORT).show() }
        }
    }

    fun searchMissing(row: EpisodeRow) {
        val tvdb = s.tvdbId ?: return
        scope.launch {
            val result = runCatching { repository.searchEpisode(tvdb, s.title, row.season, row.episode) }
            val message = result.getOrNull()?.message ?: result.exceptionOrNull()?.message ?: "Échec de la recherche"
            Toast.makeText(context, message, Toast.LENGTH_LONG).show()
        }
    }

    SeriesContent(
        series = s,
        season = season,
        rows = SeriesLogic.orderedSeasons(s).firstOrNull { it.seasonNumber == season }
            ?.let { SeriesLogic.rows(it, jellyfin[season].orEmpty(), byEpisode) }.orEmpty(),
        nextUp = nextUp,
        seasonSubtitle = { info -> seasonSubtitle(info, byEpisode) },
        absolute = absolute,
        onSeason = { chosenSeason = it },
        onPlay = { row, start -> onPlay(s, row.season, row.episode, start) },
        onMissing = { row ->
            if (row.status == EpisodeStatus.UPCOMING) {
                Toast.makeText(context, "Diffusion le ${shortDate(row.airDate) ?: "?"}", Toast.LENGTH_SHORT).show()
            } else {
                searchMissing(row)
            }
        },
        onMark = ::mark,
        onDownload = { onDownload(s) },
        onSendToTv = if (LocalScreen.current.isTouch && s.tvdbId != null) ({ row: EpisodeRow -> sendTo = row }) else null,
    )

    // « Sur la TV » : épisode envoyé à une TV de la maison
    sendTo?.let { row ->
        SendToTvDialog(
            repository = repository,
            title = "${s.title} ${row.code}",
            onDismiss = { sendTo = null },
            onSend = { target ->
                scope.launch {
                    val what = PlayOnTv("episode", s.tvdbId.toString(), row.season, row.episode, "${s.title} ${row.code}", resume = true)
                    val message = runCatching { repository.playOnTv(target.id, what) }
                        .fold({ it.message ?: "Envoyé sur ${target.name}" }, { it.message ?: "Échec" })
                    Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
                }
            },
        )
    }
}

/** « 9/9 vus », « 4/10 sur le NAS », « À venir ». */
private fun seasonSubtitle(info: SeasonInfo, states: Map<Pair<Int, Int>, WatchState>): String {
    val total = info.episodes.size.takeIf { it > 0 } ?: info.episodeCount
    val have = info.episodes.count { it.hasFile }.takeIf { info.episodes.isNotEmpty() } ?: info.episodesHave
    val seen = info.episodes.count { states[it.seasonNumber to it.episodeNumber]?.watched == true }
    return when {
        total == 0 -> "À venir"
        seen > 0 -> "$seen/$total vus"
        have < total -> "$have/$total sur le NAS"
        else -> "$total épisodes"
    }
}

/** Affichage de l'écran Série (séparé du chargement pour les captures d'écran de test). */
@Composable
fun SeriesContent(
    series: SeriesDetail,
    season: Int,
    rows: List<EpisodeRow>,
    nextUp: NextUp?,
    seasonSubtitle: (SeasonInfo) -> String,
    absolute: (String?) -> String?,
    onSeason: (Int) -> Unit,
    onPlay: (EpisodeRow, start: Int) -> Unit,
    onMissing: (EpisodeRow) -> Unit,
    onMark: (EpisodeRow, watched: Boolean) -> Unit,
    onDownload: () -> Unit,
    onSendToTv: ((EpisodeRow) -> Unit)? = null, // téléphone / tablette : « Sur la TV »
) {
    val mainFocus = remember { FocusRequester() }
    var focused by remember(season) { mutableStateOf<EpisodeRow?>(null) }
    var menuFor by remember { mutableStateOf<EpisodeRow?>(null) }
    val listState = rememberLazyListState()

    // La rangée d'épisodes s'ouvre sur le prochain à voir de la saison
    LaunchedEffect(season, rows.size) {
        val index = rows.indexOfFirst { !it.watched && it.status == EpisodeStatus.AVAILABLE }
        if (index > 0) listState.scrollToItem((index - 1).coerceAtLeast(0))
    }

    KenBurnsBackdrop(url = absolute(series.images.fanart ?: series.images.landscape)) {
        Column(Modifier.fillMaxSize().touchScroll().padding(top = 26.dp, bottom = 24.dp)) {
            // ── Titre, méta, résumé ──
            Column(Modifier.padding(horizontal = gutter).widthIn(max = 600.dp)) {
                val logo = absolute(series.images.bestLogo)
                if (logo != null) {
                    AsyncImage(
                        model = logo,
                        contentDescription = series.title,
                        contentScale = ContentScale.Fit,
                        alignment = Alignment.CenterStart,
                        modifier = Modifier.heightIn(max = 60.dp).widthIn(max = 300.dp),
                    )
                } else {
                    Text(series.title, style = MaterialTheme.typography.displayMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                Text(
                    listOfNotNull(
                        series.year?.toString(),
                        series.network?.takeIf { it.isNotBlank() },
                        series.seasons.count { it.seasonNumber > 0 }.takeIf { it > 0 }?.let { if (it > 1) "$it saisons" else "1 saison" },
                        series.genres.take(2).joinToString(", ").ifBlank { null },
                        if (series.status == "ended") "Terminée" else null,
                    ).joinToString("  ·  "),
                    style = MaterialTheme.typography.labelLarge,
                    color = ArrColors.TextSecondary,
                    modifier = Modifier.padding(top = 8.dp),
                )
                Text(
                    series.overview.orEmpty(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = ArrColors.TextSecondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }

            // ── Actions ──
            Row(Modifier.padding(start = gutter, top = 14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                if (nextUp != null) {
                    ArrButton(
                        nextUp.label,
                        { onPlay(nextUp.row, if (nextUp.resume) nextUp.row.position else 0) },
                        primary = true,
                        leading = "▶",
                        modifier = Modifier.focusRequester(mainFocus),
                    )
                }
                ArrButton("Télécharger", onDownload, modifier = if (nextUp == null) Modifier.focusRequester(mainFocus) else Modifier)
            }

            // ── Saisons ──
            LazyRow(
                contentPadding = PaddingValues(horizontal = gutter, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.padding(top = 8.dp),
            ) {
                items(SeriesLogic.orderedSeasons(series), key = { it.seasonNumber }) { info ->
                    SeasonChip(
                        label = if (info.seasonNumber == 0) "Spéciaux" else "Saison ${info.seasonNumber}",
                        subtitle = seasonSubtitle(info),
                        selected = info.seasonNumber == season,
                        onFocus = { onSeason(info.seasonNumber) },
                    )
                }
            }

            // ── Épisodes ──
            LazyRow(
                state = listState,
                contentPadding = PaddingValues(horizontal = gutter, vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                items(rows, key = { "${it.season}-${it.episode}" }) { row ->
                    EpisodeCard(
                        row = row,
                        imageUrl = absolute(row.image) ?: absolute(series.images.fanart),
                        onFocus = { focused = row },
                        onClick = {
                            when (row.status) {
                                EpisodeStatus.AVAILABLE -> onPlay(row, if (row.inProgress) row.position else 0)
                                else -> onMissing(row)
                            }
                        },
                        onLongClick = { if (row.status == EpisodeStatus.AVAILABLE) menuFor = row },
                    )
                }
            }

            // ── Épisode sélectionné : résumé ──
            val current = focused
            if (current != null) {
                Column(Modifier.padding(horizontal = gutter).widthIn(max = 760.dp)) {
                    Text(
                        listOfNotNull(
                            "${current.code} · ${current.title}",
                            current.runtime.takeIf { it > 0 }?.let { formatDuration(it) },
                            shortDate(current.airDate)?.let { "diffusé le $it" }.takeIf { current.status != EpisodeStatus.UPCOMING },
                        ).joinToString("  ·  "),
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        current.overview.orEmpty(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = ArrColors.TextSecondary,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.padding(top = 4.dp),
                    )
                }
            }
        }
    }

    // Appui long : petit menu (comme le menu contextuel de l'add-on)
    menuFor?.let { row ->
        EpisodeMenu(
            row = row,
            onDismiss = { menuFor = null },
            onFromStart = { menuFor = null; onPlay(row, 0) },
            onToggleWatched = { menuFor = null; onMark(row, !row.watched) },
            onSendToTv = onSendToTv?.let { send -> { menuFor = null; send(row) } },
        )
    }

    LaunchedEffect(series.id) { runCatching { mainFocus.requestFocus() } }
}

/** Pastille de saison : elle s'active dès qu'elle reçoit le focus. */
@Composable
private fun SeasonChip(label: String, subtitle: String, selected: Boolean, onFocus: () -> Unit) {
    val shape = RoundedCornerShape(8.dp)
    Surface(
        onClick = onFocus,
        modifier = Modifier.height(46.dp).onFocusChanged { if (it.isFocused) onFocus() }.tapToClick(onFocus),
        shape = ClickableSurfaceDefaults.shape(shape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.06f),
        border = ClickableSurfaceDefaults.border(
            border = if (selected) Border(BorderStroke(1.5.dp, ArrColors.AccentText), shape = shape) else Border.None,
        ),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) ArrColors.Accent.copy(alpha = 0.22f) else Color(0x26FFFFFF),
            contentColor = ArrColors.Text,
            focusedContainerColor = ArrColors.Accent,
            focusedContentColor = ArrColors.Night,
        ),
    ) {
        Column(Modifier.fillMaxHeight().padding(horizontal = 14.dp), verticalArrangement = Arrangement.Center) {
            Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 1)
            Text(subtitle, style = MaterialTheme.typography.labelSmall, maxLines = 1)
        }
    }
}

/** Vignette d'épisode 16:9 : image Jellyfin, pastille, barre de reprise, titre dessous. */
@Composable
private fun EpisodeCard(
    row: EpisodeRow,
    imageUrl: String?,
    onFocus: () -> Unit,
    onClick: () -> Unit,
    onLongClick: () -> Unit,
) {
    val shape = RoundedCornerShape(7.dp)
    val dimmed = row.status != EpisodeStatus.AVAILABLE
    Column(Modifier.width(200.dp)) {
        Surface(
            onClick = onClick,
            onLongClick = onLongClick,
            modifier = Modifier.width(200.dp).height(112.dp).onFocusChanged { if (it.isFocused) onFocus() }
                .tapToClick(onClick, onLongClick),
            shape = ClickableSurfaceDefaults.shape(shape),
            scale = ClickableSurfaceDefaults.scale(focusedScale = 1.08f),
            border = ClickableSurfaceDefaults.border(focusedBorder = Border(BorderStroke(2.dp, ArrColors.Accent), shape = shape)),
            glow = ClickableSurfaceDefaults.glow(focusedGlow = Glow(ArrColors.Accent.copy(alpha = 0.65f), 14.dp)),
            colors = ClickableSurfaceDefaults.colors(containerColor = ArrColors.Card, focusedContainerColor = ArrColors.Card),
        ) {
            ArtImage(imageUrl, row.title, Modifier.fillMaxSize())
            if (dimmed) Box(Modifier.fillMaxSize().background(Color(0xB30A0E16)))
            Box(Modifier.fillMaxSize().background(Brush.verticalGradient(0.6f to Color.Transparent, 1f to Color(0xCC0A0E16))))
            when {
                row.watched -> SeenBadge(Modifier.align(Alignment.TopEnd).padding(6.dp))
                row.status == EpisodeStatus.MISSING -> Badge("MANQUANT", Modifier.align(Alignment.TopEnd).padding(6.dp))
                row.status == EpisodeStatus.UPCOMING -> Badge("À VENIR ${shortDate(row.airDate).orEmpty()}".trim(), Modifier.align(Alignment.TopEnd).padding(6.dp), highlight = true)
            }
            Text(
                row.code,
                style = MaterialTheme.typography.labelSmall,
                color = ArrColors.TextSecondary,
                modifier = Modifier.align(Alignment.BottomStart).padding(start = 8.dp, bottom = if (row.progress > 0f) 12.dp else 6.dp),
            )
            if (row.progress > 0f) {
                ProgressBar(row.progress, Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp))
            }
        }
        Text(
            "${row.episode}. ${row.title}",
            style = MaterialTheme.typography.labelLarge,
            color = if (dimmed) ArrColors.TextSecondary else ArrColors.Text,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(top = 6.dp),
        )
        if (row.inProgress) {
            Text("Reprendre à ${formatClock(row.position.toLong())}", style = MaterialTheme.typography.labelSmall, color = ArrColors.AccentText)
        }
    }
}

@Composable
private fun EpisodeMenu(
    row: EpisodeRow,
    onDismiss: () -> Unit,
    onFromStart: () -> Unit,
    onToggleWatched: () -> Unit,
    onSendToTv: (() -> Unit)? = null,
) {
    val first = remember { FocusRequester() }
    Dialog(onDismissRequest = onDismiss) {
        Column(
            Modifier
                .background(ArrColors.CardDeep, RoundedCornerShape(16.dp))
                .padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("${row.code} · ${row.title}", style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(4.dp))
            ArrButton("Lire depuis le début", onFromStart, primary = true, modifier = Modifier.fillMaxWidth().focusRequester(first))
            ArrButton(if (row.watched) "Marquer comme non vu" else "Marquer comme vu", onToggleWatched, modifier = Modifier.fillMaxWidth())
            onSendToTv?.let { ArrButton("Lire sur une TV", it, modifier = Modifier.fillMaxWidth()) }
            ArrButton("Annuler", onDismiss, modifier = Modifier.fillMaxWidth())
        }
    }
    LaunchedEffect(row) { runCatching { first.requestFocus() } }
}
