package fr.arrmada.app.ui.videos

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Fr
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.VideoFile
import fr.arrmada.app.data.VideoFolder
import fr.arrmada.app.data.VideoListing
import fr.arrmada.app.data.WatchState
import fr.arrmada.app.data.WatchStateUpdate
import fr.arrmada.app.ui.components.ChoiceDialog
import fr.arrmada.app.ui.components.FocusPanel
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.Pill
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch

/**
 * Écran « Vidéos » : les dossiers du NAS déclarés dans la web app (Réglages ›
 * Dossiers vidéo), parcourus comme un explorateur de fichiers. Pour ce qui
 * n'a pas de fiche officielle (mangas « Kai », montages, vidéos perso).
 *
 * Chaque dossier ouvert est un nouvel écran : la touche Retour remonte d'un
 * niveau, comme « cd .. ». OK sur une vidéo : la lit (reprise là où on
 * s'était arrêté) ; appui long : depuis le début, vu / pas vu.
 */
@Composable
fun VideosScreen(
    repository: Repository,
    token: String?,
    onFolder: (String) -> Unit,
    onPlay: (VideoFile, startSeconds: Int) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var listing by remember { mutableStateOf<VideoListing?>(null) }
    var states by remember { mutableStateOf<Map<String, WatchState>>(emptyMap()) }
    var error by remember { mutableStateOf<String?>(null) }
    var menu by remember { mutableStateOf<VideoFile?>(null) }
    var reload by remember { mutableStateOf(0) }

    // Rechargé à chaque retour sur l'écran (vu / reprise après un épisode)
    LaunchedEffect(token, reload) {
        runCatching { repository.videos(token) }
            .onSuccess { listing = it; error = null }
            .onFailure { error = it.message ?: "Serveur injoignable" }
        states = runCatching { repository.watchStates() }.getOrDefault(emptyList())
            .filter { it.mediaType == "file" }
            .associateBy { it.id }
    }

    val current = listing
    when {
        current == null && error != null -> MessageScreen("Vidéos indisponibles", error, "Réessayer") { reload++ }
        current == null -> MessageScreen("Chargement…")
        else -> VideosContent(
            listing = current,
            states = states,
            onFolder = { onFolder(it.token) },
            onPlay = { file -> onPlay(file, VideoRules.resumeAt(states[file.watchId]) ?: 0) },
            onMenu = { menu = it },
        )
    }

    menu?.let { file ->
        val state = states[file.watchId]
        val resumeAt = VideoRules.resumeAt(state)
        val watched = state?.watched == true
        ChoiceDialog(
            title = file.title,
            subtitle = VideoRules.detail(file, state),
            choices = listOfNotNull(
                resumeAt?.let { "Reprendre à ${formatClock(it.toLong())}" to { menu = null; onPlay(file, it) } },
                "Lire depuis le début" to { menu = null; onPlay(file, 0) },
                (if (watched) "Marquer comme non vu" else "Marquer comme vu") to {
                    menu = null
                    scope.launch {
                        runCatching {
                            repository.saveWatchState(
                                WatchStateUpdate(
                                    mediaType = "file",
                                    idType = "sha1",
                                    id = file.watchId,
                                    title = file.title,
                                    watched = !watched,
                                    position = 0,
                                    total = state?.total ?: 0,
                                    lastPlayed = Repository.nowLastPlayed(),
                                )
                            )
                        }
                        reload++
                    }
                },
            ),
            onDismiss = { menu = null },
        )
    }
}

/** Règles d'affichage (reprise, libellés), séparées pour les tests. */
object VideoRules {
    /** Position de reprise en secondes, ou null (pas commencé, ou vu). */
    fun resumeAt(state: WatchState?): Int? = state?.takeIf { !it.watched && it.position > 0 }?.position

    /** « 1,2 Go · sous-titres · vu » / « 1,2 Go · reprise à 12:30 ». */
    fun detail(file: VideoFile, state: WatchState?): String = listOfNotNull(
        Fr.bytes(file.size.toDouble()).takeIf { file.size > 0 },
        when (file.subtitles) {
            0 -> null
            1 -> "sous-titres"
            else -> "${file.subtitles} sous-titres"
        },
        when {
            state?.watched == true -> "vu"
            resumeAt(state) != null -> "reprise à ${formatClock(resumeAt(state)!!.toLong())}"
            else -> null
        },
    ).joinToString(" · ")
}

