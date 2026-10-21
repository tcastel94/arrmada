package fr.arrmada.app.ui.home

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
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.theme.ArrColors

/** Vue de la grille (onglet), comme les vues de la grille de l'add-on. */
private class GridView(val label: String, val apply: (List<LibraryItem>) -> List<LibraryItem>)

private val RECENT = GridView("Récents") { list -> list.sortedByDescending { it.added } }
private val TITLE = GridView("A à Z") { list -> list.sortedBy { it.title.lowercase() } }
private val YEAR = GridView("Année") { list -> list.sortedByDescending { it.year ?: 0 } }
private val FOUR_K = GridView("4K") { list -> list.filter { (it.quality ?: "").contains("2160") }.sortedByDescending { it.added } }
private val TOP_RATED = GridView("Mieux notés") { list -> list.filter { it.rating != null }.sortedByDescending { it.rating } }

/**
 * Grille « Films » ou « Séries » : mur d'affiches de 7 colonnes (comme la
 * grille de l'add-on), triée par onglet. Seuls les titres présents sur le
 * disque sont montrés : c'est ce qu'on peut regarder.
 *
 * [type] : « movie » ou « series ».
 */
@Composable
fun LibraryScreen(type: String, repository: Repository, api: Api, onOpen: (LibraryItem) -> Unit) {
    var items by remember { mutableStateOf<List<LibraryItem>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val label = if (type == "movie") "Films" else "Séries"

    LaunchedEffect(type) {
        try {
            items = repository.allLibrary(type).filter { it.hasFile }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    val all = items
    when {
        error != null -> return MessageScreen("$label indisponibles", error)
        all == null -> return MessageScreen("Chargement des ${label.lowercase()}…")
    }
    LibraryContent(label, all!!, api::absolute, onOpen)
}

/** Affichage de la grille (séparé du chargement pour les captures d'écran de test). */
@Composable
fun LibraryContent(label: String, all: List<LibraryItem>, absolute: (String?) -> String?, onOpen: (LibraryItem) -> Unit) {
    val views = if (all.firstOrNull()?.isMovie != false) listOf(RECENT, TITLE, YEAR, FOUR_K) else listOf(RECENT, TITLE, YEAR, TOP_RATED)
    var view by remember { mutableStateOf(views.first()) }
    val firstFocus = remember { FocusRequester() }
    val sorted = view.apply(all)

    Column(Modifier.fillMaxSize().background(ArrColors.Night).padding(top = 20.dp)) {
        Row(
            Modifier.padding(horizontal = 48.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(label, style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(end = 18.dp))
            views.forEach { option ->
                ArrButton(option.label, { view = option }, primary = option == view)
            }
            Text("${sorted.size} titres", style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(start = 12.dp))
        }
        PosterGrid(sorted, absolute, onOpen, Modifier, firstFocus)
    }
    LaunchedEffect(view) { runCatching { firstFocus.requestFocus() } }
}

/** Mur d'affiches de 7 colonnes (grilles, résultats de recherche). */
@Composable
fun PosterGrid(
    items: List<LibraryItem>,
    absolute: (String?) -> String?,
    onOpen: (LibraryItem) -> Unit,
    modifier: Modifier = Modifier,
    firstFocus: FocusRequester? = null,
) {
    LazyVerticalGrid(
        columns = GridCells.Fixed(7),
        contentPadding = PaddingValues(horizontal = 48.dp, vertical = 18.dp),
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
                modifier = if (firstFocus != null && item == items.first()) Modifier.focusRequester(firstFocus) else Modifier,
            )
        }
    }
}
