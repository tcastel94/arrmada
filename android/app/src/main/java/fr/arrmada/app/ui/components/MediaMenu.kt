package fr.arrmada.app.ui.components

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import fr.arrmada.app.data.MediaMenuLogic
import fr.arrmada.app.data.MenuAction
import fr.arrmada.app.data.MenuTarget
import fr.arrmada.app.data.Repository
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Menu de l'appui long sur une carte (OK maintenu à la télécommande, doigt
 * appuyé sur le téléphone) : lire ou reprendre, ouvrir la fiche,
 * bande-annonce, ajouter à / retirer de « Ma liste », marquer vu / non vu.
 *
 * « Dans ma liste ? » et « déjà vu ? » sont lus avant d'ouvrir le menu (en
 * mémoire le plus souvent, 2 s au plus) pour proposer la bonne action.
 */
@Composable
fun MediaMenu(target: MenuTarget, repository: Repository, onDismiss: () -> Unit, onAction: (MenuAction) -> Unit) {
    var actions by remember(target) { mutableStateOf<List<MenuAction>?>(null) }
    LaunchedEffect(target) {
        val inList = target.watchlist?.let { list ->
            withTimeoutOrNull(2_000) { runCatching { repository.inWatchlist(list.key) }.getOrNull() }
        } ?: false
        val watched = if (target.resume != null) {
            target.resume.state.watched
        } else {
            withTimeoutOrNull(2_000) { runCatching { MediaMenuLogic.watched(target, repository.watchStates()) }.getOrNull() }
        }
        actions = MediaMenuLogic.actions(target, inList, watched)
    }
    val ready = actions ?: return
    ChoiceDialog(
        title = target.title,
        subtitle = MediaMenuLogic.subtitle(target),
        choices = ready.map { action -> MediaMenuLogic.label(action, target) to { onAction(action) } },
        onDismiss = onDismiss,
    )
}
