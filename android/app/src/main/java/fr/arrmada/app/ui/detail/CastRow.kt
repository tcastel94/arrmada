package fr.arrmada.app.ui.detail

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import coil.compose.AsyncImage
import fr.arrmada.app.data.Person
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.tapToClick
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch

/**
 * Rangée « Distribution » d'une fiche (film ou série), tout en bas de la page.
 *
 * À la TV, la fiche tient sur un écran et la distribution dépasse en bas : la
 * page ([scroll]) descend jusqu'au bout quand le focus entre dans la rangée,
 * et remonte tout en haut quand il en sort. Sans ça, les photos restaient
 * coupées par le bas de l'écran, voire invisibles (résumé long, carte
 * technique haute). Au doigt, la page défile librement.
 *
 * Chaque acteur prend le focus, même sans filmographie connue : c'est ce qui
 * permet d'atteindre la rangée à la télécommande. OK ouvre la filmographie
 * ([onPerson]) quand l'identifiant TMDB de l'acteur est connu.
 */
@Composable
fun CastRow(
    cast: List<Person>,
    scroll: ScrollState,
    onPerson: ((tmdbId: Long) -> Unit)?,
    modifier: Modifier = Modifier,
    startPadding: Dp = 0.dp,
    endPadding: Dp = 0.dp,
) {
    if (cast.isEmpty()) return
    val scope = rememberCoroutineScope()
    val touch = LocalScreen.current.isTouch
    Column(
        modifier.onFocusChanged { state ->
            if (!touch) scope.launch { scroll.animateScrollTo(if (state.hasFocus) scroll.maxValue else 0) }
        },
    ) {
        Text(
            "Distribution",
            style = MaterialTheme.typography.titleMedium,
            color = ArrColors.TextSecondary,
            modifier = Modifier.padding(start = startPadding, bottom = 8.dp),
        )
        // Marge haute / basse : la carte grossie au focus n'est pas coupée par la rangée
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            contentPadding = PaddingValues(start = startPadding, end = endPadding, top = 8.dp, bottom = 8.dp),
        ) {
            items(cast.take(15)) { person -> // pas de clé : deux rôles peuvent avoir le même nom
                val tmdb = person.tmdbId
                CastCard(person, if (onPerson != null && tmdb != null) { { onPerson(tmdb) } } else null)
            }
        }
    }
}

/** Un membre de la distribution : photo ronde, nom, rôle ; OK ouvre sa filmographie si elle est connue. */
@Composable
private fun CastCard(person: Person, onClick: (() -> Unit)?) {
    val shape = RoundedCornerShape(10.dp)
    val click = onClick ?: {}
    Surface(
        onClick = click,
        modifier = Modifier.tapToClick(click),
        shape = ClickableSurfaceDefaults.shape(shape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.05f),
        border = ClickableSurfaceDefaults.border(
            focusedBorder = Border(BorderStroke(3.dp, Color.White), shape = shape),
        ),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = Color.Transparent,
            contentColor = ArrColors.Text,
            focusedContainerColor = ArrColors.Card,
            focusedContentColor = ArrColors.Text,
        ),
    ) {
        Column(Modifier.width(92.dp).padding(horizontal = 4.dp, vertical = 6.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.size(68.dp).clip(CircleShape).background(ArrColors.Card), contentAlignment = Alignment.Center) {
                if (person.photo != null) {
                    // Portrait vertical recadré dans un rond : calé en haut, le visage n'est pas coupé
                    AsyncImage(
                        model = person.photo,
                        contentDescription = person.name,
                        contentScale = ContentScale.Crop,
                        alignment = Alignment.TopCenter,
                        modifier = Modifier.fillMaxSize(),
                    )
                } else {
                    // Pas de photo : initiales
                    Text(castInitials(person.name), style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary)
                }
            }
            // Nom sur deux lignes au besoin (plus de « Timothée Chal… »)
            Text(person.name, style = MaterialTheme.typography.labelMedium, maxLines = 2, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 4.dp))
            Text(person.character, style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
        }
    }
}

/** « Timothée Chalamet » → « TC ». */
internal fun castInitials(name: String): String =
    name.split(' ').filter { it.isNotBlank() }.take(2).joinToString("") { it.first().uppercase() }
