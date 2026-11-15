package fr.arrmada.app.ui.player

import android.content.Context
import android.widget.Toast
import androidx.annotation.OptIn
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.media3.common.C
import androidx.media3.common.PlaybackException
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlaybackException
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.data.DefaultQuality
import fr.arrmada.app.data.DolbyVisionLogic
import fr.arrmada.app.data.HlsAudioLogic
import fr.arrmada.app.data.LateSubtitleLogic
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.Quality
import fr.arrmada.app.data.QualityLogic
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.StreamSwitchLogic
import fr.arrmada.app.data.TrackPreference
import fr.arrmada.app.data.VideoRescueLogic
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Flux lu par le lecteur et ses changements : quel flux (direct, remux,
 * SDR, 1080p), quelle piste audio demandée à Jellyfin, et les filets de
 * sécurité quand la lecture se passe mal.
 *
 * Comme un petit service à part du lecteur : il garde son propre état (flux
 * en cours, qualité, conversion par Jellyfin, coupures comptées, carte
 * « Passer en 1080p ? », erreur affichée) et le lecteur l'appelle :
 *  - [load] charge un flux à une position, sous-titres posés à côté compris ;
 *  - [setQuality] et [setHlsAudio] : menu pause › Qualité, panneau Audio ;
 *  - [onTracksChanged], [checkVideo], [onBuffering], [onPlayerError] : ce
 *    que le lecteur signale (nouvelles pistes, attente, erreur), avec les
 *    reprises automatiques (remux, SDR, image réencodée, son par FFmpeg).
 *
 * Une instance par lecture (créée avec `remember` dans PlayerSurface).
 */
