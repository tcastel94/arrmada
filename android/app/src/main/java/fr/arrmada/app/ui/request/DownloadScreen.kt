package fr.arrmada.app.ui.request

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import fr.arrmada.app.ui.components.AdaptiveRow
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.tapToClick
import android.widget.Toast
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import fr.arrmada.app.data.DownloadLogic
import fr.arrmada.app.data.DownloadTarget
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.Scope
import fr.arrmada.app.data.SeasonsInfo
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.Glass
import fr.arrmada.app.ui.components.GlassEdge
import fr.arrmada.app.ui.components.GlassStrong
import fr.arrmada.app.ui.components.Ink
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch

/**
 * Feuille « Télécharger » (celle de l'add-on, ADR-005) : un film part d'un
 * seul bouton ; pour une série on choisit la portée (toute la série, une
 * saison, des épisodes précis). « Pour ce soir » fait passer la demande
 * devant les autres téléchargements. Le serveur ajoute le titre si besoin
 * et répond tout de suite ; une notification prévient quand c'est prêt.
 */
@Composable
fun DownloadScreen(target: DownloadTarget, repository: Repository, absolute: (String?) -> String?, onDone: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var current by remember { mutableStateOf(target) }
    val seasons = remember { mutableStateMapOf<Int, SeasonsInfo>() } // saison → épisodes (cache)
    var overview by remember { mutableStateOf<SeasonsInfo?>(null) } // premier chargement (liste des saisons)
    var loadError by remember { mutableStateOf<String?>(null) }
    var sending by remember { mutableStateOf(false) }

    // Série : liste des saisons et saison proposée par le serveur
    LaunchedEffect(target) {
        if (target.isMovie) return@LaunchedEffect
        val info = runCatching { repository.seasons(target.title, target.tmdbId, target.tvdbId) }
            .getOrElse { SeasonsInfo(status = "error", message = it.message) }
        if (info.status != "ok") {
            loadError = info.message ?: "Saisons indisponibles"
            return@LaunchedEffect
        }
        overview = info
        info.season?.let { seasons[it] = info }
        // Les identifiants trouvés par le serveur servent pour la demande
        current = current.copy(
            tvdbId = current.tvdbId ?: info.tvdbId,
            tmdbId = current.tmdbId ?: info.tmdbId,
            arrId = current.arrId ?: info.arrId,
            inLibrary = current.inLibrary || info.inLibrary,
        )
    }

    fun send(selection: Selection) {
        if (sending) return
        sending = true
        scope.launch {
            val request = DownloadLogic.request(current, selection.scope, selection.season, selection.ticked, selection.tonight)
            val result = runCatching { repository.download(request) }
            sending = false
            val ok = result.getOrNull()?.ok == true
            val message = result.getOrNull()?.message ?: result.exceptionOrNull()?.message
                ?: if (ok) "C’est parti" else "Échec de la demande"
            Toast.makeText(context, message, Toast.LENGTH_LONG).show()
            if (ok) onDone()
        }
    }

    DownloadContent(
        target = current,
        overview = overview,
        loadError = loadError,
        episodesOf = { season -> seasons[season] },
        onLoadSeason = { season ->
            if (season !in seasons) {
                scope.launch {
                    runCatching { repository.seasons(current.title, current.tmdbId, current.tvdbId, season) }
                        .getOrNull()?.takeIf { it.status == "ok" }?.let { seasons[season] = it }
                }
            }
        },
        sending = sending,
        absolute = absolute,
        onSend = ::send,
        onCancel = onDone,
    )
}

/** Ce qui est coché dans la feuille au moment d'envoyer. */
data class Selection(val scope: Scope, val season: Int?, val ticked: List<Int>, val tonight: Boolean)

