package fr.arrmada.app.ui.player

import androidx.annotation.OptIn
import androidx.compose.runtime.Stable
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.TrackLanguageLogic
import fr.arrmada.app.data.TrackPreference
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch

/**
 * Choix des pistes audio et sous-titres du lecteur, et leur mémoire par
 * profil (TrackLanguageLogic pour la règle, le serveur pour la mémoire).
 *
 * Comme un petit service à part du lecteur :
 *  - au premier jeu de pistes du fichier, il choisit seul les langues
 *    (dernier choix du profil pour ce titre, sinon VO + sous-titres FR, ou
 *    VF + forcés) ;
 *  - quand quelqu'un change de piste ([select] : menu pause, tablette), il
 *    applique le choix puis le range sur le serveur dès que le lecteur
 *    l'a pris en compte, pour l'épisode suivant.
 *
 * Flux converti (1080p, remux, SDR) : Jellyfin n'y met qu'une piste audio,
 * dont le lecteur ne connaît pas la langue. PlayerSurface lui passe celle de
 * la piste du serveur que le flux porte (HlsAudioLogic.playedLanguage) : les
 * sous-titres d'office en tiennent compte, et la mémoire du profil range cette
 * langue-là, y compris quand la piste change au panneau Audio
 * ([saveHlsAudioChoice]) — le lecteur, lui, n'y voit toujours qu'une piste
 * anonyme, pas de quoi attendre son prochain jeu de pistes comme pour [select].
 *
 * Le lecteur lui transmet chaque nouveau jeu de pistes ([onTracksChanged]).
 * Une instance par lecture (créée avec `remember` dans PlayerSurface).
 */
