package fr.arrmada.app.ui.player

import android.content.Context
import android.widget.Toast
import androidx.annotation.OptIn
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.C
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.SubtitleFollowLogic
import fr.arrmada.app.data.SubtitleRequest
import fr.arrmada.app.data.SubtitleResult
import fr.arrmada.app.data.SubtitleShiftLogic
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Outils Sous-titres du lecteur (menu pause › Sous-titres, et tablette du
 * salon) : chercher des sous-titres français avec Bazarr, les recaler sur
 * le son, les décaler de ±0,5 s.
 *
 * Comme un petit service à part du lecteur : il garde son propre état
 * (sous-titres posés à côté du fichier, « Bazarr travaille », dernier
 * message, décalage en cours) et le lecteur l'appelle. Chaque action qui
 * change les sous-titres relit le flux au même endroit : le lecteur passe
 * pour cela [reload] (même flux, même position, nouvelle liste
 * [sideSubs]).
 *
 * Une instance par lecture (créée avec `remember` dans PlayerSurface).
 */
@OptIn(UnstableApi::class)
@Stable
internal class SubtitleTools(
    private val info: PlayInfo,
    playRequest: PlayRequest,
    private val player: ExoPlayer,
    private val repository: Repository,
    private val scope: CoroutineScope,
    private val context: Context,
) {
    /** Sous-titres posés à côté du fichier (Bazarr…), complétés depuis le menu pause. */
    var sideSubs by mutableStateOf(info.subtitles)
        private set

    /** Bazarr travaille (recherche ou resynchro) : les boutons attendent. */
    var busy by mutableStateOf(false)
        private set

    /** Résultat de la dernière action (« Sous-titres ajoutés : Français »…). */
    var note by mutableStateOf<String?>(null)
        private set

    /** Décalage manuel en cours, en ms (0 : sous-titres d'origine). */
    var shiftMs by mutableIntStateOf(0)
        private set

    /**
     * Piste à choisir dès que le flux rechargé la montre (copie décalée,
     * sous-titre resynchronisé) ; le lecteur la remet à null une fois choisie.
     */
    var pendingLabel by mutableStateOf<String?>(null)

    /**
     * Ce que Bazarr doit chercher : film ou épisode de la médiathèque
     * seulement (Bazarr ne connaît pas les vidéos de l'écran Vidéos) ;
     * null : pas d'outil Bazarr pour cette vidéo.
     */
    val request: SubtitleRequest? = when (playRequest.kind) {
        "movie" -> SubtitleRequest("movie", tmdbId = playRequest.id)
        "episode" -> SubtitleRequest("episode", tvdbId = playRequest.id, season = playRequest.season, episode = playRequest.episode)
        else -> null
    }?.takeIf { info.itemId.isNotBlank() }

    /**
     * Menu pause → « Sous-titres FR » : Bazarr cherche, les trouvés s'ajoutent aux pistes.
     *
     * La recherche tourne sur le serveur ; tant qu'elle n'est pas finie
     * (« pending »), la TV redemande toute seule (même recherche, rejointe),
     * en affichant l'étape en cours sous le bouton. La lecture reste possible
     * pendant ce temps. Voir [SubtitleFollowLogic].
     */
    fun download(reload: () -> Unit) {
        val body = request ?: return
        if (busy) return
        busy = true
        note = null
        scope.launch {
            var round = 0
            var result = SubtitleResult(status = "pending")
            while (true) {
                round++
                result = runCatching { repository.downloadSubtitles(info.itemId, body) }
                    .getOrElse {
                        // Délai dépassé : la recherche continue sur le serveur, on la rejoint
                        if (it is java.net.SocketTimeoutException) SubtitleResult(status = "pending")
                        else SubtitleResult(message = subtitleError(it))
                    }
                if (!SubtitleFollowLogic.shouldFollow(result.status, round)) break
                if (round == 1) {
                    Toast.makeText(context, "Bazarr cherche… les sous-titres s’ajouteront tout seuls", Toast.LENGTH_LONG).show()
                }
                note = SubtitleFollowLogic.progressNote(result)
                delay(SubtitleFollowLogic.PAUSE_MS)
            }
            if (result.status == "pending") result = result.copy(message = SubtitleFollowLogic.STILL_RUNNING)
            busy = false
            note = result.message
            result.message?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
            if (result.subtitles.isNotEmpty() && result.subtitles.map { it.url } != sideSubs.map { it.url }) {
                sideSubs = result.subtitles
                // Même flux, sous-titres en plus ; la lecture reste en pause, le
                // français est choisi d'office
                reload()
                (player.trackSelector as? DefaultTrackSelector)?.let {
                    // Réactivés : ils ont pu être coupés au lancement (VF sans forcés)
                    it.setParameters(
                        it.buildUponParameters()
                            .setTrackTypeDisabled(C.TRACK_TYPE_TEXT, false)
                            .setPreferredTextLanguage("fr")
                    )
                }
            }
        }
    }

    /** Menu pause › Sous-titres › « Resynchro auto » : Bazarr recale le .srt sur le son. */
    fun sync(reload: () -> Unit) {
        val body = request ?: return
        if (busy) return
        busy = true
        note = null
        scope.launch {
            val result = runCatching { repository.syncSubtitles(info.itemId, body) }
                .getOrElse { SubtitleResult(message = subtitleError(it)) }
            busy = false
            note = result.message
            result.message?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
            if (result.status == "ok" && result.subtitles.isNotEmpty()) {
                // Même adresse, fichier réécrit par Bazarr : « ?v= » force le lecteur à le relire
                val version = System.currentTimeMillis() / 1000
                sideSubs = result.subtitles.map { it.copy(url = it.url + "?v=$version") }
                shiftMs = 0
                pendingLabel = sideSubs.firstOrNull { it.language == "fr" }?.label
                reload()
            }
        }
    }

    /**
     * Menu pause › Sous-titres › −/+ 0,5 s sur la piste affichée ([tracks]) :
     * copie décalée servie par le serveur.
     */
    fun shift(deltaMs: Int, tracks: Tracks, reload: () -> Unit) {
        val choice = trackChoices(tracks, C.TRACK_TYPE_TEXT).firstOrNull { it.selected }
        val format = choice?.group?.getTrackFormat(choice.index)
        if (format == null) {
            Toast.makeText(context, "Choisis d’abord une piste de sous-titres", Toast.LENGTH_SHORT).show()
            return
        }
        val forced = (format.selectionFlags and C.SELECTION_FLAG_FORCED) != 0
        val src = SubtitleShiftLogic.source(format.label.orEmpty(), format.language, forced, sideSubs, info.embeddedSubtitles)
        if (src == null) {
            Toast.makeText(context, "Cette piste (image) ne peut pas être décalée", Toast.LENGTH_LONG).show()
            return
        }
        val ms = (shiftMs + deltaMs).coerceIn(-600_000, 600_000)
        shiftMs = ms
        val shifted = if (ms == 0) {
            null
        } else {
            src.copy(url = SubtitleShiftLogic.shiftedUrl(src.url, ms), label = SubtitleShiftLogic.shiftedLabel(src.label, ms))
        }
        sideSubs = sideSubs.filterNot { SubtitleShiftLogic.baseLabel(it.label) != it.label } + listOfNotNull(shifted)
        // Après rechargement : la copie décalée, ou (retour à zéro) la piste d'origine
        pendingLabel = shifted?.label ?: src.label.takeIf { s -> sideSubs.any { it.label == s } }
        if (pendingLabel == null) {
            (player.trackSelector as? DefaultTrackSelector)?.let {
                it.setParameters(it.buildUponParameters().setPreferredTextLanguage(format.language))
            }
        }
        reload()
        Toast.makeText(context, if (ms == 0) "Sous-titres d’origine" else "Sous-titres décalés de ${SubtitleShiftLogic.format(ms)}", Toast.LENGTH_SHORT).show()
    }
}
