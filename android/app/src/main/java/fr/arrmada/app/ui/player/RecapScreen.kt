package fr.arrmada.app.ui.player

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Recap
import fr.arrmada.app.data.RecapLogic
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay

/** Secondes avant le lancement automatique (lancé depuis la tablette, on n'est peut-être pas devant). */
private const val AUTO_START_S = 15

/**
 * « Précédemment dans… » : résumé de l'épisode d'avant, avant de lancer
 * celui-ci (série pas regardée depuis une semaine, voir RecapLogic).
 *
 * « Lancer » a le focus : OK suffit. Sans rien toucher, l'épisode part au
 * bout de [AUTO_START_S] s ; le décompte s'arrête si on va sur « Revoir ».
 */
@Composable
fun RecapScreen(
    recap: Recap,
    nextCode: String,
    absolute: (String?) -> String?,
    onStart: () -> Unit,
    onReplayPrevious: (() -> Unit)?, // null : épisode d'avant absent du NAS
    onExit: () -> Unit,
) {
    val startFocus = remember { FocusRequester() }
    var left by remember { mutableIntStateOf(AUTO_START_S) }
    var counting by remember { mutableStateOf(true) }

    LaunchedEffect(counting) {
        while (counting && left > 0) {
            delay(1_000)
            if (counting) left--
        }
        if (counting && left == 0) onStart()
    }
    LaunchedEffect(Unit) { runCatching { startFocus.requestFocus() } }
    BackHandler(onBack = onExit)

    KenBurnsBackdrop(url = absolute(recap.fanart)) {
        Column(
            Modifier.fillMaxSize().padding(horizontal = gutter, vertical = 40.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Text(
                "Précédemment dans ${recap.seriesTitle}",
                style = MaterialTheme.typography.labelLarge,
                color = ArrColors.AccentText,
            )
            Text(
                recap.code + (recap.previous.title?.takeIf { it.isNotBlank() }?.let { " · $it" } ?: ""),
                style = MaterialTheme.typography.displayMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 8.dp).widthIn(max = 760.dp),
            )
            recap.previous.overview?.takeIf { it.isNotBlank() }?.let { overview ->
                Text(
                    overview,
                    style = MaterialTheme.typography.bodyLarge,
                    color = ArrColors.TextSecondary,
                    maxLines = 7,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 14.dp).widthIn(max = 680.dp),
                )
            }
            Text(
                "Dernier épisode vu ${RecapLogic.awayLabel(recap.awayDays)}",
                style = MaterialTheme.typography.labelMedium,
                color = ArrColors.TextSecondary,
                modifier = Modifier.padding(top = 14.dp),
            )
            Row(
                Modifier.padding(top = 24.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ArrButton(
                    if (counting) "Lancer $nextCode ($left s)" else "Lancer $nextCode",
                    onStart,
                    primary = true,
                    leading = "▶",
                    modifier = Modifier.focusRequester(startFocus),
                )
                onReplayPrevious?.let { replay ->
                    ArrButton(
                        "Revoir ${recap.code}",
                        replay,
                        // Aller sur ce bouton : on est devant l'écran, plus de lancement automatique
                        modifier = Modifier.onFocusChanged { if (it.isFocused) counting = false },
                    )
                }
            }
        }
    }
}
