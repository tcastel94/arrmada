package fr.arrmada.app.ui.home

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import fr.arrmada.app.ui.components.gutter
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Api
import fr.arrmada.app.data.LibraryItem
import fr.arrmada.app.data.LocalSeriesLogic
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.Saga
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.sagas.SagaGrid
import fr.arrmada.app.ui.theme.ArrColors

/** Vue de la grille (onglet), comme les vues de la grille de l'add-on. */
private class GridView(val label: String, val apply: (List<LibraryItem>) -> List<LibraryItem>)

private val RECENT = GridView("Récents") { list -> list.sortedByDescending { it.added } }
private val TITLE = GridView("A à Z") { list -> list.sortedBy { it.title.lowercase() } }
private val YEAR = GridView("Année") { list -> list.sortedByDescending { it.year ?: 0 } }
private val FOUR_K = GridView("4K") { list -> list.filter { (it.quality ?: "").contains("2160") }.sortedByDescending { it.added } }
private val TOP_RATED = GridView("Mieux notés") { list -> list.filter { it.rating != null }.sortedByDescending { it.rating } }

/** Vue « Sagas » de l'écran Films (ADR-016) : une grille de sagas à la place des affiches. */
private val SAGAS = GridView("Sagas") { list -> list }

/**
 * Grille « Films » ou « Séries » : mur d'affiches de 7 colonnes (comme la
 * grille de l'add-on), triée par onglet. Seuls les titres présents sur le
 * disque sont montrés : c'est ce qu'on peut regarder.
 *
 * [type] : « movie » ou « series ».
 */
@Composable
fun LibraryScreen(
    type: String,
    repository: Repository,
    api: Api,
    onOpen: (LibraryItem) -> Unit,
    onFocusItem: (LibraryItem) -> Unit = {},
    onMenu: (LibraryItem) -> Unit = {}, // appui long : menu du titre
    onSaga: ((Saga) -> Unit)? = null, // films : ouvre une saga de la vue « Sagas »
) {
    var items by remember { mutableStateOf<List<LibraryItem>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val label = if (type == "movie") "Films" else "Séries"
    // Gardés avec l'écran (ici, composés tout de suite, même pendant le
    // chargement) : au retour d'une saga, on retrouve la vue « Sagas » et
    // le focus sur la saga d'où l'on vient
    var viewLabel by rememberSaveable(type) { mutableStateOf<String?>(null) }
    var sagaFocus by rememberSaveable { mutableStateOf(-1) }

    LaunchedEffect(type) {
        try {
            // Grille Séries : les séries maison (Naruto Kai, One Pace…) s'ajoutent aux séries Sonarr
            val local = if (type == "series") {
                runCatching { repository.localSeries() }.getOrDefault(emptyList()).map(LocalSeriesLogic::libraryItem)
            } else {
                emptyList()
            }
            items = (repository.allLibrary(type) + local).filter { it.hasFile }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    val all = items
    when {
        error != null -> return MessageScreen("$label indisponibles", error)
        all == null -> return MessageScreen("Chargement des ${label.lowercase()}…")
    }
    // Films : vue « Sagas » en plus (grille des sagas à la place des affiches)
    val sagaGrid: (@Composable () -> Unit)? = if (type == "movie" && onSaga != null) {
        @Composable { SagaGrid(repository, onSaga, focusedId = sagaFocus, onFocused = { sagaFocus = it }) }
    } else {
        null
    }
    LibraryContent(label, all!!, api::absolute, onOpen, onFocusItem, onMenu, sagaGrid, view = viewLabel, onView = { viewLabel = it })
}

/** Affichage de la grille (séparé du chargement pour les captures d'écran de test). */
@Composable
fun LibraryContent(
    label: String,
    all: List<LibraryItem>,
    absolute: (String?) -> String?,
    onOpen: (LibraryItem) -> Unit,
    onFocusItem: (LibraryItem) -> Unit = {},
    onMenu: ((LibraryItem) -> Unit)? = null,
    sagaGrid: (@Composable () -> Unit)? = null, // vue « Sagas » (films) : remplace le mur d'affiches
    view: String? = null, // vue choisie, gardée par l'appelant (null : la première)
    onView: (String) -> Unit = {},
) {
    val base = if (all.firstOrNull()?.isMovie != false) listOf(RECENT, TITLE, YEAR, FOUR_K) else listOf(RECENT, TITLE, YEAR, TOP_RATED)
    val views = if (sagaGrid != null) base + SAGAS else base
    var localView by remember { mutableStateOf(views.first().label) }
    val viewLabel = view ?: localView
    val current = views.firstOrNull { it.label == viewLabel } ?: views.first()
    val showSagas = current == SAGAS && sagaGrid != null
    val firstFocus = remember { FocusRequester() }
    val sorted = current.apply(all)

    Column(Modifier.fillMaxSize().background(ArrColors.Night).padding(top = 20.dp)) {
        Row(
            Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = gutter),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(end = 18.dp))
            views.forEach { option ->
                ArrButton(option.label, { localView = option.label; onView(option.label) }, primary = option == current)
            }
            if (!showSagas) {
                Text("${sorted.size} titres", style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(start = 12.dp))
            }
        }
        if (showSagas) {
            sagaGrid?.invoke() // la grille des sagas place elle-même le focus
        } else {
            PosterGrid(sorted, absolute, onOpen, Modifier, firstFocus, onFocusItem, onMenu)
        }
    }
    LaunchedEffect(current) { if (!showSagas) runCatching { firstFocus.requestFocus() } }
}

/** Mur d'affiches de 7 colonnes (grilles, résultats de recherche). */
@Composable
fun PosterGrid(
    items: List<LibraryItem>,
    absolute: (String?) -> String?,
    onOpen: (LibraryItem) -> Unit,
    modifier: Modifier = Modifier,
    firstFocus: FocusRequester? = null,
    onFocusItem: (LibraryItem) -> Unit = {},
    onMenu: ((LibraryItem) -> Unit)? = null,
) {
    LazyVerticalGrid(
        // 7 colonnes à la TV, 3 sur un téléphone (largeur mini d'une affiche)
        columns = GridCells.Adaptive(108.dp),
        contentPadding = PaddingValues(horizontal = gutter, vertical = 18.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
        modifier = modifier,
    ) {
        items(items, key = { it.type + it.externalId }) { item ->
            PosterCard(
                imageUrl = absolute(item.posterUrl),
                title = item.title,
                width = 108.dp,
                onClick = { onOpen(item) },
                onFocus = { onFocusItem(item) },
                onLongClick = onMenu?.let { menu -> { menu(item) } },
                modifier = if (firstFocus != null && item == items.first()) Modifier.focusRequester(firstFocus) else Modifier,
            )
        }
    }
}
