package fr.arrmada.app.ui.player

import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.common.Tracks
import java.util.Locale

/** Une piste audio ou de sous-titres, telle qu'on la propose dans le menu pause. */
data class TrackChoice(
    val label: String,
    val detail: String,
    val selected: Boolean,
    val supported: Boolean,
    val group: Tracks.Group?,
    val index: Int,
)

/** Pistes d'un type (audio ou texte) du fichier en cours, lisibles par un humain. */
fun trackChoices(tracks: Tracks, type: Int): List<TrackChoice> {
    val choices = mutableListOf<TrackChoice>()
    for (group in tracks.groups) {
        if (group.type != type) continue
        for (i in 0 until group.length) {
            val format = group.getTrackFormat(i)
            choices += TrackChoice(
                label = languageName(format.language) ?: format.label ?: "Piste ${choices.size + 1}",
                detail = listOfNotNull(
                    format.label?.takeIf { it.isNotBlank() && languageName(format.language) != null },
                    if (type == C.TRACK_TYPE_AUDIO) audioCodecName(format) else subtitleKind(format),
                    if (type == C.TRACK_TYPE_AUDIO) channelsName(format.channelCount) else null,
                    if ((format.selectionFlags and C.SELECTION_FLAG_FORCED) != 0) "forcés" else null,
                ).joinToString(" · "),
                selected = group.isTrackSelected(i),
                supported = group.isTrackSupported(i),
                group = group,
                index = i,
            )
        }
    }
    return choices
}

/**
 * Son de la piste audio en cours (pour le « son conseillé »), ou null tant
 * que rien n'est choisi. [fileAudio] : format lu par Radarr (« TrueHD Atmos »).
 */
fun selectedSound(tracks: Tracks, fileAudio: String?): fr.arrmada.app.data.SoundAdvisor.Sound? {
    for (group in tracks.groups) {
        if (group.type != C.TRACK_TYPE_AUDIO) continue
        for (i in 0 until group.length) {
            if (!group.isTrackSelected(i)) continue
            val format = group.getTrackFormat(i)
            return fr.arrmada.app.data.SoundAdvisor.sound(format.sampleMimeType, format.channelCount, format.label, fileAudio)
        }
    }
    return null
}

/** Choisit une piste ; pour les sous-titres, `choice == null` les coupe. */
fun selectTrack(player: Player, type: Int, choice: TrackChoice?) {
    val builder = player.trackSelectionParameters.buildUpon()
    val group = choice?.group
    if (choice == null || group == null) {
        builder.setTrackTypeDisabled(type, true)
    } else {
        builder.setTrackTypeDisabled(type, false)
            .setOverrideForType(TrackSelectionOverride(group.mediaTrackGroup, choice.index))
    }
    player.trackSelectionParameters = builder.build()
}

/** « fre » / « fr » → « Français ». */
fun languageName(code: String?): String? {
    if (code.isNullOrBlank() || code == C.LANGUAGE_UNDETERMINED || code == "und") return null
    val name = Locale.forLanguageTag(code).getDisplayLanguage(Locale.FRENCH)
    if (name.isBlank() || name.equals(code, ignoreCase = true)) return code.uppercase()
    return name.replaceFirstChar { it.titlecase(Locale.FRENCH) }
}

/** Nom commercial du format audio (ce qu'affiche l'ampli). */
fun audioCodecName(format: Format): String? = when (format.sampleMimeType) {
    MimeTypes.AUDIO_TRUEHD -> "Dolby TrueHD"
    MimeTypes.AUDIO_E_AC3_JOC -> "Dolby Atmos (DD+)"
    MimeTypes.AUDIO_E_AC3 -> "Dolby Digital Plus"
    MimeTypes.AUDIO_AC3 -> "Dolby Digital"
    MimeTypes.AUDIO_AC4 -> "Dolby AC-4"
    MimeTypes.AUDIO_DTS_HD -> "DTS-HD"
    MimeTypes.AUDIO_DTS_X -> "DTS:X"
    MimeTypes.AUDIO_DTS, MimeTypes.AUDIO_DTS_EXPRESS -> "DTS"
    MimeTypes.AUDIO_AAC -> "AAC"
    MimeTypes.AUDIO_OPUS -> "Opus"
    MimeTypes.AUDIO_FLAC -> "FLAC"
    MimeTypes.AUDIO_MPEG, MimeTypes.AUDIO_MPEG_L2 -> "MP3"
    MimeTypes.AUDIO_VORBIS -> "Vorbis"
    MimeTypes.AUDIO_RAW -> "PCM"
    else -> format.sampleMimeType?.substringAfter('/')?.uppercase()
}

fun channelsName(count: Int): String? = when {
    count <= 0 -> null
    count == 1 -> "Mono"
    count == 2 -> "Stéréo"
    count == 6 -> "5.1"
    count == 8 -> "7.1"
    else -> "$count canaux"
}

// Depuis Media3 1.4, les sous-titres sont décodés dès la lecture du fichier :
// le format d'origine (PGS, SRT…) est alors rangé dans « codecs ».
private fun subtitleKind(format: Format): String? = when (
    if (format.sampleMimeType == MimeTypes.APPLICATION_MEDIA3_CUES) format.codecs else format.sampleMimeType
) {
    MimeTypes.APPLICATION_PGS -> "Blu-ray (image)"
    MimeTypes.APPLICATION_VOBSUB -> "DVD (image)"
    MimeTypes.TEXT_SSA -> "ASS"
    MimeTypes.APPLICATION_SUBRIP -> "SRT"
    else -> null
}
