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

/** Tri proposé en onglets (comme les vues de la grille de l'add-on). */
private enum class Sort(val label: String) { ADDED("Récents"), TITLE("A à Z"), YEAR("Année"), FOUR_K("4K") }

/**
 * Grille « Films » : mur d'affiches de 7 colonnes (comme la grille de
 * l'add-on), triée par onglet. Seuls les films présents sur le disque sont
 * montrés : c'est ce qu'on peut regarder.
 */
@Composable
fun LibraryScreen(repository: Repository, api: Api, onOpen: (LibraryItem) -> Unit) {
    var items by remember { mutableStateOf<List<LibraryItem>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            items = repository.allLibrary("movie").filter { it.hasFile }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    val all = items
    when {
        error != null -> return MessageScreen("Films indisponibles", error)
        all == null -> return MessageScreen("Chargement des films…")
    }
    LibraryContent(all!!, api::absolute, onOpen)
}

/** Affichage de la grille (séparé du chargement pour les captures d'écran de test). */
@Composable
fun LibraryContent(all: List<LibraryItem>, absolute: (String?) -> String?, onOpen: (LibraryItem) -> Unit) {
    var sort by remember { mutableStateOf(Sort.ADDED) }
    val firstFocus = remember { FocusRequester() }
    val sorted = when (sort) {
        Sort.ADDED -> all.sortedByDescending { it.added }
        Sort.TITLE -> all.sortedBy { it.title.lowercase() }
        Sort.YEAR -> all.sortedByDescending { it.year ?: 0 }
        Sort.FOUR_K -> all.filter { (it.quality ?: "").contains("2160") }.sortedByDescending { it.added }
    }

    Column(Modifier.fillMaxSize().background(ArrColors.Night).padding(top = 20.dp)) {
        Row(
            Modifier.padding(horizontal = 48.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Films", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.padding(end = 18.dp))
            Sort.entries.forEach { option ->
                ArrButton(option.label, { sort = option }, primary = option == sort)
            }
            Text("${sorted.size} titres", style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(start = 12.dp))
        }
        LazyVerticalGrid(
            columns = GridCells.Fixed(7),
            contentPadding = PaddingValues(horizontal = 48.dp, vertical = 18.dp),
            horizontalArrangement = Arrangement.spacedBy(14.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            items(sorted, key = { it.externalId }) { item ->
                PosterCard(
                    imageUrl = absolute(item.posterUrl),
                    title = item.title,
                    width = 108.dp,
                    onClick = { onOpen(item) },
                    modifier = if (item == sorted.first()) Modifier.focusRequester(firstFocus) else Modifier,
                )
            }
        }
    }
    LaunchedEffect(sort) { runCatching { firstFocus.requestFocus() } }
}