@OptIn(UnstableApi::class)
@Stable
internal class StreamSwitcher(
    private val info: PlayInfo,
    private val request: PlayRequest,
    private val player: ExoPlayer,
    private val app: ArrMadaApplication,
    private val repository: Repository,
    private val uiScope: CoroutineScope,
    private val context: Context,
    private val subtitles: SubtitleTools,
    private val trackChooser: TrackChooser,
    private val lateSubtitles: LateSubtitleFetcher,
    startQuality: Quality,
    private val reducedQuality: Quality?, // le « 1080p » proposé sur cet écran
    initialSource: Pair<String, Boolean>,
    initialHlsAudio: Int?,
    sdrAtStart: Boolean,
    private val screenDolbyVision: Boolean,
) {
    var playbackError by mutableStateOf<String?>(null)
    var remuxed by mutableStateOf(info.mode == "remux" || startQuality != Quality.ORIGINAL) // flux converti par Jellyfin
    var toneMapped by mutableStateOf(startQuality == Quality.HD_SDR) // image convertie en SDR (DV profil 5, 1080p SDR)
    // Qualité lue (menu pause › Qualité) ; « Original » : le direct, ou le remux
    // si le direct a échoué ; le DV profil 5 a-t-il imposé le SDR sur cet écran ?
    var quality by mutableStateOf(startQuality)
    var originalSource by mutableStateOf(QualityLogic.source(info, Quality.ORIGINAL))
    var doviForcedSdr by mutableStateOf(sdrAtStart)
    // Coupures en pleine lecture (ADR-012) : 3 en 5 min → proposer le 1080p
    var readyOnce by mutableStateOf(false) // première image du flux en cours affichée
    var lastSeekAt by mutableLongStateOf(0L) // dernier saut ou changement de flux
    var rebuffers by mutableStateOf(emptyList<Long>())
    var qualityDeclined by mutableStateOf(false) // « Non merci » : plus de proposition
    var qualityCard by mutableStateOf<QualityCardKind?>(null)
    var dolbyVisionWarned by mutableStateOf(false)
    // Image que l'appareil ne décode pas et rien pour la convertir (VideoRescueLogic) : dit une fois
    var noPictureWarned by mutableStateOf(false)
    var source by mutableStateOf(initialSource)
    // Piste audio demandée à Jellyfin pour le flux converti en cours (index
    // MediaStreams), null : sa piste par défaut. Sa liste HLS n'en porte qu'une :
    // sans ça, la VF choisie en direct serait perdue en 1080p (HlsAudioLogic).
    // Converti dès le départ : la piste de la règle des langues d'office
    var hlsAudio by mutableStateOf(initialHlsAudio)
    // Pistes texte extraites par Jellyfin, qui peuvent répondre dans des minutes :
    // lateLoad : l'attente en cours pour le flux lu (LateSubtitleFetcher)
    var lateLoad by mutableStateOf<Job?>(null)
    var softwareAudio by mutableStateOf(false) // son décodé par FFmpeg (secours)

    /**
     * Recharge le flux [url] (remux, SDR, 1080p, nouveaux sous-titres) à la
     * position [at]. [before] : pistes lues jusque-là, dont la piste audio
     * entendue et les sous-titres affichés, à retrouver dans le nouveau flux
     * (HlsAudioLogic, TrackChooser) ; à passer soi-même si le lecteur a été
     * arrêté entre-temps.
     *
     * En HLS, le flux de Jellyfin n'a que l'image et une seule piste de son :
     * la piste audio entendue lui est demandée (« ?audio=N ») et les pistes
     * texte du fichier sont posées à côté, avec les sous-titres externes.
     *
     * Les pistes texte extraites par Jellyfin peuvent mettre des minutes à
     * répondre, et Media3 ne démarre pas tant qu'une piste posée à côté n'a
     * pas répondu (LateSubtitleLogic) : si elles arrivent dans la foulée
     * (déjà extraites), elles partent avec le flux, comme avant ; sinon la
     * vidéo démarre sans elles, elles sont demandées en arrière-plan
     * (LateSubtitleFetcher) et le même flux est relu, au même endroit, quand
     * elles sont là. Le lecteur les lit alors depuis le disque de l'appli.
     */
    fun load(url: String, hls: Boolean, at: Long, before: Tracks = player.currentTracks) {
        // Flux converti : la piste audio entendue, retrouvée parmi celles du
        // serveur (déjà converti : la même qu'avant, le lecteur n'en voit qu'une).
        // Lue AVANT de changer d'élément : le lecteur oublie alors ses pistes.
        hlsAudio = if (hls) HlsAudioLogic.indexForSwitch(source.second, hlsAudio, heardAudio(before), info.audioTracks) else null
        source = url to hls
        val subs = StreamSwitchLogic.sideloaded(hls, subtitles.sideSubs, info.embeddedSubtitles)
        val target = app.api.baseUrl + HlsAudioLogic.withAudio(url, hlsAudio)
        // L'attente de pistes lancée pour le flux précédent ne vaut plus
        lateLoad?.cancel()
        lateLoad = null
        lateSubtitles.cancel()

        /** Charge le flux à [position] avec les sous-titres disponibles maintenant (reçus : depuis le disque). */
        fun post(position: Long) {
            // Le nouveau flux remplit sa mémoire tampon : ce n'est pas une coupure
            readyOnce = false
            lastSeekAt = System.currentTimeMillis()
            trackChooser.keepSubtitle(before)
            val posted = LateSubtitleLogic.split(subs, info.embeddedSubtitles, lateSubtitles.ready, lateSubtitles.failed).now
            player.setMediaItem(mediaItem(target, hls, sideSubtitles(posted, app.api.baseUrl, lateSubtitles::localUri)), position)
            player.prepare()
        }

        val later = LateSubtitleLogic.split(subs, info.embeddedSubtitles, lateSubtitles.ready, lateSubtitles.failed).later
        if (later.isEmpty()) {
            post(at)
            return
        }
        lateLoad = uiScope.launch {
            val fetch = lateSubtitles.fetch(later)
            // Déjà extraites : reçues en moins de PROBE_MS, un seul chargement, comme avant
            val quick = withTimeoutOrNull(LateSubtitleLogic.PROBE_MS) { fetch.join() } != null
            post(at)
            if (!quick) fetch.join() // des minutes, peut-être ; la vidéo joue pendant ce temps
            val message = lateSubtitles.outcomeMessage(later)
            if (!quick && later.any { it.url in lateSubtitles.ready }) {
                lateLoad = null // cette attente est finie : rien à interrompre
                load(url, hls, player.currentPosition) // relecture au même endroit, pistes reçues depuis le disque
            }
            message?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
        }
    }

    /** Même flux, même position : relu après un changement de sous-titres (SubtitleTools). */
    fun reloadSameStream() = load(source.first, source.second, player.currentPosition)

    /**
     * Menu pause › Qualité, ou carte « Passer en 1080p ? » : même position,
     * même état lecture / pause. Une conversion Jellyfin en cours est arrêtée
     * AVANT de lancer le nouveau flux : remux, SDR et 1080p partagent la même
     * session chez Jellyfin, l'arrêt après coup couperait aussi le nouveau.
     * Cet arrêt efface aussi les morceaux déjà produits : indispensable quand
     * la piste audio change, Jellyfin les resservirait sinon (son dossier de
     * sortie ne dépend que de la session, pas de la piste demandée).
     */
    fun setQuality(target: Quality, message: String? = null) {
        if (target == quality) return
        val (url, hls) = if (target == Quality.ORIGINAL) originalSource else QualityLogic.source(info, target)
        if (url.isBlank()) return
        val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
        val wasPlaying = player.playWhenReady
        val before = player.currentTracks // les sous-titres affichés, avant l'arrêt du lecteur
        val stopFirst = remuxed && info.itemId.isNotBlank()
        quality = target
        toneMapped = target == Quality.HD_SDR
        remuxed = target != Quality.ORIGINAL || hls
        rebuffers = emptyList()
        Toast.makeText(context, message ?: QualityLogic.switchMessage(target), if (message != null) Toast.LENGTH_LONG else Toast.LENGTH_SHORT).show()
        if (!stopFirst) {
            load(url, hls, at, before)
            player.playWhenReady = wasPlaying
            return
        }
        player.stop() // plus aucune requête vers la conversion qu'on arrête
        uiScope.launch {
            runCatching { repository.stopRemux(info.itemId) }
            load(url, hls, at, before)
            player.playWhenReady = wasPlaying
        }
    }

    /**
     * Écran noir avec le son (VideoRescueLogic) : l'appareil ne décode pas
     * l'image de format [mime] (AV1 sur une Shield…), ou son décodeur a
     * planté. Jellyfin la réencode, un cran plus bas à chaque appel (1080p de
     * cet écran, puis H.264), là où on en était. Faux : plus rien à tenter.
     */
    fun rescuePicture(mime: String?): Boolean {
        val target = VideoRescueLogic.next(quality, reducedQuality, info) ?: return false
        if (QualityLogic.source(info, target).first.isBlank()) return false
        setQuality(target, VideoRescueLogic.rescueMessage(mime))
        player.playWhenReady = true
        return true
    }

    /**
     * Panneau Audio (ou tablette) pendant un flux converti : Jellyfin n'y met
     * qu'une piste, on recharge le MÊME flux avec la piste [index] (« ?audio=N »),
     * même position, même état lecture / pause. La conversion en cours est
     * arrêtée AVANT (comme setQuality) : son dossier de sortie ne dépend que de
     * la session, Jellyfin resservirait sinon les morceaux déjà produits avec
     * l'ancienne piste.
     */
    fun setHlsAudio(index: Int) {
        if (!source.second || !HlsAudioLogic.switchNeeded(info.audioTracks, hlsAudio, index)) return
        val (url, hls) = source
        val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
        val wasPlaying = player.playWhenReady
        // Mémoire du profil (l'épisode suivant repartira dans cette langue) : la
        // langue de la piste du serveur, avec les sous-titres en cours, rangée
        // avant le rechargement (le lecteur ne saura pas celle qu'il reçoit)
        trackChooser.saveHlsAudioChoice(HlsAudioLogic.playedLanguage(info.audioTracks, index))
        hlsAudio = index // load() le garde : déjà sur un flux converti
        rebuffers = emptyList()
        player.stop() // plus aucune requête vers la conversion qu'on arrête
        uiScope.launch {
            if (info.itemId.isNotBlank()) runCatching { repository.stopRemux(info.itemId) }
            load(url, hls, at)
            player.playWhenReady = wasPlaying
        }
    }

    /** Carte de qualité : OK / « Passer en 1080p » (ou « Oui » à la seconde question). */
    fun acceptQualityCard() {
        when (qualityCard) {
            QualityCardKind.SUGGEST -> {
                reducedQuality?.let { setQuality(it) }
                // Une seule fois par TV : en faire le réglage par défaut ?
                val ask = app.prefs.defaultQuality == DefaultQuality.ORIGINAL && !app.prefs.qualityAsked
                qualityCard = if (ask) QualityCardKind.ALWAYS else null
            }
            QualityCardKind.ALWAYS -> {
                app.prefs.defaultQuality = DefaultQuality.HD_1080
                app.prefs.qualityAsked = true
                qualityCard = null
                Toast.makeText(context, "Cette TV lira en 1080p (modifiable dans Réglages)", Toast.LENGTH_LONG).show()
            }
            null -> Unit
        }
    }

    /** Carte de qualité : Retour / « Non merci » (la proposition ne revient plus de la séance). */
    fun declineQualityCard() {
        when (qualityCard) {
            QualityCardKind.SUGGEST -> qualityDeclined = true
            QualityCardKind.ALWAYS -> app.prefs.qualityAsked = true
            null -> Unit
        }
        qualityCard = null
    }

    /** Nouveau jeu de pistes : pistes choisies (TrackChooser), sous-titres attendus. */
    fun onTracksChanged(newTracks: Tracks, originalLanguage: String?, preference: TrackPreference?) {
        // Langues d'office au premier jeu de pistes, choix de l'utilisateur rangé,
        // sous-titres d'avant repris après un changement de flux (qualité, remux)
        trackChooser.onTracksChanged(
            newTracks,
            originalLanguage = originalLanguage,
            preference = preference,
            waitingSubtitle = subtitles.pendingLabel != null,
            // Flux converti : la langue de la piste que Jellyfin y a mise (le lecteur ne la voit pas)
            hlsAudioLanguage = if (source.second) HlsAudioLogic.playedLanguage(info.audioTracks, hlsAudio) else null,
            // Piste extraite par Jellyfin encore attendue : elle reviendra à la relecture du flux
            comingLater = { shown -> LateSubtitleLogic.comingLater(shown, lateSubtitles.pending) },
            onSubtitleLost = { label, image, later ->
                // Piste image (PGS, VobSub) : pas de version texte à poser à côté du flux converti
                val text = when {
                    later -> LateSubtitleLogic.waitingMessage(label)
                    image -> "Sous-titres « $label » : pas de version texte pour ce flux"
                    else -> "Sous-titres « $label » absents de ce flux"
                }
                Toast.makeText(context, text, Toast.LENGTH_LONG).show()
            },
        )
        // Flux rechargé (décalage, resynchro) : la piste voulue, dès qu'elle apparaît
        subtitles.pendingLabel?.let { wanted ->
            trackChoices(newTracks, C.TRACK_TYPE_TEXT)
                .firstOrNull { it.group?.getTrackFormat(it.index)?.label == wanted }
                ?.let {
                    subtitles.pendingLabel = null
                    selectTrack(player, C.TRACK_TYPE_TEXT, it)
                }
        }
    }

    /** Filets de sécurité sur l'image, à chaque nouveau jeu de pistes. */
    fun checkVideo(newTracks: Tracks) {
        // Filet de sécurité : le fichier a une image, mais l'appareil n'a pas de
        // décodeur pour elle (AV1 sur une Shield…). Le lecteur ne dit rien et
        // joue le son sur un écran noir : Jellyfin réencode l'image.
        val videoGroups = newTracks.groups.filter { it.type == C.TRACK_TYPE_VIDEO }
        if (VideoRescueLogic.noPicture(videoGroups.size, videoGroups.any { it.isSelected })) {
            val mime = videoGroups.first().getTrackFormat(0).let { it.sampleMimeType ?: it.codecs }
            if (!rescuePicture(mime) && !noPictureWarned) {
                noPictureWarned = true
                Toast.makeText(context, VideoRescueLogic.stuckMessage(mime), Toast.LENGTH_LONG).show()
            }
            return
        }
        // Filet de sécurité : la piste vidéo se révèle Dolby Vision profil 5
        // alors que l'écran ne le gère pas (serveur Jellyfin trop ancien
        // pour l'annoncer, ou remux) → conversion SDR là où on en était.
        val video = selectedVideoFormat(newTracks) ?: return
        if (toneMapped || screenDolbyVision || !DolbyVisionLogic.withoutFallback(video.sampleMimeType, video.codecs)) return
        if (info.sdrStream.isNotBlank()) {
            toneMapped = true
            remuxed = true
            quality = Quality.HD_SDR
            doviForcedSdr = true
            val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
            load(info.sdrStream, hls = true, at = at)
            player.play()
            Toast.makeText(context, DV_SDR_MESSAGE, Toast.LENGTH_LONG).show()
        } else if (!dolbyVisionWarned) {
            // Fichier de l'écran Vidéos : pas de Jellyfin pour le convertir
            dolbyVisionWarned = true
            Toast.makeText(
                context,
                "Dolby Vision profil 5 : couleurs fausses sur cet écran",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    /** Attente de chargement : une coupure en pleine lecture est comptée (carte « Passer en 1080p ? »). */
    fun onBuffering() {
        val now = System.currentTimeMillis()
        if (QualityLogic.isRebuffer(player.playWhenReady, readyOnce, now, lastSeekAt)) {
            rebuffers = QualityLogic.record(rebuffers, now)
            if (qualityCard == null &&
                QualityLogic.shouldSuggest(rebuffers, now, quality, reducedQuality, qualityDeclined, info.bitrate)
            ) {
                qualityCard = QualityCardKind.SUGGEST
            }
        }
    }

    /** Erreur du lecteur : reprise automatique si possible, sinon message ([playbackError]). */
    fun onPlayerError(e: PlaybackException) {
        // Décodeur audio d'Android en échec (ex. MP3 d'un vieil .avi, dont
        // les blocs ne tombent pas sur les trames) : on le met de côté et
        // FFmpeg, plus tolérant, reprend le son là où on en était.
        if (!softwareAudio && audioDecoderFailed(e)) {
            val audio = (0 until player.rendererCount).filter { player.getRendererType(it) == C.TRACK_TYPE_AUDIO }
            val selector = player.trackSelector as? DefaultTrackSelector
            if (audio.size > 1 && selector != null) {
                softwareAudio = true
                val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
                selector.setParameters(selector.buildUponParameters().setRendererDisabled(audio.first(), true))
                player.prepare()
                player.seekTo(at)
                player.play()
                Toast.makeText(context, "Son décodé par l’appli (format audio mal géré par Android)", Toast.LENGTH_LONG).show()
                return
            }
        }
        // Décodeur vidéo en échec (format au-delà de ce que l'appareil sait
        // faire, décodeur qui plante) : le remux garderait la même image,
        // Jellyfin la réencode, là où on en était
        if (videoDecoderFailed(e) && rescuePicture((e as? ExoPlaybackException)?.rendererFormat?.sampleMimeType)) return
        // Fichier illisible en direct : on retente une fois en remux,
        // là où on en était
        if (!remuxed && info.remuxStream.isNotBlank() && remuxRetry(e.errorCode, info.container)) {
            remuxed = true
            originalSource = info.remuxStream to true // « Original » = ce remux désormais
            val at = player.currentPosition.takeIf { it > 0 } ?: (request.startSeconds * 1000L)
            load(info.remuxStream, hls = true, at = at)
            player.play()
            Toast.makeText(context, "Format ${info.container.ifBlank { "inconnu" }} : conversion par Jellyfin…", Toast.LENGTH_LONG).show()
            return
        }
        playbackError = describe(
            e,
            info.container,
            when {
                toneMapped -> "converti en SDR par Jellyfin"
                remuxed -> "converti par Jellyfin"
                else -> "lecture directe"
            },
        )
    }
}