@OptIn(UnstableApi::class)
@Stable
internal class TrackChooser(
    private val player: ExoPlayer,
    playRequest: PlayRequest,
    private val repository: Repository,
    private val appScope: CoroutineScope, // tâche de fond qui survit à la sortie du lecteur
) {
    // Titre sous lequel ranger le choix de pistes (série entière, film, série maison)
    private val titleScope: String? = TrackLanguageLogic.scope(playRequest.kind, playRequest.id, playRequest.localSeries)

    // Pistes choisies d'office (VO + sous-titres FR, ou VF + forcés) : une
    // fois, au premier jeu de pistes ; ensuite, c'est le choix de l'utilisateur
    private var autoTracksDone = false

    // Piste changée par l'utilisateur : à ranger dès que le lecteur l'a appliquée
    private var saveTracksPending = false

    // Flux converti : langue de la piste audio que Jellyfin y a mise (code du
    // fichier, « fre »), null en lecture directe ou si le fichier ne la dit pas
    private var hlsAudioLanguage: String? = null

    /**
     * Nouveau jeu de pistes (ouverture du fichier, piste changée, flux
     * rechargé). [originalLanguage] : langue originale du titre (fiche) ;
     * [preference] : dernier choix rangé du profil ; [waitingSubtitle] : une
     * piste de sous-titres précise est attendue après rechargement (outils
     * Sous-titres), le choix automatique attend alors ; [hlsAudioLanguage] :
     * pendant un flux converti, la langue de la piste du serveur qu'il porte
     * (le lecteur ne la voit pas), null en lecture directe.
     */
    fun onTracksChanged(
        newTracks: Tracks,
        originalLanguage: String?,
        preference: TrackPreference?,
        waitingSubtitle: Boolean,
        hlsAudioLanguage: String?,
    ) {
        this.hlsAudioLanguage = hlsAudioLanguage
        // Premier jeu de pistes du fichier : langues choisies d'office
        if (!autoTracksDone && !waitingSubtitle && newTracks.groups.any { it.type == C.TRACK_TYPE_AUDIO }) {
            autoTracksDone = true
            applyLanguagePlan(newTracks, originalLanguage, preference)
        }
        // Choix de l'utilisateur appliqué par le lecteur : on le range
        if (saveTracksPending) {
            saveTracksPending = false
            saveTrackChoice(newTracks)
        }
    }

    /** Piste choisie par l'utilisateur (menu pause, tablette) : appliquée, puis rangée pour ce profil. */
    fun select(type: Int, choice: TrackChoice?) {
        selectTrack(player, type, choice)
        saveTracksPending = titleScope != null
    }

    /**
     * Piste du serveur choisie pendant un flux converti (panneau Audio,
     * tablette : PlayerSurface.setHlsAudio), de langue [language] (code du
     * fichier, « fre ») : rangée tout de suite pour ce profil, avec les
     * sous-titres en cours. À appeler AVANT que le lecteur recharge le flux :
     * il y perdra ses pistes, et n'apprendra pas la langue de la nouvelle.
     */
    fun saveHlsAudioChoice(language: String?) {
        save(audioLanguage = language, text = selectedText(player.currentTracks))
    }

    /**
     * Langues au lancement (TrackLanguageLogic) : titre étranger avec
     * sous-titres français → VO + sous-titres FR complets ; film français
     * (ou pas de sous-titres FR) → piste française + sous-titres « forcés »
     * français s'il y en a. Les préférences du lecteur suivent le même choix,
     * pour qu'un rechargement du flux (qualité, remux) le garde.
     *
     * Flux converti dès le départ : la piste audio a déjà été demandée à
     * Jellyfin d'après la même règle (HlsAudioLogic.indexAtStart) ; l'unique
     * piste que voit le lecteur prend ici la langue de celle du serveur, pour
     * que les sous-titres suivent (pas de sous-titres FR complets sur une VF).
     */
    private fun applyLanguagePlan(newTracks: Tracks, originalLanguage: String?, preference: TrackPreference?) {
        val audios = trackChoices(newTracks, C.TRACK_TYPE_AUDIO)
        val texts = trackChoices(newTracks, C.TRACK_TYPE_TEXT)
        val plan = TrackLanguageLogic.plan(
            originalLanguage,
            audios.map { TrackLanguageLogic.Audio(hlsAudioLanguage ?: it.group?.getTrackFormat(it.index)?.language, it.supported) },
            texts.map { choice ->
                val format = choice.group?.getTrackFormat(choice.index)
                TrackLanguageLogic.Text(
                    language = format?.language,
                    forced = format != null && (format.selectionFlags and C.SELECTION_FLAG_FORCED) != 0,
                    supported = choice.supported,
                    isDefault = format != null && (format.selectionFlags and C.SELECTION_FLAG_DEFAULT) != 0,
                    label = format?.label,
                )
            },
            TrackLanguageLogic.remembered(preference),
        )
        player.trackSelectionParameters = player.trackSelectionParameters.buildUpon()
            .setPreferredAudioLanguages(*TrackLanguageLogic.preferredAudioLanguages(plan).toTypedArray())
            // Sous-titres complets : leur langue préférée (Media3 écarte alors les forcés) ;
            // sinon aucune préférence : seuls les forcés de la langue entendue s'affichent
            .setPreferredTextLanguage(plan.textLanguage)
            .build()
        plan.audio?.let { audios.getOrNull(it) }?.let { selectTrack(player, C.TRACK_TYPE_AUDIO, it) }
        // Pas de sous-titre voulu : coupés (pas de piste « par défaut » en anglais sur la VF)
        selectTrack(player, C.TRACK_TYPE_TEXT, plan.text?.let { texts.getOrNull(it) })
    }

    /** Range ce qui est lu (audio, sous-titres ou « coupés ») : l'épisode suivant le reprendra. */
    private fun saveTrackChoice(newTracks: Tracks) {
        val audio = trackChoices(newTracks, C.TRACK_TYPE_AUDIO).firstOrNull { it.selected }
            ?.let { it.group?.getTrackFormat(it.index) }
        // Flux converti : la piste du lecteur n'a pas de langue, celle du serveur fait foi
        save(audioLanguage = hlsAudioLanguage ?: audio?.language, text = selectedText(newTracks))
    }

    /** La piste de sous-titres lue dans [tracks], null si coupés. */
    private fun selectedText(tracks: Tracks): Format? =
        trackChoices(tracks, C.TRACK_TYPE_TEXT).firstOrNull { it.selected }?.let { it.group?.getTrackFormat(it.index) }

    /** Range [audioLanguage] et les sous-titres [text] (null : coupés) sur le serveur, pour ce titre et ce profil. */
    private fun save(audioLanguage: String?, text: Format?) {
        val key = titleScope ?: return
        val remembered = TrackLanguageLogic.remember(
            audioLanguage = audioLanguage,
            subtitlesOn = text != null,
            subtitleLanguage = text?.language,
            subtitleForced = text != null &&
                TrackLanguageLogic.isForced((text.selectionFlags and C.SELECTION_FLAG_FORCED) != 0, text.label),
        )
        // En tâche de fond (survit à la sortie du lecteur) ; un échec ne gêne pas la lecture
        appScope.launch { runCatching { repository.saveTrackPreference(key, TrackLanguageLogic.preference(remembered)) } }
    }
}
