package fr.arrmada.app.data

import java.util.Locale

/**
 * Piste audio à demander à Jellyfin quand le lecteur passe du fichier
 * d'origine à un flux converti (menu pause › Qualité, carte « Passer en
 * 1080p ? », remux de secours, conversion SDR).
 *
 * Vérifié dans le code de Jellyfin 12.4 (DynamicHlsHelper, EncodingHelper) :
 * sa liste HLS ne porte qu'UNE piste audio, celle d'`AudioStreamIndex`,
 * sinon la première du fichier. Une VF choisie en direct serait donc perdue
 * en 1080p sur un fichier MULTi : une seule piste au panneau Audio du menu
 * pause, et la VO dans les enceintes. Le serveur accepte « ?audio=N » (index
 * MediaStreams de Jellyfin) sur master.m3u8 et sdr.m3u8 et donne la liste
 * des pistes du fichier (`audio_tracks`) : reste à y retrouver la piste que
 * le lecteur joue, que lui ne connaît que par sa langue, son format, ses
 * canaux et son rang dans le fichier.
 *
 * Pendant un flux converti (dès le départ : réglage « 1080p » de la TV,
 * remux .m2ts / .iso ; ou après une bascule), le panneau Audio du menu pause
 * propose les pistes du serveur ([choices]) à la place de l'unique piste que
 * voit le lecteur ; en choisir une autre recharge le même flux avec
 * « ?audio=N » ([switchNeeded], [withAudio]).
 *
 * Logique pure (sans Android), testée sur la JVM (HlsAudioLogicTest).
 */
object HlsAudioLogic {
    /**
     * Piste entendue par le lecteur : [position] = rang parmi les pistes audio
     * (même ordre que le fichier, donc que la liste du serveur), [language] =
     * code de piste (« fr », « fre », null si indéterminé), [mimeType] = type
     * Media3 (« audio/eac3 »), [channels] = canaux (0 ou moins si inconnu).
     */
    data class Heard(val position: Int, val language: String?, val mimeType: String?, val channels: Int)

    /**
     * Index Jellyfin à demander pour le nouveau flux converti. Déjà sur un
     * flux converti ([currentIsHls]) : le lecteur n'y voit qu'une piste, sans
     * langue fiable ; on garde celle qu'on avait demandée ([currentIndex]).
     * Sinon, la piste entendue retrouvée dans la liste du serveur.
     */
    fun indexForSwitch(currentIsHls: Boolean, currentIndex: Int?, heard: Heard?, tracks: List<AudioTrack>): Int? =
        if (currentIsHls) currentIndex else jellyfinIndex(heard, tracks)

    /**
     * La piste du serveur qui correspond à [heard] ; null si rien ne colle
     * (Jellyfin prend alors la première piste du fichier).
     *
     * Une piste d'une autre langue connue est écartée d'office. Entre les
     * autres : la langue entendue compte le plus, puis le rang dans le
     * fichier, puis le format et le nombre de canaux (deux pistes françaises :
     * TrueHD 7.1 et Dolby Digital 2.0 d'audiodescription). À égalité, la
     * première du fichier.
     */
    fun jellyfinIndex(heard: Heard?, tracks: List<AudioTrack>): Int? {
        if (heard == null || tracks.isEmpty()) return null
        val language = TrackLanguageLogic.normalize(heard.language)
        val codec = codecFamily(heard.mimeType)
        val candidates = tracks.withIndex().filter { (_, track) ->
            val trackLanguage = TrackLanguageLogic.normalize(track.language)
            language == null || trackLanguage == null || trackLanguage == language
        }
        return candidates.maxByOrNull { (rank, track) ->
            (if (language != null && TrackLanguageLogic.normalize(track.language) == language) 4 else 0) +
                (if (rank == heard.position) 3 else 0) +
                (if (codec != null && codecFamily(track.codec) == codec) 1 else 0) +
                (if (heard.channels > 0 && track.channels == heard.channels) 1 else 0)
        }?.value?.index
    }

    /** Adresse du flux converti avec la piste voulue : « …/sdr.m3u8?audio=2 » ; telle quelle sans piste. */
    fun withAudio(url: String, index: Int?): String {
        if (index == null || index < 0 || url.isBlank()) return url
        return url + (if ('?' in url) "&" else "?") + "audio=$index"
    }

