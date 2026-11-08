package fr.arrmada.app.ui.player

import androidx.annotation.OptIn
import androidx.media3.common.Format
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import fr.arrmada.app.data.SideSubtitle

// Petits outils Media3 du lecteur : élément à lire, sous-titres posés à côté,
// piste vidéo en cours, activité de l'écran.

/** Format de la piste vidéo en cours de lecture (null tant qu'aucune n'est choisie). */
@OptIn(UnstableApi::class)
internal fun selectedVideoFormat(tracks: Tracks): Format? {
    val group = tracks.groups.firstOrNull { it.type == C.TRACK_TYPE_VIDEO && it.isSelected } ?: return null
    return (0 until group.length).firstOrNull { group.isTrackSelected(it) }?.let(group::getTrackFormat)
}

/** Élément à lire : fichier d'origine, ou liste HLS du remux. */
internal fun mediaItem(url: String, hls: Boolean, subtitles: List<MediaItem.SubtitleConfiguration> = emptyList()): MediaItem =
    MediaItem.Builder()
        .setUri(url)
        .apply { if (hls) setMimeType(MimeTypes.APPLICATION_M3U8) }
        .setSubtitleConfigurations(subtitles)
        .build()

/**
 * Sous-titres posés à côté de la vidéo (écran Vidéos) : ajoutés aux pistes du
 * fichier, choisis dans l'onglet Sous-titres du menu pause. Téléchargés par
 * le même client HTTP que la vidéo (jeton d'appareil), en UTF-8 ; [local] :
 * fichier de l'appli déjà reçu pour une piste (LateSubtitleFetcher), lu à
 * la place du serveur, null sinon.
 */
internal fun sideSubtitles(
    subtitles: List<SideSubtitle>,
    baseUrl: String,
    local: (SideSubtitle) -> android.net.Uri? = { null },
): List<MediaItem.SubtitleConfiguration> =
    subtitles.map { sub ->
        MediaItem.SubtitleConfiguration.Builder(local(sub) ?: android.net.Uri.parse(baseUrl + sub.url))
            .setMimeType(sub.mime)
            .setLanguage(sub.language.ifBlank { null })
            .setLabel(sub.label)
            .setSelectionFlags(if ("forcés" in sub.label) C.SELECTION_FLAG_FORCED else 0)
            .build()
    }

/** L'activité qui porte cet écran (le Context de Compose peut être une enveloppe). */
internal tailrec fun android.content.Context.findActivity(): android.app.Activity? = when (this) {
    is android.app.Activity -> this
    is android.content.ContextWrapper -> baseContext.findActivity()
    else -> null
}