/** Affichage de la feuille (séparé du chargement pour les captures d'écran de test). */
@Composable
fun DownloadContent(
    target: DownloadTarget,
    overview: SeasonsInfo?,
    loadError: String?,
    episodesOf: (Int) -> SeasonsInfo?,
    onLoadSeason: (Int) -> Unit,
    sending: Boolean,
    absolute: (String?) -> String?,
    onSend: (Selection) -> Unit,
    onCancel: () -> Unit,
) {
    val context = LocalContext.current
    var scopeChoice by remember { mutableStateOf(Scope.SEASON) }
    var season by remember(overview) { mutableStateOf(overview?.season) }
    val ticked = remember { mutableStateListOf<Int>() }
    var tonight by remember { mutableStateOf(true) }
    val mainFocus = remember { FocusRequester() }

    BackHandler(onBack = onCancel)

    val label = DownloadLogic.buttonLabel(target, scopeChoice, season, ticked)
    val ready = DownloadLogic.ready(target, scopeChoice, season, ticked)

    KenBurnsBackdrop(url = absolute(target.fanart ?: target.poster)) {
        Box(Modifier.fillMaxSize().background(Color(0x990A0E16)))
        // Téléphone : le titre au-dessus de la demande, le tout défile
        AdaptiveRow(Modifier.fillMaxSize().padding(horizontal = gutter, vertical = 30.dp), spacing = 32.dp) { share ->
            // ── Le titre ──
            Column(Modifier.width(200.dp)) {
                ArtImage(absolute(target.poster), target.title, Modifier.width(150.dp).height(225.dp).clip(RoundedCornerShape(8.dp)))
                Text(target.title, style = MaterialTheme.typography.titleLarge, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 12.dp))
                Text(
                    listOfNotNull(target.year?.toString(), if (target.isMovie) "Film" else "Série").joinToString(" · "),
                    style = MaterialTheme.typography.labelLarge,
                    color = ArrColors.TextSecondary,
                )
                Text(
                    if (target.inLibrary) "Déjà dans la médiathèque" else "Pas encore dans la médiathèque",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (target.inLibrary) ArrColors.Seen else ArrColors.AccentText,
                    modifier = Modifier.padding(top = 6.dp),
                )
                Text(
                    target.overview.orEmpty(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = ArrColors.TextSecondary,
                    maxLines = 6,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 8.dp),
                )
            }

            // ── La demande ──
            Column(share.of(1f)) {
                Text(
                    if (target.isMovie) "Prêt à télécharger" else "Que veux-tu télécharger ?",
                    style = MaterialTheme.typography.headlineMedium,
                )
                if (target.isMovie) {
                    listOf(
                        "Le film est ajouté avec ta qualité habituelle, puis téléchargé.",
                        "Les sous-titres français arrivent avec lui.",
                        "Une notification te prévient sur cette TV.",
                    ).forEach {
                        Text(it, style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 8.dp))
                    }
                } else {
                    // Portée
                    Row(Modifier.padding(top = 14.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        Scope.entries.forEachIndexed { i, option ->
                            Chip(
                                title = option.label,
                                subtitle = when (option) {
                                    Scope.SERIES -> overview?.seasons?.takeIf { it.isNotEmpty() }?.let { s -> "${s.size} saisons · ${s.sumOf { it.episodes }} épisodes" } ?: "tout ce qui existe"
                                    Scope.SEASON -> "au choix"
                                    Scope.EPISODE -> "précis"
                                },
                                selected = option == scopeChoice,
                                onClick = { scopeChoice = option; ticked.clear() },
                                modifier = if (i == 0) Modifier.focusRequester(mainFocus) else Modifier,
                            )
                        }
                    }
                    when {
                        loadError != null -> {
                            Text("Saisons indisponibles : $loadError", style = MaterialTheme.typography.bodyLarge, color = ArrColors.Error, modifier = Modifier.padding(top = 14.dp))
                            Text("Tu peux quand même demander toute la série.", style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary)
                        }
                        overview == null -> Text("Chargement des saisons…", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 14.dp))
                        scopeChoice != Scope.SERIES -> {
                            // Saisons
                            LazyRow(contentPadding = PaddingValues(vertical = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                items(overview.seasons, key = { it.number }) { count ->
                                    Chip(
                                        title = "Saison ${count.number}",
                                        subtitle = DownloadLogic.seasonSubtitle(count),
                                        selected = count.number == season,
                                        onClick = { season = count.number; ticked.clear(); onLoadSeason(count.number) },
                                    )
                                }
                            }
                            // Épisodes (cochables en portée « Un épisode »)
                            val episodes = season?.let(episodesOf)?.episodes
                            if (episodes == null) {
                                Text("Chargement des épisodes…", style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary)
                            } else if (episodes.isEmpty()) {
                                Text(
                                    if (overview.source == "sonarr") "Épisodes connus une fois la série ajoutée : choisis la saison entière."
                                    else "Aucun épisode pour cette saison.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = ArrColors.TextSecondary,
                                )
                            } else {
                                LazyColumn(Modifier.height(150.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    items(episodes, key = { it.number }) { ep ->
                                        EpisodeLine(
                                            code = "S%02dE%02d".format(ep.season, ep.number),
                                            title = ep.title?.takeIf { it.isNotBlank() } ?: "Épisode ${ep.number}",
                                            state = DownloadLogic.episodeState(ep),
                                            checkable = scopeChoice == Scope.EPISODE,
                                            checked = ep.number in ticked,
                                            onClick = {
                                                if (scopeChoice == Scope.EPISODE) {
                                                    if (ep.number in ticked) ticked.remove(ep.number) else ticked.add(ep.number)
                                                }
                                            },
                                        )
                                    }
                                }
                            }
                        }
                    }
                    Text(
                        when (scopeChoice) {
                            Scope.SERIES -> "Toutes les saisons, au fur et à mesure de leur sortie."
                            Scope.SEASON -> "Toute la saison choisie (OK sur une pastille pour en changer)."
                            Scope.EPISODE -> "OK sur un épisode pour le cocher, plusieurs possibles."
                        },
                        style = MaterialTheme.typography.labelMedium,
                        color = ArrColors.TextSecondary,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }

                Spacer(Modifier.weight(1f))
                // « Pour ce soir » + bouton principal
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Chip(
                        title = if (tonight) "Pour ce soir : oui" else "Pour ce soir : non",
                        subtitle = if (tonight) "Passe devant les autres téléchargements" else "Rejoint la file normale",
                        selected = tonight,
                        onClick = { tonight = !tonight },
                    )
                    ArrButton(
                        if (sending) "Envoi…" else label,
                        {
                            when {
                                sending -> Unit
                                !ready -> Toast.makeText(context, label, Toast.LENGTH_SHORT).show()
                                else -> onSend(Selection(scopeChoice, season, ticked.toList(), tonight))
                            }
                        },
                        primary = true,
                        modifier = if (target.isMovie) Modifier.focusRequester(mainFocus) else Modifier,
                    )
                    ArrButton("Annuler", onCancel)
                }
            }
        }
    }
    LaunchedEffect(target.isMovie) { runCatching { mainFocus.requestFocus() } }
}

