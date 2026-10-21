package fr.arrmada.app.ui.home

import fr.arrmada.app.ui.components.gutter
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Recommendations
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.TmdbItem
import fr.arrmada.app.ui.components.ContentRow
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.theme.ArrColors

/**
 * « Découvrir » (comme l'onglet de l'add-on) : tendances TMDB et « Parce que
 * tu as… ». OK sur un titre déjà présent : sa fiche ; sinon : la feuille
 * « Télécharger ».
 */
@Composable
fun DiscoverScreen(repository: Repository, onOpen: (TmdbItem) -> Unit) {
    var recos by remember { mutableStateOf<Recommendations?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        runCatching { repository.recommendations() }
            .onSuccess { recos = it }
            .onFailure { error = it.message ?: "Serveur injoignable" }
    }
    val r = recos
    if (error != null) return MessageScreen("Découvrir indisponible", error)
    if (r == null) return MessageScreen("Chargement…")
    DiscoverContent(r, onOpen)
}

/** Affichage de « Découvrir » (séparé du chargement pour les captures d'écran de test). */
@Composable
fun DiscoverContent(recos: Recommendations, onOpen: (TmdbItem) -> Unit) {
    val rows = buildList {
        add("Films du moment" to recos.trendingMovies)
        add("Séries du moment" to recos.trendingSeries)
        recos.becauseYouHave.forEach { add("Parce que tu as « ${it.baseTitle} »" to it.recommendations) }
    }.filter { it.second.isNotEmpty() }
    var hero by remember { mutableStateOf(rows.firstOrNull()?.second?.firstOrNull()?.let { heroOf(it) }) }
    val firstFocus = remember { FocusRequester() }

    if (rows.isEmpty()) {
        return MessageScreen("Rien à découvrir", "Les recommandations demandent une clé TMDB dans les réglages du serveur.")
    }

    KenBurnsBackdrop(url = hero?.backdrop) {
        Column(Modifier.fillMaxSize()) {
            Text("Découvrir", style = MaterialTheme.typography.headlineMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(start = gutter, top = 22.dp))
            AnimatedContent(
                targetState = hero,
                transitionSpec = { fadeIn(tween(320)) togetherWith fadeOut(tween(200)) },
                label = "hero",
                modifier = Modifier.padding(start = gutter, top = 12.dp).height(170.dp),
            ) { current -> if (current != null) HeroBlock(current) }
            LazyColumn(
                contentPadding = PaddingValues(bottom = 40.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                rows.forEachIndexed { index, (title, items) ->
                    item(key = title) {
                        ContentRow(title, items, key = { "${it.type}${it.tmdbId}" }) { item ->
                            PosterCard(
                                imageUrl = item.posterUrl,
                                title = item.title,
                                onClick = { onOpen(item) },
                                onFocus = { hero = heroOf(item) },
                                modifier = if (index == 0 && item == items.first()) Modifier.focusRequester(firstFocus) else Modifier,
                            )
                        }
                    }
                }
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { firstFocus.requestFocus() } }
}