    /**
     * Famille d'un format audio, qu'il vienne du lecteur (type MIME Media3 :
     * « audio/eac3-joc ») ou de Jellyfin (nom ffprobe : « eac3 ») ; null si inconnu.
     */
    fun codecFamily(value: String?): String? {
        val v = value?.trim()?.lowercase(Locale.ROOT)?.takeIf { it.isNotEmpty() } ?: return null
        return when {
            v == "eac3" || v == "audio/eac3" || v == "audio/eac3-joc" -> "eac3"
            v == "ac3" || v == "audio/ac3" -> "ac3"
            v == "truehd" || v == "mlp" || v == "audio/true-hd" || v == "audio/mlp" -> "truehd"
            v == "dts" || v.startsWith("audio/vnd.dts") -> "dts"
            v == "aac" || v == "audio/mp4a-latm" -> "aac"
            v == "flac" || v == "audio/flac" -> "flac"
            v == "opus" || v == "audio/opus" -> "opus"
            v == "vorbis" || v == "audio/vorbis" -> "vorbis"
            v == "mp3" || v == "mp2" || v == "mp1" || v.startsWith("audio/mpeg") -> "mpeg"
            v.startsWith("pcm") || v == "audio/raw" -> "pcm"
            v == "ac4" || v == "audio/ac4" -> "ac4"
            else -> v.substringAfter('/')
        }
    }

    /**
     * Piste du serveur telle que le panneau Audio la propose pendant un flux
     * converti : [index] Jellyfin à demander, libellé (langue, sinon titre,
     * sinon « Piste n »), détail (titre, format, canaux), [selected] pour la
     * piste lue.
     */
    data class Choice(val index: Int, val label: String, val detail: String, val selected: Boolean)

    /**
     * Pistes à proposer au panneau Audio pendant un flux converti, dans l'ordre
     * du fichier. [requested] : index demandé à Jellyfin (« ?audio=N »), null
     * si rien n'a été demandé ; la piste lue ([playedIndex]) est marquée.
     * [languageName] : « fre » → « Français », null si la langue est inconnue
     * (Tracks.kt l'a, la logique pure l'emprunte).
     */
    fun choices(tracks: List<AudioTrack>, requested: Int?, languageName: (String?) -> String?): List<Choice> {
        val played = playedIndex(tracks, requested)
        return tracks.mapIndexed { rank, track ->
            val language = languageName(track.language.ifBlank { null })
            val title = track.title.trim().takeIf { it.isNotEmpty() }
            Choice(
                index = track.index,
                label = language ?: title ?: "Piste ${rank + 1}",
                detail = listOfNotNull(
                    title?.takeIf { language != null },
                    codecName(track.codec),
                    channelsName(track.channels),
                ).joinToString(" · "),
                selected = track.index == played,
            )
        }
    }

    /**
     * Index Jellyfin de la piste qu'un flux converti porte : [requested] si elle
     * est dans la liste ; sinon celle que Jellyfin prend de lui-même sans
     * `AudioStreamIndex` (`MediaSourceInfo.GetDefaultAudioStream`) : la piste
     * marquée par défaut, sinon la première du fichier. Null sans liste.
     */
    fun playedIndex(tracks: List<AudioTrack>, requested: Int?): Int? =
        tracks.firstOrNull { requested != null && it.index == requested }?.index
            ?: tracks.firstOrNull { it.isDefault }?.index
            ?: tracks.firstOrNull()?.index

    /**
     * Piste [chosen] prise au panneau Audio pendant un flux converti : faut-il
     * recharger le flux ? Non si c'est déjà celle qui est lue, ou si elle n'est
     * pas dans la liste du serveur.
     */
    fun switchNeeded(tracks: List<AudioTrack>, requested: Int?, chosen: Int): Boolean =
        tracks.any { it.index == chosen } && chosen != playedIndex(tracks, requested)

    /**
     * Nom commercial d'un format audio nommé par Jellyfin (ffprobe : « eac3 »),
     * le même que celui du lecteur pour une piste Media3 (audioCodecName,
     * Tracks.kt) ; ffprobe ne dit pas l'Atmos ni le DTS-HD. Null si inconnu.
     */
    fun codecName(codec: String?): String? = when (val family = codecFamily(codec)) {
        null -> null
        "truehd" -> "Dolby TrueHD"
        "eac3" -> "Dolby Digital Plus"
        "ac3" -> "Dolby Digital"
        "ac4" -> "Dolby AC-4"
        "dts" -> "DTS"
        "aac" -> "AAC"
        "opus" -> "Opus"
        "flac" -> "FLAC"
        "mpeg" -> "MP3"
        "vorbis" -> "Vorbis"
        "pcm" -> "PCM"
        else -> family.uppercase(Locale.ROOT)
    }

    /** « 6 » → « 5.1 » ; null si inconnu. Le lecteur (Tracks.kt) s'en sert aussi. */
    fun channelsName(count: Int): String? = when {
        count <= 0 -> null
        count == 1 -> "Mono"
        count == 2 -> "Stéréo"
        count == 6 -> "5.1"
        count == 8 -> "7.1"
        else -> "$count canaux"
    }
}
