package fr.arrmada.app.ui.components

import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.WatchlistTarget
import kotlinx.coroutines.launch

/**
 * Bouton « Ma liste » d'une fiche (film ou série) : ajoute le titre à la
 * liste « À voir » du profil qui regarde, ou l'en retire.
 *
 * L'état affiché change tout de suite (« optimiste », comme un cache en
 * écriture différée) ; si le serveur refuse, il revient en arrière avec un
 * message.
 */
@Composable
fun WatchlistButton(target: WatchlistTarget, repository: Repository, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var inList by remember(target.key) { mutableStateOf<Boolean?>(null) } // null : pas encore su
    var busy by remember { mutableStateOf(false) }

    LaunchedEffect(target.key) { inList = repository.inWatchlist(target.key) }

    val checked = inList == true
    ArrButton(
        if (checked) "Dans ma liste" else "Ma liste",
        {
            if (busy || inList == null) return@ArrButton
            busy = true
            val adding = !checked
            inList = adding
            scope.launch {
                val result = runCatching {
                    if (adding) repository.addToWatchlist(target) else repository.removeFromWatchlist(target)
                }
                result.exceptionOrNull()?.let { error ->
                    inList = !adding
                    Toast.makeText(context, error.message ?: "Liste injoignable", Toast.LENGTH_LONG).show()
                }
                busy = false
            }
        },
        leading = if (checked) "✓" else "+",
        modifier = modifier,
    )
}
