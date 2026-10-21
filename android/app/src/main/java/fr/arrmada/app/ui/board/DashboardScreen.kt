package fr.arrmada.app.ui.board

import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.AdaptiveRow
import fr.arrmada.app.ui.components.gutter
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.CubicBezierEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Dashboard
import fr.arrmada.app.data.DashboardLogic
import fr.arrmada.app.data.Fr
import fr.arrmada.app.data.LibraryItem
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ContentRow
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.Motion
import fr.arrmada.app.ui.components.Pill
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay
import java.time.LocalDateTime

/** Relecture du tableau de bord (l'add-on : 20 s ; le serveur le garde 15 s). */
private const val REFRESH_MS = 20_000L

/**
 * Tableau de bord de l'add-on : salutation, quatre compteurs (films,
 * séries, stockage, téléchargements) qui défilent jusqu'à leur valeur,
 * téléchargements en cours, état des services et ajouts récents.
 */
@Composable
fun DashboardScreen(repository: Repository, absolute: (String?) -> String?, onOpen: (LibraryItem) -> Unit, onDownloads: () -> Unit) {
    var dashboard by remember { mutableStateOf<Dashboard?>(null) }
    var recent by remember { mutableStateOf<List<LibraryItem>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var fetchedAt by remember { mutableStateOf<LocalDateTime?>(null) }
    var refresh by remember { mutableIntStateOf(0) }

    LaunchedEffect(refresh) {
        while (true) {
            runCatching { repository.dashboard() }
                .onSuccess { dashboard = it; fetchedAt = LocalDateTime.now(); error = null }
                .onFailure { if (dashboard == null) error = it.message ?: "Serveur injoignable" }
            recent = runCatching { repository.recent() }.getOrDefault(recent)
            delay(REFRESH_MS)
        }
    }

    val d = dashboard
    when {
        error != null && d == null -> return MessageScreen("Serveur injoignable", error, "Réessayer") { error = null; refresh++ }
        d == null -> return MessageScreen("Chargement…")
    }
    DashboardContent(d!!, recent, LocalDateTime.now(), fetchedAt, absolute, onOpen, onDownloads, onRefresh = { refresh++ })
}

/** Affichage (séparé pour les captures d'écran de test). */
@Composable
fun DashboardContent(
    dashboard: Dashboard,
    recent: List<LibraryItem>,
    now: LocalDateTime,
    fetchedAt: LocalDateTime?,
    absolute: (String?) -> String?,
    onOpen: (LibraryItem) -> Unit,
    onDownloads: () -> Unit,
    onRefresh: () -> Unit,
) {
    val stats = dashboard.stats
    val storage = DashboardLogic.storage(dashboard)
    val downloads = DashboardLogic.downloadsCount(dashboard)
    val services = DashboardLogic.services(dashboard)
    val focus = remember { FocusRequester() }

    LazyColumn(Modifier.fillMaxSize().background(ArrColors.Night)) {
        item {
            val title: @Composable () -> Unit = {
                Text("${Fr.greeting(now.hour)}.", style = MaterialTheme.typography.displayMedium)
                Text(DashboardLogic.summary(dashboard), style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary)
            }
            val buttons: @Composable () -> Unit = {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    ArrButton("Téléchargements", onDownloads, modifier = Modifier.focusRequester(focus))
                    ArrButton("Actualiser", onRefresh)
                }
            }
            if (LocalScreen.current.isPhone) {
                // Téléphone : titre et résumé sur toute la largeur, boutons dessous
                Column(Modifier.fillMaxWidth().padding(start = gutter, end = gutter, top = 28.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Column { title() }
                    buttons()
                }
            } else {
                Row(Modifier.fillMaxWidth().padding(start = gutter, end = gutter, top = 28.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) { title() }
                    buttons()
                }
            }
        }
        // ── Compteurs ──
        item {
            // Quatre compteurs sur une ligne (TV, tablette), deux par ligne sur téléphone
            val tiles: List<@Composable (Modifier) -> Unit> = listOf(
                { m -> Kpi("Films", stats.movies, "dans la médiathèque", m) },
                { m -> Kpi("Séries", stats.series, Fr.plural(stats.episodes, "épisode"), m) },
                { m ->
                    Tile("Stockage", m.height(104.dp)) {
                        Text(storage.value, style = MaterialTheme.typography.headlineMedium, maxLines = 1)
                        Text(storage.hint, style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary, maxLines = 1)
                        ProgressBar(storage.usedPct / 100f, Modifier.fillMaxWidth().padding(top = 6.dp), height = 4.dp)
                    }
                },
                { m -> Kpi("En cours", downloads, if (downloads == 0) "file vide" else if (downloads == 1) "téléchargement" else "téléchargements", m) },
            )
            Column(Modifier.padding(start = gutter, end = gutter, top = 20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                tiles.chunked(if (LocalScreen.current.isPhone) 2 else 4).forEach { line ->
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        line.forEach { tile -> tile(Modifier.weight(1f)) }
                    }
                }
            }
        }
        // ── Téléchargements + services ──
        item {
            AdaptiveRow(Modifier.padding(start = gutter, end = gutter, top = 18.dp), scroll = false) { share ->
                Tile("En cours de téléchargement", share.of(1.4f)) {
                    if (dashboard.downloads.isEmpty()) {
                        Text("Aucun téléchargement en cours", style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary)
                    }
                    dashboard.downloads.take(DashboardLogic.MAX_DOWNLOADS).forEach { dl ->
                        Column(Modifier.padding(top = 6.dp)) {
                            Text(dl.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(DashboardLogic.downloadMeta(dl), style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary)
                            ProgressBar((dl.progress / 100).toFloat(), Modifier.fillMaxWidth().padding(top = 3.dp))
                        }
                    }
                    val more = downloads - dashboard.downloads.take(DashboardLogic.MAX_DOWNLOADS).size
                    if (more > 0) Text("+ $more autre(s)", style = MaterialTheme.typography.labelSmall, color = ArrColors.AccentText, modifier = Modifier.padding(top = 6.dp))
                }
                Tile("Services", share.of(1f)) {
                    ServicePills(services)
                    val active = services.count { it.isEnabled }
                    val ago = fetchedAt?.let { java.time.Duration.between(it, now).toMinutes() }
                    Text(
                        listOfNotNull(
                            when {
                                ago == null -> null
                                ago < 1 -> "Mis à jour à l’instant"
                                else -> "Mis à jour il y a $ago min"
                            },
                            "$active/${services.size} actifs",
                        ).joinToString(" · "),
                        style = MaterialTheme.typography.labelSmall,
                        color = ArrColors.TextSecondary,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
            }
        }
        // ── Ajouts récents ──
        item {
            ContentRow("Ajouts récents · ${Fr.plural(recent.size, "titre")}", recent, Modifier.padding(top = 18.dp), key = { it.type + it.externalId }) { item ->
                PosterCard(absolute(item.posterUrl), item.title, onClick = { onOpen(item) }, width = 96.dp)
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ServicePills(services: List<fr.arrmada.app.data.DashService>) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        services.forEach { s ->
            Row(
                Modifier.clip(RoundedCornerShape(50)).background(Color(0x14FFFFFF)).padding(horizontal = 9.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Box(Modifier.size(7.dp).clip(CircleShape).background(if (s.isEnabled) ArrColors.Seen else Color(0x66C9D3E0)))
                Text(s.name.ifBlank { s.type }, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun Tile(label: String, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Column(modifier.background(ArrColors.CardDeep, RoundedCornerShape(14.dp)).padding(14.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
        content()
    }
}

/** Compteur qui défile jusqu'à sa valeur (~0,7 s, ralenti à la fin), comme l'add-on. */
@Composable
private fun Kpi(label: String, value: Int, hint: String, modifier: Modifier = Modifier) {
    val shown = remember { Animatable(if (Motion.enabled) 0f else value.toFloat()) }
    LaunchedEffect(value) {
        if (!Motion.enabled) {
            shown.snapTo(value.toFloat())
            return@LaunchedEffect
        }
        delay(250)
        shown.animateTo(value.toFloat(), tween(726, easing = CubicBezierEasing(0.33f, 1f, 0.68f, 1f)))
    }
    Tile(label, modifier.height(104.dp)) {
        Text(Fr.int(shown.value.toInt()), style = MaterialTheme.typography.displayMedium, maxLines = 1)
        Text(hint, style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary, maxLines = 1)
    }
}
