package fr.arrmada.app.ui.request

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import fr.arrmada.app.data.PlayTarget
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ChoiceDialog

/**
 * « Sur la TV » (téléphone, tablette) : choisir une TV de la maison où lancer
 * le titre. La TV le reçoit dans les 5 s, comme « Lire sur la TV » de la web
 * app (TV sous Kodi comme TV avec l'appli). [onSend] fait l'envoi, depuis un
 * écran qui reste affiché (la boîte se ferme aussitôt).
 */
@Composable
fun SendToTvDialog(repository: Repository, title: String, onSend: (PlayTarget) -> Unit, onDismiss: () -> Unit) {
    var targets by remember { mutableStateOf<List<PlayTarget>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        runCatching { repository.playTargets() }
            .onSuccess { targets = it }
            .onFailure { error = it.message ?: "Serveur injoignable" }
    }
    val list = targets
    ChoiceDialog(
        title = "Lire sur une TV",
        subtitle = when {
            error != null -> error
            list == null -> "Recherche des TV…"
            list.isEmpty() -> "Aucune TV appairée (web app › Réglages › Kodi › Appareils)."
            else -> title
        },
        choices = list.orEmpty().map { target ->
            (target.name + if (target.online) "" else " · éteinte ?") to { onSend(target) }
        },
        onDismiss = onDismiss,
    )
}
