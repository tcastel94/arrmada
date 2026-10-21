package fr.arrmada.app.ui.home

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.data.Api
import fr.arrmada.app.data.CalendarEntry
import fr.arrmada.app.data.LibraryItem
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.ResumeEntry
import fr.arrmada.app.data.TmdbItem
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ContentRow
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.LandscapeCard
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/** Ce que le héros (haut de l'écran) montre de l'élément sélectionné. */
data class Hero(
    val backdrop: String?,
    val logo: String?,
    val title: String,
    val meta: String,
    val overview: String?,
    val note: String? = null,
)

data class HomeState(
    val loading: Boolean = true,
    val error: String? = null,
    val resume: List<ResumeEntry> = emptyList(),
    val recent: List<LibraryItem> = emptyList(),
    val forYou: List<TmdbItem> = emptyList(),
    val upcoming: List<CalendarEntry> = emptyList(),
)

/**
 * Données de l'accueil. Les rangées sont chargées en parallèle et
 * indépendamment : une rangée en erreur (TMDB absent…) n'empêche pas les
 * autres de s'afficher, comme les flux en cache de l'add-on.
 */
class HomeViewModel(private val repository: Repository) : ViewModel() {

    private val _state = MutableStateFlow(HomeState())
    val state: StateFlow<HomeState> = _state

    init {
        load()
    }

    fun load() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            val recent = async { runCatching { repository.recent() } }
            val forYou = async { runCatching { repository.recommendations() } }
            val upcoming = async { runCatching { repository.upcoming() } }
            val resume = async {
                runCatching {
                    val states = repository.watchStates()
                    val movies = async { repository.allLibrary("movie") }
                    val series = async { repository.allLibrary("series") }
                    repository.resumeRow(states, movies.await(), series.await())
                }
            }
            val recentItems = recent.await()
            val recos = forYou.await().getOrNull()
            _state.value = HomeState(
                loading = false,
                // Erreur bloquante seulement si même la médiathèque ne répond pas
                error = recentItems.exceptionOrNull()?.message,
                resume = resume.await().getOrDefault(emptyList()),
                recent = recentItems.getOrDefault(emptyList()),
                forYou = recos?.let { r ->
                    (r.trendingMovies + r.becauseYouHave.flatMap { it.recommendations })
                        .filter { !it.inLibrary }
                        .distinctBy { it.tmdbId }
                        .take(20)
                } ?: emptyList(),
                upcoming = upcoming.await().getOrNull()?.items.orEmpty().take(20),
            )
        }
    }
}

/**
 * Ce que l'accueil peut demander à la navigation. [go] reçoit le nom d'un
 * écran du menu : « movies », « series », « discover », « search », « settings ».
 */
class HomeActions(
    val open: (LibraryItem) -> Unit = {}, // fiche film ou écran Série
    val openMovieId: (Int) -> Unit = {}, // fiche film par identifiant Radarr
    val openSeriesId: (Int) -> Unit = {}, // écran Série par identifiant Sonarr
    val resume: (ResumeEntry) -> Unit = {},
    val request: (TmdbItem) -> Unit = {}, // titre absent : feuille « Télécharger »
    val go: (String) -> Unit = {},
    val prefetch: (LibraryItem) -> Unit = {}, // carte survolée : fiche préchargée
    // Profil qui regarde (ADR-008), à droite du menu ; null : pas de profils dans la maison
    val viewer: fr.arrmada.app.data.FamilyProfile? = null,
)

@Composable
fun HomeScreen(viewModel: HomeViewModel, api: Api, actions: HomeActions) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    HomeContent(state, api::absolute, viewModel::load, actions)
}

/** Menu du haut, commun à l'accueil et aux grilles (comme la coquille de l'add-on). */
val TOP_MENU = listOf(
    "home" to "Accueil", "movies" to "Films", "series" to "Séries", "tonight" to "Ce soir",
    "apps" to "Applis", "discover" to "Découvrir", "search" to "Rechercher", "queue" to "Téléchargements",
    "board" to "Tableau de bord", "settings" to "Réglages",
)

