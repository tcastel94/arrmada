package fr.arrmada.app.ui.request

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import fr.arrmada.app.data.GrabBody
import fr.arrmada.app.data.Release
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.CardShape
import fr.arrmada.app.ui.components.ChoiceDialog
import fr.arrmada.app.ui.components.Dim
import fr.arrmada.app.ui.components.Glass
import fr.arrmada.app.ui.components.GlassChip
import fr.arrmada.app.ui.components.Ink
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.Pressed
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.tapToClick
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch

/**
 * « Trouver une autre version » (appui long sur un film ou une série) :
 * les versions que proposent les indexeurs, comme la recherche manuelle de
 * Radarr / Sonarr. OK sur une version → confirmation → téléchargement (en
 * tête de file). Les versions que Radarr / Sonarr refuseraient d'eux-mêmes
 * (qualité hors profil, déjà présente…) sont grisées, avec la raison : on
 * peut quand même les prendre.
 *
 * [type] : « movie » ou « series » ; [arrId] : Radarr / Sonarr. Série : une
 * saison à la fois (pastilles en haut, première saison par défaut).
 */
@Composable
fun ReleasesScreen(repository: Repository, type: String, arrId: String, title: String, onDone: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val series = type != "movie"
    var seasons by remember { mutableStateOf<List<Int>>(emptyList()) }
    var season by remember { mutableStateOf<Int?>(null) }
    var releases by remember { mutableStateOf<List<Release>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableStateOf(0) }
    var confirm by remember { mutableStateOf<Release?>(null) }
    var grabbing by remember { mutableStateOf(false) }
    val first = remember { FocusRequester() }

    // Série : ses saisons (fiche en cache le plus souvent), hors épisodes spéciaux d'abord
    LaunchedEffect(arrId) {
        if (!series) return@LaunchedEffect
        val numbers = runCatching { repository.series(arrId) }.getOrNull()?.seasons?.map { it.seasonNumber }.orEmpty()
        seasons = numbers.filter { it > 0 }.sorted() + numbers.filter { it == 0 }
        if (season == null) season = seasons.firstOrNull()
    }

    // Recherche interactive : tous les indexeurs sont interrogés (souvent 10 à 40 s)
    LaunchedEffect(season, reload) {
        if (series && season == null) return@LaunchedEffect
        releases = null
        error = null
        runCatching { repository.releases(if (series) "series" else "movie", arrId, season.takeIf { series }) }
            .onSuccess { list ->
                if (list.status == "ok") releases = list.releases else error = list.message ?: "Recherche impossible"
            }
            .onFailure { error = it.message ?: "Serveur injoignable" }
    }

    fun grab(release: Release) {
        val guid = release.guid ?: return
        if (grabbing) return
        grabbing = true
        scope.launch {
            val body = GrabBody(guid, release.indexerId, release.title, title, season.takeIf { series })
            runCatching { repository.grabRelease(if (series) "series" else "movie", arrId, body) }
                .onSuccess {
                    val ok = it.status == "ok"
                    Toast.makeText(context, it.message ?: if (ok) "Téléchargement lancé" else "Refusé", Toast.LENGTH_LONG).show()
                    if (ok) onDone()
                }
                .onFailure { Toast.makeText(context, it.message ?: "Serveur injoignable", Toast.LENGTH_LONG).show() }
            grabbing = false
        }
    }

    val list = releases
    Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
        ScreenHeader(
            "Versions disponibles",
            listOfNotNull(title, season?.let { if (it == 0) "Épisodes spéciaux" else "Saison $it" }.takeIf { series })
                .joinToString(" · "),
        )
        if (series && seasons.size > 1) {
            Row(
                Modifier.padding(horizontal = gutter).padding(top = 8.dp).horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                seasons.forEach { n ->
                    GlassChip(if (n == 0) "Spéciaux" else "Saison $n", selected = n == season) { season = n }
                }
            }
        }
        when {
            error != null -> MessageScreen("Aucune version", error, "Réessayer") { reload++ }
            list == null -> MessageScreen("Les indexeurs cherchent…", "Toutes les sources sont interrogées : 10 à 40 s en général.")
            list.isEmpty() -> MessageScreen("Aucune version trouvée", "Les indexeurs n'ont rien proposé pour ce titre.", "Réessayer") { reload++ }
            else -> {
                LazyColumn(
                    contentPadding = PaddingValues(horizontal = gutter, vertical = 14.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    itemsIndexed(list, key = { i, r -> r.guid ?: "r$i" }) { i, release ->
                        ReleaseRow(release, Modifier.then(if (i == 0) Modifier.focusRequester(first) else Modifier)) {
                            confirm = release
                        }
                    }
                }
                LaunchedEffect(list) { runCatching { first.requestFocus() } }
            }
        }
    }

    confirm?.let { release ->
        ChoiceDialog(
            title = "Télécharger cette version ?",
            subtitle = release.title,
            choices = listOf(
                "Télécharger" to { confirm = null; grab(release) },
                "Annuler" to { confirm = null },
            ),
            onDismiss = { confirm = null },
        )
    }
}

/** Une version : qualité et taille en grand, puis indexeur, source, raison d'un refus éventuel. */
@Composable
private fun ReleaseRow(release: Release, modifier: Modifier, onClick: () -> Unit) {
    val source = if (release.protocol == "usenet") "Usenet" else "Torrent · ${release.seeders ?: 0} sources"
    Surface(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(CardShape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.02f),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = Glass,
            contentColor = if (release.rejected) Dim else Color.White,
            focusedContainerColor = Color.White,
            focusedContentColor = Ink,
            pressedContainerColor = Pressed,
            pressedContentColor = Ink,
        ),
    ) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) {
            Text(
                listOf(release.quality, release.size).filter { it.isNotBlank() }.joinToString(" · "),
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
            )
            Text(release.title, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
            Text(
                listOfNotNull(
                    release.indexer.takeIf { it.isNotBlank() },
                    source,
                    release.rejections.firstOrNull()?.let { "Refusée d'office : $it" }.takeIf { release.rejected },
                ).joinToString(" · "),
                style = MaterialTheme.typography.labelMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}
