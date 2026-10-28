package fr.arrmada.app.ui.detail

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.data.CreditOpen
import fr.arrmada.app.data.FilmCredit
import fr.arrmada.app.data.Filmography
import fr.arrmada.app.data.PersonLogic
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ContentRow
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.theme.ArrColors

/**
 * Page d'un acteur (clic sur la distribution d'une fiche), comme dans la web
 * app : photo, biographie, puis sa filmographie en deux rangées. « Dans ta
 * médiathèque » : OK ouvre la fiche du film. « À découvrir » : OK ouvre la
 * feuille « Télécharger ».
 */
@Composable
fun PersonScreen(personId: Long, repository: Repository, onOpen: (CreditOpen) -> Unit) {
    var data by remember { mutableStateOf<Filmography?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(personId) {
        runCatching { repository.person(personId) }
            .onSuccess { found -> if (found.person == null) error = found.error ?: "Acteur introuvable" else data = found }
            .onFailure { error = it.message ?: "Serveur injoignable" }
    }
    val d = data
    if (error != null) return MessageScreen("Filmographie indisponible", error)
    if (d == null) return MessageScreen("Chargement…")
    PersonContent(d, onOpen)
}

/** Affichage de la page (séparé du chargement pour les captures d'écran de test). */
@Composable
fun PersonContent(data: Filmography, onOpen: (CreditOpen) -> Unit) {
    val person = data.person ?: return MessageScreen("Acteur introuvable")
    val rows = listOf(
        "Dans ta médiathèque (${data.inLibrary.size})" to data.inLibrary,
        "À découvrir" to data.discover,
    ).filter { it.second.isNotEmpty() }
    var focused by remember { mutableStateOf(rows.firstOrNull()?.second?.firstOrNull()) }
    val firstFocus = remember { FocusRequester() }
    val phone = LocalScreen.current.isPhone

    Box(Modifier.fillMaxSize().background(ArrColors.Night)) {
        Column(Modifier.fillMaxSize()) {
            // ── Photo, nom, naissance, biographie ──
            Row(Modifier.padding(start = gutter, end = gutter, top = 28.dp), verticalAlignment = Alignment.Top) {
                Box(Modifier.size(if (phone) 84.dp else 112.dp).clip(CircleShape).background(ArrColors.Card)) {
                    if (person.photo != null) {
                        AsyncImage(model = person.photo, contentDescription = person.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                    }
                }
                Column(Modifier.padding(start = 20.dp).widthIn(max = 720.dp)) {
                    Text(person.name, style = MaterialTheme.typography.headlineMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    val meta = PersonLogic.meta(person)
                    if (meta.isNotBlank()) {
                        Text(meta, style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 4.dp))
                    }
                    if (person.biography.isNotBlank()) {
                        Text(
                            person.biography,
                            style = MaterialTheme.typography.bodyMedium,
                            color = ArrColors.TextSecondary,
                            maxLines = if (phone) 3 else 4,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.padding(top = 8.dp),
                        )
                    }
                }
            }

            // ── Film survolé ──
            AnimatedContent(
                targetState = focused,
                transitionSpec = { fadeIn(tween(240)) togetherWith fadeOut(tween(160)) },
                label = "credit",
                modifier = Modifier.padding(start = gutter, top = 14.dp).height(46.dp),
            ) { credit ->
                if (credit != null) {
                    Column {
                        Text(credit.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(PersonLogic.subtitle(credit), style = MaterialTheme.typography.labelMedium, color = ArrColors.AccentText, maxLines = 1)
                    }
                }
            }

            if (rows.isEmpty()) {
                Text("Aucun film connu pour cette personne.", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(start = gutter, top = 12.dp))
            }

            // ── Filmographie ──
            LazyColumn(
                contentPadding = PaddingValues(bottom = 40.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                rows.forEachIndexed { index, (title, credits) ->
                    item(key = title) {
                        ContentRow(title, credits, key = { it.tmdbId }) { credit: FilmCredit ->
                            PosterCard(
                                imageUrl = credit.poster,
                                title = credit.title,
                                onClick = { onOpen(PersonLogic.open(credit)) },
                                onFocus = { focused = credit },
                                seen = false,
                                modifier = if (index == 0 && credit == credits.first()) Modifier.focusRequester(firstFocus) else Modifier,
                            )
                        }
                    }
                }
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { firstFocus.requestFocus() } }
}
