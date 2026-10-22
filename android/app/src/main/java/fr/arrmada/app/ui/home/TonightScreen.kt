package fr.arrmada.app.ui.home

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import fr.arrmada.app.ui.components.gutter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.TonightLogic
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import java.time.LocalDateTime

/**
 * « Ce soir » (comme l'add-on) : ce qui sera fini avant l'heure choisie.
 * Onglets « Avant 22:00 »… « Sans limite » ; chaque affiche dit « fini
 * vers 22:14 ». OK lance la lecture (reprise comprise).
 */
@Composable
fun TonightScreen(repository: Repository, absolute: (String?) -> String?, onPlay: (TonightLogic.Row) -> Unit) {
    var rows by remember { mutableStateOf<List<TonightLogic.Row>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        try {
            // coroutineScope : une requête qui échoue remonte ici (message
            // affiché) au lieu de faire tomber l'appli
            rows = coroutineScope {
                val states = async { repository.watchStates() }
                val movies = async { repository.allLibrary("movie") }
                val series = async { repository.allLibrary("series") }
                TonightLogic.candidates(states.await(), movies.await(), series.await())
            }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }
    val all = rows
    if (error != null) return MessageScreen("Ce soir indisponible", error)
    if (all == null) return MessageScreen("Chargement…")
    TonightContent(all, LocalDateTime.now(), absolute, onPlay)
}

@Composable
fun TonightContent(all: List<TonightLogic.Row>, now: LocalDateTime, absolute: (String?) -> String?, onPlay: (TonightLogic.Row) -> Unit) {
    val slots = remember(now.hour, now.minute / 30) { TonightLogic.slots(now) }
    var slot by remember { mutableIntStateOf(TonightLogic.defaultSlot(slots, now)) }
    var focused by remember { mutableStateOf<TonightLogic.Row?>(null) }
    val shown = TonightLogic.rows(all, slots[slot], now)
    val firstFocus = remember { FocusRequester() }

    KenBurnsBackdrop(url = absolute(focused?.item?.fanartUrl ?: shown.firstOrNull()?.item?.fanartUrl)) {
        Column(Modifier.fillMaxSize()) {
            ScreenHeader("Ce soir", "Ce qui sera fini avant l’heure choisie, en partant de maintenant")
            Row(Modifier.padding(top = 14.dp).horizontalScroll(rememberScrollState()).padding(horizontal = gutter), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                slots.forEachIndexed { index, s ->
                    ArrButton(s.label, { slot = index }, primary = index == slot)
                }
            }
            val current = focused?.takeIf { it in shown } ?: shown.firstOrNull()
            Text(
                current?.let { listOf(TonightLogic.status(it, now), it.subtitle, it.title).filter { p -> p.isNotBlank() }.joinToString(" · ") }
                    ?: "Rien ne tient avant ${slots[slot].label.removePrefix("Avant ")} : essaie un horaire plus tard, ou « Sans limite ».",
                style = MaterialTheme.typography.titleMedium,
                color = ArrColors.AccentText,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(start = gutter, top = 14.dp, end = gutter),
            )
            LazyVerticalGrid(
                columns = GridCells.Adaptive(108.dp),
                contentPadding = PaddingValues(horizontal = gutter, vertical = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(14.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                items(shown, key = { (it.state?.let { s -> "r:${s.mediaType}${s.id}" } ?: "f:") + (it.item?.externalId ?: it.title) }) { row ->
                    Column(Modifier.width(108.dp)) {
                        PosterCard(
                            imageUrl = absolute(row.item?.posterUrl),
                            title = row.title,
                            width = 108.dp,
                            progress = row.state?.let { s -> if (s.total > 0) s.position.toFloat() / s.total else null },
                            onClick = { onPlay(row) },
                            onFocus = { focused = row },
                            modifier = if (row == shown.first()) Modifier.focusRequester(firstFocus) else Modifier,
                        )
                        Text(
                            TonightLogic.status(row, now).substringAfterLast("fini vers ").let { if (it.length <= 6) "fini vers $it" else it },
                            style = MaterialTheme.typography.labelSmall,
                            color = ArrColors.TextSecondary,
                            maxLines = 1,
                            modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                }
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { firstFocus.requestFocus() } }
}