/** Affichage d'un dossier (séparé pour les captures d'écran de test). */
@Composable
fun VideosContent(
    listing: VideoListing,
    states: Map<String, WatchState>,
    onFolder: (VideoFolder) -> Unit,
    onPlay: (VideoFile) -> Unit,
    onMenu: (VideoFile) -> Unit,
) {
    val first = remember { FocusRequester() }
    val top = listing.crumbs.isEmpty()
    // Fil d'Ariane sous le titre : « Mangas Kai › Dragon Ball Kai »
    val summary = when {
        top -> "Dossiers du NAS hors médiathèque · ajoute-les dans la web app (Réglages › Dossiers vidéo)"
        else -> listOf(
            listing.crumbs.joinToString(" › ") { it.name },
            Fr.plural(listing.folders.size, "dossier").takeIf { listing.folders.isNotEmpty() },
            Fr.plural(listing.files.size, "vidéo").takeIf { listing.files.isNotEmpty() },
        ).filterNotNull().joinToString(" · ")
    }

    Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
        ScreenHeader(if (top) "Vidéos" else listing.title, summary)
        if (listing.folders.isEmpty() && listing.files.isEmpty()) {
            Text(
                if (top) "Aucun dossier vidéo : ajoute-en un dans la web app, Réglages › Dossiers vidéo (ex. /mnt/user/medias/mangas-kai)."
                else "Dossier vide (ni sous-dossier, ni vidéo lisible).",
                style = MaterialTheme.typography.bodyLarge,
                color = ArrColors.TextSecondary,
                modifier = Modifier.padding(horizontal = gutter, vertical = 24.dp),
            )
            return@Column
        }
        LazyColumn(
            contentPadding = PaddingValues(start = gutter, end = gutter, top = 16.dp, bottom = 36.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(listing.folders, key = { "d:" + it.token }) { folder ->
                val isFirst = folder == listing.folders.first()
                FolderRow(folder, Modifier.then(if (isFirst) Modifier.focusRequester(first) else Modifier)) { onFolder(folder) }
            }
            items(listing.files, key = { "f:" + it.token }) { file ->
                val isFirst = listing.folders.isEmpty() && file == listing.files.first()
                FileRow(
                    file,
                    states[file.watchId],
                    Modifier.then(if (isFirst) Modifier.focusRequester(first) else Modifier),
                    onClick = { onPlay(file) },
                    onLongClick = { onMenu(file) },
                )
            }
        }
    }
    LaunchedEffect(listing) { runCatching { first.requestFocus() } }
}

@Composable
private fun FolderRow(folder: VideoFolder, modifier: Modifier, onClick: () -> Unit) {
    FocusPanel(onClick = { if (folder.available) onClick() }, modifier = modifier.fillMaxWidth().height(60.dp)) {
        Row(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("📁", fontSize = 22.sp, modifier = Modifier.width(40.dp))
            Text(
                folder.name,
                style = MaterialTheme.typography.titleMedium,
                color = if (folder.available) ArrColors.Text else ArrColors.TextSecondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            if (!folder.available) Pill("Introuvable sur le NAS", ArrColors.Warning.copy(alpha = 0.25f))
            else Text("›", fontSize = 26.sp, color = ArrColors.TextSecondary)
        }
    }
}

@Composable
private fun FileRow(file: VideoFile, state: WatchState?, modifier: Modifier, onClick: () -> Unit, onLongClick: () -> Unit) {
    val watched = state?.watched == true
    val progress = state?.takeIf { !it.watched && it.total > 0 && it.position > 0 }?.let { it.position.toFloat() / it.total }
    FocusPanel(onClick = onClick, onLongClick = onLongClick, modifier = modifier.fillMaxWidth().height(72.dp)) {
        Row(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(40.dp)) {
                Text(if (watched) "✓" else "▶", fontSize = 20.sp, color = if (watched) ArrColors.Seen else ArrColors.AccentText)
            }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(file.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(VideoRules.detail(file, state), style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, maxLines = 1)
                if (progress != null) ProgressBar(progress, Modifier.fillMaxWidth(0.6f), height = 3.dp)
            }
        }
    }
}
