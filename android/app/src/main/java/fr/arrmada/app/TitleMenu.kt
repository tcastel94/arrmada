package fr.arrmada.app

import android.content.Context
import android.widget.Toast
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import fr.arrmada.app.data.MediaMenuLogic
import fr.arrmada.app.data.MenuAction
import fr.arrmada.app.data.MenuTarget
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.SubtitleSearchBody
import fr.arrmada.app.ui.player.PlayRequest
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * Menu d'appui long sur une carte (accueil, grilles Films / Séries) : le
 * titre visé et ce que fait chaque action (reprendre, ma liste, vu / non
 * vu, autre version, sous-titres…).
 *
 * Comme un petit service à part de la navigation, sur le modèle de
 * SubtitleTools et TrackChooser pour le lecteur : il garde le titre dont le
 * menu est ouvert ([target]) et exécute l'action choisie ([run]). Il ne
 * connaît pas les écrans : pour en ouvrir un, il passe l'adresse
 * (Routes.…) à [navigate].
 *
 * Une instance pour toute l'appli (créée avec `remember` dans ArrMadaNavigation).
 */
@Stable
internal class TitleMenu(
    private val repository: Repository,
    private val context: Context,
    private val scope: CoroutineScope,
    private val navigate: (String) -> Unit,
) {
    /** Titre dont le menu est ouvert ; null : menu fermé. */
    var target by mutableStateOf<MenuTarget?>(null)

    /** Ferme le menu (Retour, ou action choisie). */
    fun close() {
        target = null
    }

    private fun toast(text: String, length: Int = Toast.LENGTH_SHORT) = Toast.makeText(context, text, length).show()

    /** Action choisie dans le menu de [target]. */
    fun run(target: MenuTarget, action: MenuAction) {
        val resume = target.resume
        when (action) {
            MenuAction.RESUME -> resume?.let { navigate(Routes.play(resumeRequest(it))) }
            MenuAction.FROM_START -> resume?.let { navigate(Routes.play(resumeRequest(it).copy(startSeconds = 0))) }
            MenuAction.PLAY -> target.tmdbId?.let { navigate(Routes.play(PlayRequest("movie", it, radarrId = target.arrId))) }
            MenuAction.OPEN -> {
                val arr = target.arrId
                when {
                    target.localSeries != null -> navigate(Routes.localShow(target.localSeries))
                    arr != null && target.isMovie -> navigate(Routes.movie(arr, target.tmdbId))
                    arr != null -> navigate(Routes.show(arr))
                }
            }
            MenuAction.TRAILER -> target.tmdbId?.let { navigate(Routes.trailer(it, null)) }
            MenuAction.ADD_TO_LIST, MenuAction.REMOVE_FROM_LIST -> {
                val item = target.watchlist ?: return
                scope.launch {
                    val adding = action == MenuAction.ADD_TO_LIST
                    runCatching { if (adding) repository.addToWatchlist(item) else repository.removeFromWatchlist(item) }
                        .onSuccess { toast(if (adding) "Ajouté à ma liste" else "Retiré de ma liste") }
                        .onFailure { toast(it.message ?: "Liste injoignable") }
                }
            }
            MenuAction.OTHER_RELEASE -> target.arrId?.let {
                navigate(Routes.releases(if (target.isMovie) "movie" else "series", it, target.title))
            }
            MenuAction.FIND_SUBTITLES -> scope.launch {
                // Bazarr cherche (sur tous ses fournisseurs) ; la réponse dit si la recherche est lancée
                runCatching { repository.searchSubtitles(SubtitleSearchBody("movie", target.tmdbId, target.title)) }
                    .onSuccess { toast(it.message ?: "Recherche de sous-titres lancée", Toast.LENGTH_LONG) }
                    .onFailure { toast(it.message ?: "Bazarr injoignable", Toast.LENGTH_LONG) }
            }
            MenuAction.MARK_WATCHED, MenuAction.MARK_UNWATCHED -> {
                val watched = action == MenuAction.MARK_WATCHED
                val update = MediaMenuLogic.watchedUpdate(target, watched, Repository.nowLastPlayed()) ?: return
                scope.launch {
                    runCatching { repository.saveWatchState(update) }
                        .onSuccess {
                            repository.notifyWatchChanged()
                            toast(if (watched) "Marqué comme vu" else "Marqué comme non vu")
                        }
                        .onFailure { toast(it.message ?: "Échec") }
                }
            }
        }
    }
}