/** Affichage de l'accueil à partir d'un état (séparé pour les captures d'écran de test). */
@Composable
fun HomeContent(state: HomeState, absolute: (String?) -> String?, onRetry: () -> Unit, actions: HomeActions) {
    var hero by remember { mutableStateOf<Hero?>(null) }
    val firstFocus = remember { FocusRequester() }

    if (state.loading && state.recent.isEmpty()) {
        MessageScreen("Chargement…")
        return
    }
    if (state.error != null && state.recent.isEmpty() && state.resume.isEmpty()) {
        MessageScreen("Serveur ArrMada injoignable", state.error, "Réessayer", onRetry)
        return
    }

    // Héros par défaut : le premier titre à reprendre, sinon le dernier ajout
    val shown = hero ?: state.resume.firstOrNull()?.let { heroOf(it, absolute) } ?: state.recent.firstOrNull()?.let { heroOf(it, absolute) }

    KenBurnsBackdrop(url = shown?.backdrop) {
        Column(Modifier.fillMaxSize()) {
            // ── Menu du haut (comme la coquille de l'add-on) ──
            // Défile si besoin : l'entrée qui prend le focus est toujours amenée à l'écran
            Row(
                Modifier.padding(top = 20.dp).horizontalScroll(rememberScrollState()).padding(horizontal = 48.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TOP_MENU.forEach { (route, label) ->
                    ArrButton(label, { if (route != "home") actions.go(route) }, primary = route == "home", compact = true)
                }
                actions.viewer?.let { viewer -> ViewerChip(viewer) { actions.go("profiles") } }
            }

            // ── Héros : l'élément sélectionné ──
            AnimatedContent(
                targetState = shown,
                transitionSpec = { fadeIn(tween(320)) togetherWith fadeOut(tween(200)) },
                label = "hero",
                modifier = Modifier.padding(start = 48.dp, top = 22.dp).height(178.dp),
            ) { current ->
                if (current != null) HeroBlock(current)
            }

            // ── Rangées ──
            LazyColumn(
                contentPadding = PaddingValues(bottom = 40.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                item {
                    ContentRow("Reprendre", state.resume, key = { it.state.mediaType + it.state.id + it.state.season + it.state.episode }) { entry ->
                        LandscapeCard(
                            imageUrl = absolute(entry.item?.fanartUrl ?: entry.item?.posterUrl),
                            title = entry.title,
                            subtitle = entry.subtitle,
                            progress = entry.progress,
                            onClick = { actions.resume(entry) },
                            onFocus = { hero = heroOf(entry, absolute) },
                            modifier = if (entry == state.resume.first()) Modifier.focusRequester(firstFocus) else Modifier,
                        )
                    }
                }
                item {
                    ContentRow("Ajouts récents", state.recent, key = { it.type + it.externalId }) { item ->
                        PosterCard(
                            imageUrl = absolute(item.posterUrl),
                            title = item.title,
                            onClick = { actions.open(item) },
                            onFocus = {
                                hero = heroOf(item, absolute)
                                actions.prefetch(item)
                            },
                            modifier = if (state.resume.isEmpty() && item == state.recent.first()) Modifier.focusRequester(firstFocus) else Modifier,
                        )
                    }
                }
                item {
                    ContentRow("Pour toi", state.forYou, key = { "t" + it.tmdbId }) { item ->
                        PosterCard(
                            imageUrl = item.posterUrl,
                            title = item.title,
                            onClick = { actions.request(item) },
                            onFocus = { hero = heroOf(item) },
                        )
                    }
                }
                item {
                    ContentRow("Bientôt", state.upcoming, key = { it.id }) { entry ->
                        PosterCard(
                            imageUrl = absolute(entry.posterUrl),
                            title = entry.title,
                            onClick = {
                                entry.movieId?.let(actions.openMovieId) ?: entry.seriesId?.let(actions.openSeriesId)
                            },
                            onFocus = { hero = heroOf(entry, absolute) },
                        )
                    }
                }
            }
        }
    }

    // Focus de départ sur la première carte (sinon la télécommande ne « voit » rien)
    LaunchedEffect(state.resume.isNotEmpty() || state.recent.isNotEmpty()) {
        runCatching { firstFocus.requestFocus() }
    }
}

@Composable
fun HeroBlock(hero: Hero) {
    Column(Modifier.widthIn(max = 520.dp)) {
        if (hero.logo != null) {
            AsyncImage(
                model = hero.logo,
                contentDescription = hero.title,
                contentScale = ContentScale.Fit,
                alignment = Alignment.CenterStart,
                modifier = Modifier.heightIn(max = 64.dp).widthIn(max = 280.dp),
            )
        } else {
            Text(hero.title, style = MaterialTheme.typography.displayMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        if (hero.meta.isNotBlank()) {
            Text(hero.meta, style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 8.dp))
        }
        if (hero.note != null) {
            Text(hero.note, style = MaterialTheme.typography.labelLarge, color = ArrColors.AccentText, modifier = Modifier.padding(top = 4.dp))
        }
        if (!hero.overview.isNullOrBlank()) {
            Text(
                hero.overview,
                style = MaterialTheme.typography.bodyMedium,
                color = ArrColors.TextSecondary,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }
}

private fun meta(vararg parts: Any?): String = parts.filterNotNull().map { it.toString() }.filter { it.isNotBlank() }.joinToString("  ·  ")

private fun heroOf(item: LibraryItem, absolute: (String?) -> String?) = Hero(
    backdrop = absolute(item.fanartUrl ?: item.posterUrl),
    logo = absolute(item.clearlogoUrl),
    title = item.title,
    meta = meta(item.year, item.genres.take(2).joinToString(", ").ifBlank { null }, item.runtime?.let { "$it min" }, item.rating?.let { "★ %.1f".format(it) }),
    overview = item.overview,
)

private fun heroOf(entry: ResumeEntry, absolute: (String?) -> String?) = Hero(
    backdrop = absolute(entry.item?.fanartUrl ?: entry.item?.posterUrl),
    logo = absolute(entry.item?.clearlogoUrl),
    title = entry.title,
    meta = meta(entry.item?.year, entry.item?.genres?.take(2)?.joinToString(", ")?.ifBlank { null }),
    overview = entry.item?.overview,
    note = if (entry.isEpisode) entry.subtitle + "  ·  reprendre à " + formatClock(entry.state.position.toLong()) else entry.subtitle,
)

fun heroOf(item: TmdbItem) = Hero(
    backdrop = item.backdropUrl,
    logo = null,
    title = item.title,
    meta = meta(item.year, item.rating?.let { "★ %.1f".format(it) }),
    overview = item.overview,
    note = if (item.inLibrary) "Dans la médiathèque" else "Pas encore dans la médiathèque",
)

private fun heroOf(entry: CalendarEntry, absolute: (String?) -> String?) = Hero(
    backdrop = absolute(entry.posterUrl),
    logo = null,
    title = entry.title,
    meta = meta(entry.label, entry.subtitle.ifBlank { null }),
    overview = entry.overview,
    note = entry.airDate?.take(10)?.let { "Sortie le " + it.split("-").reversed().joinToString("/") },
)

/** Avatar et nom du profil qui regarde : OK ramène à « Qui regarde ? ». */
@Composable
private fun ViewerChip(viewer: fr.arrmada.app.data.FamilyProfile, onClick: () -> Unit) {
    androidx.tv.material3.Surface(
        onClick = onClick,
        modifier = Modifier.height(34.dp),
        shape = androidx.tv.material3.ClickableSurfaceDefaults.shape(RoundedCornerShape(17.dp)),
        scale = androidx.tv.material3.ClickableSurfaceDefaults.scale(focusedScale = 1.06f),
        colors = androidx.tv.material3.ClickableSurfaceDefaults.colors(
            containerColor = Color(0x26FFFFFF),
            contentColor = ArrColors.Text,
            focusedContainerColor = ArrColors.Accent,
            focusedContentColor = ArrColors.Night,
        ),
    ) {
        Row(
            Modifier.padding(start = 4.dp, end = 12.dp).fillMaxHeight(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            fr.arrmada.app.ui.profiles.ProfileAvatar(viewer, 26.dp)
            Text(viewer.name, style = MaterialTheme.typography.labelLarge, maxLines = 1)
        }
    }
}
