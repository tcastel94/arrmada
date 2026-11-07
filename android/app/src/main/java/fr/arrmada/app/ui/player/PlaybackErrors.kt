package fr.arrmada.app.ui.player

import androidx.annotation.OptIn
import androidx.media3.common.PlaybackException
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.ExoPlaybackException

// Erreurs de lecture : lesquelles justifient un secours (FFmpeg, remux) et
// comment les dire en clair à l'écran.

/** Erreurs de décodeur audio : on retente avec FFmpeg (décodage par l'appli). */
internal val AUDIO_DECODER_ERRORS = setOf(
    PlaybackException.ERROR_CODE_DECODING_FAILED,
    PlaybackException.ERROR_CODE_DECODER_INIT_FAILED,
    PlaybackException.ERROR_CODE_DECODER_QUERY_FAILED,
    PlaybackException.ERROR_CODE_DECODING_FORMAT_EXCEEDS_CAPABILITIES,
)

/** L'erreur vient-elle du décodeur de la piste audio (et pas de la vidéo ou du réseau) ? */
@OptIn(UnstableApi::class)
internal fun audioDecoderFailed(e: PlaybackException): Boolean {
    val renderer = e as? ExoPlaybackException ?: return false
    return renderer.type == ExoPlaybackException.TYPE_RENDERER &&
        renderer.rendererFormat?.sampleMimeType?.startsWith("audio/") == true &&
        e.errorCode in AUDIO_DECODER_ERRORS
}

/**
 * Échec d'une action Sous-titres (Bazarr), en clair : serveur trop ancien
 * pour la fonction (403 / 404), Bazarr trop lent, ou serveur vraiment injoignable.
 */
internal fun subtitleError(e: Throwable): String = when {
    e is fr.arrmada.app.data.ApiException && e.code in setOf(403, 404, 405) ->
        "Le serveur ArrMada n’a pas encore cette fonction : mets-le à jour (maj-arrmada.sh)"
    e is java.net.SocketTimeoutException -> "Bazarr met du temps : la recherche continue sur le serveur"
    e is fr.arrmada.app.data.ApiException -> e.message ?: "Le serveur a refusé (${e.code})"
    else -> "Serveur injoignable (${e.message.orEmpty()})"
}

/** Message affiché quand l'image Dolby Vision est convertie en SDR par Jellyfin. */
// Court : Android TV coupe ses messages après deux lignes
internal const val DV_SDR_MESSAGE = "Image convertie en SDR (TV sans Dolby Vision)"

/** Erreurs de lecture directe qui justifient de retenter en remux. */
internal val REMUX_RETRY = setOf(
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_UNSUPPORTED,
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_MALFORMED,
    PlaybackException.ERROR_CODE_DECODING_FORMAT_UNSUPPORTED,
    PlaybackException.ERROR_CODE_AUDIO_TRACK_INIT_FAILED,
)

/**
 * Message lisible, suivi du détail technique (code ExoPlayer, format du
 * fichier, direct ou remux) : utile pour comprendre ce qui coince.
 */
internal fun describe(e: PlaybackException, container: String, how: String): String {
    val detail = listOfNotNull(
        e.errorCodeName,
        container.takeIf { it.isNotBlank() }?.let { "fichier .$it" },
        how,
    ).joinToString(" · ")
    // AVI : conteneur mal géré par le lecteur d'Android ; le MKV, lui, passe
    val hint = if (container.equals("avi", ignoreCase = true)) {
        "\n\nAVI mal pris en charge : le convertir en MKV, sans perte (scripts/remux-avi-mkv.sh sur le serveur)."
    } else {
        ""
    }
    return describe(e) + "\n\n" + detail + hint
}

/** Message lisible pour les erreurs de lecture les plus courantes. */
internal fun describe(e: PlaybackException): String = when (e.errorCode) {
    PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_FAILED,
    PlaybackException.ERROR_CODE_IO_NETWORK_CONNECTION_TIMEOUT -> "Connexion au serveur perdue."
    PlaybackException.ERROR_CODE_IO_BAD_HTTP_STATUS -> "Le serveur a refusé le fichier (Jellyfin joignable ?)."
    PlaybackException.ERROR_CODE_DECODER_INIT_FAILED,
    PlaybackException.ERROR_CODE_DECODER_QUERY_FAILED,
    PlaybackException.ERROR_CODE_DECODING_FORMAT_UNSUPPORTED,
    PlaybackException.ERROR_CODE_DECODING_FORMAT_EXCEEDS_CAPABILITIES -> "Format vidéo non pris en charge par cet appareil."
    PlaybackException.ERROR_CODE_AUDIO_TRACK_INIT_FAILED,
    PlaybackException.ERROR_CODE_AUDIO_TRACK_WRITE_FAILED -> "Sortie audio impossible (format non accepté par l’ampli ou la TV)."
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_UNSUPPORTED,
    PlaybackException.ERROR_CODE_PARSING_CONTAINER_MALFORMED -> "Fichier illisible ou format de conteneur non pris en charge."
    else -> "${e.errorCodeName} : ${e.message.orEmpty()}"
}