/** Pastille à deux lignes (portée, saison, « Pour ce soir »). */
@Composable
private fun Chip(title: String, subtitle: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    // Choix actuel : verre plus clair + liseré (comme un réglage choisi) ; focus blanc
    val shape = RoundedCornerShape(14.dp)
    Surface(
        onClick = onClick,
        modifier = modifier.height(50.dp).widthIn(min = 120.dp).tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(shape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.05f),
        border = ClickableSurfaceDefaults.border(
            border = if (selected) Border(BorderStroke(1.dp, GlassEdge), shape = shape) else Border.None,
        ),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) GlassStrong else Glass,
            contentColor = Color.White,
            focusedContainerColor = Color.White,
            focusedContentColor = Ink,
        ),
    ) {
        Column(Modifier.fillMaxHeight().padding(horizontal = 14.dp), verticalArrangement = Arrangement.Center) {
            Text(title, style = MaterialTheme.typography.labelLarge, maxLines = 1)
            if (subtitle.isNotBlank()) Text(subtitle, style = MaterialTheme.typography.labelSmall, maxLines = 1)
        }
    }
}

/** Ligne d'épisode : case à cocher (portée « Un épisode »), code, titre, état. */
@Composable
private fun EpisodeLine(code: String, title: String, state: String, checkable: Boolean, checked: Boolean, onClick: () -> Unit) {
    val shape = RoundedCornerShape(6.dp)
    Surface(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().height(34.dp).tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(shape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.01f),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = Color(0x14FFFFFF),
            contentColor = if (checkable) ArrColors.Text else ArrColors.TextSecondary,
            focusedContainerColor = Color.White,
            focusedContentColor = Ink,
        ),
    ) {
        Row(Modifier.fillMaxSize().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            if (checkable) {
                Box(
                    Modifier.size(14.dp).clip(CircleShape)
                        .background(if (checked) ArrColors.Seen else Color(0x33FFFFFF))
                )
            }
            Text(code, style = MaterialTheme.typography.labelLarge)
            Text(title, style = MaterialTheme.typography.bodyMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
            Text(state, style = MaterialTheme.typography.labelMedium)
        }
    }
}
