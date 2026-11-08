package fr.arrmada.app.ui.player

import androidx.annotation.OptIn
import androidx.compose.runtime.Stable
import androidx.media3.common.C
import androidx.media3.common.MimeTypes
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlayer
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.StreamSwitchLogic
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
 *    l'a pris en compte, pour l'épisode suivant ;
 *  - quand le flux change (qualité, remux de secours, SDR), il retient la
 *    piste de sous-titres affichée ([keepSubtitle]) et la rechoisit dans le
 *    nouveau flux, où elle n'a plus ni le même numéro ni forcément le même
 *    nom (piste du MKV en direct, extraction de Jellyfin en HLS).
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

    // Sous-titres affichés avant un changement de flux : à retrouver dans le
    // nouveau flux dès que ses pistes arrivent (null : rien n'était affiché)
    private var carried: StreamSwitchLogic.Shown? = null

    // Piste retenue mais absente du flux lu (PGS français en 1080p…) : les
    // sous-titres sont coupés en attendant, et elle est réessayée au prochain
    // changement de flux (retour à l'original), tant que personne n'a choisi autre chose
    private var lost: StreamSwitchLogic.Shown? = null

    /**
     * Nouveau jeu de pistes (ouverture du fichier, piste changée, flux
     * rechargé). [originalLanguage] : langue originale du titre (fiche) ;
     * [preference] : dernier choix rangé du profil ; [waitingSubtitle] : une
     * piste de sous-titres précise est attendue après rechargement (outils
     * Sous-titres), le choix automatique et la piste retenue s'effacent
     * alors devant elle. [onSubtitleLost] : la piste retenue avant le
     * changement de flux n'y existe plus (nom, piste image ?) ; les
     * sous-titres sont alors coupés plutôt que remplacés par une autre piste
     * de la même langue (des forcés à la place des complets surprendraient).
     */
    fun onTracksChanged(
        newTracks: Tracks,
        originalLanguage: String?,
        preference: TrackPreference?,
        waitingSubtitle: Boolean,
        onSubtitleLost: (String, Boolean) -> Unit = { _, _ -> },
    ) {
        val loaded = newTracks.groups.any { it.type == C.TRACK_TYPE_AUDIO }
        // Premier jeu de pistes du fichier : langues choisies d'office
        if (!autoTracksDone && !waitingSubtitle && loaded) {
            autoTracksDone = true
            applyLanguagePlan(newTracks, originalLanguage, preference)
        }
        // Flux rechargé : la piste de sous-titres d'avant, si le nouveau flux l'a
        val wanted = carried
        if (wanted != null && loaded) {
            carried = null
            if (!waitingSubtitle) {
                val texts = trackChoices(newTracks, C.TRACK_TYPE_TEXT)
                val index = StreamSwitchLogic.sameText(wanted, texts.map(::asText))
                if (index != null) {
                    lost = null
                    selectTrack(player, C.TRACK_TYPE_TEXT, texts[index])
                } else {
                    lost = wanted
                    selectTrack(player, C.TRACK_TYPE_TEXT, null)
                    onSubtitleLost(wanted.label?.ifBlank { null } ?: languageName(wanted.language) ?: "inconnus", wanted.image)
                }
            }
        }
        // Choix de l'utilisateur appliqué par le lecteur : on le range
        if (saveTracksPending) {
            saveTracksPending = false
            saveTrackChoice(newTracks)
        }
    }

    /**
     * Le flux va être rechargé (qualité, remux de secours, SDR) : retenir la
     * piste de sous-titres affichée dans [tracks], pour la rechoisir dans le
     * nouveau flux ([onTracksChanged]). Rien d'affiché (coupés, aucune) :
     * la piste perdue au changement précédent s'il y en a une, sinon rien à
     * retenir, le lecteur garde ce réglage de lui-même.
     */
    fun keepSubtitle(tracks: Tracks) {
        val format = trackChoices(tracks, C.TRACK_TYPE_TEXT).firstOrNull { it.selected }?.let { it.group?.getTrackFormat(it.index) }
        carried = if (format == null) {
            lost
        } else {
            // Depuis Media3 1.4, les sous-titres sont décodés dès la lecture : le format d'origine est dans « codecs »
            val kind = if (format.sampleMimeType == MimeTypes.APPLICATION_MEDIA3_CUES) format.codecs else format.sampleMimeType
            StreamSwitchLogic.Shown(
                label = format.label,
                language = format.language,
                forced = TrackLanguageLogic.isForced((format.selectionFlags and C.SELECTION_FLAG_FORCED) != 0, format.label),
                image = kind == MimeTypes.APPLICATION_PGS || kind == MimeTypes.APPLICATION_VOBSUB || kind == MimeTypes.APPLICATION_DVBSUBS,
            )
        }
    }

    /** La piste de sous-titres [choice], vue par la logique pure. */
    private fun asText(choice: TrackChoice): TrackLanguageLogic.Text {
        val format = choice.group?.getTrackFormat(choice.index)
        return TrackLanguageLogic.Text(
            language = format?.language,
            forced = format != null && (format.selectionFlags and C.SELECTION_FLAG_FORCED) != 0,
            supported = choice.supported,
            isDefault = format != null && (format.selectionFlags and C.SELECTION_FLAG_DEFAULT) != 0,
            label = format?.label,
        )
    }

    /** Piste choisie par l'utilisateur (menu pause, tablette) : appliquée, puis rangée pour ce profil. */
    fun select(type: Int, choice: TrackChoice?) {
        selectTrack(player, type, choice)
        if (type == C.TRACK_TYPE_TEXT) lost = null // choix explicite : plus rien à reprendre d'un flux précédent
        saveTracksPending = titleScope != null
    }

    /**
     * Langues au lancement (TrackLanguageLogic) : titre étranger avec
     * sous-titres français → VO + sous-titres FR complets ; film français
     * (ou pas de sous-titres FR) → piste française + sous-titres « forcés »
     * français s'il y en a. Les préférences du lecteur suivent le même choix,
     * pour qu'un rechargement du flux (qualité, remux) le garde.
     */
    private fun applyLanguagePlan(newTracks: Tracks, originalLanguage: String?, preference: TrackPreference?) {
        val audios = trackChoices(newTracks, C.TRACK_TYPE_AUDIO)
        val texts = trackChoices(newTracks, C.TRACK_TYPE_TEXT)
        val remembered = preference?.let {
            TrackLanguageLogic.Remembered(
                audio = it.audioLanguage.ifBlank { null },
                subtitle = it.subtitleLanguage.ifBlank { null },
                subtitleForced = it.subtitleForced,
            )
        }
        val plan = TrackLanguageLogic.plan(
            originalLanguage,
            audios.map { TrackLanguageLogic.Audio(it.group?.getTrackFormat(it.index)?.language, it.supported) },
            texts.map(::asText),
            remembered,
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
        val key = titleScope ?: return
        val audio = trackChoices(newTracks, C.TRACK_TYPE_AUDIO).firstOrNull { it.selected }
            ?.let { it.group?.getTrackFormat(it.index) }
        val text = trackChoices(newTracks, C.TRACK_TYPE_TEXT).firstOrNull { it.selected }
            ?.let { it.group?.getTrackFormat(it.index) }
        val remembered = TrackLanguageLogic.remember(
            audioLanguage = audio?.language,
            subtitlesOn = text != null,
            subtitleLanguage = text?.language,
            subtitleForced = text != null &&
                TrackLanguageLogic.isForced((text.selectionFlags and C.SELECTION_FLAG_FORCED) != 0, text.label),
        )
        val preference = TrackPreference(
            found = true,
            audioLanguage = remembered.audio.orEmpty(),
            subtitleLanguage = remembered.subtitle.orEmpty(),
            subtitleForced = remembered.subtitleForced,
        )
        // En tâche de fond (survit à la sortie du lecteur) ; un échec ne gêne pas la lecture
        appScope.launch { runCatching { repository.saveTrackPreference(key, preference) } }
    }
}
