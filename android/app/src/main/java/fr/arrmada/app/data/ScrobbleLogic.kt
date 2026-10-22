package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.intOrNull

/**
 * « Lecture en cours » envoyée au serveur (POST /api/kodi/scrobble), comme le
 * faisait l'add-on Kodi : c'est elle qui alimente l'écran d'appoint (la
 * tablette sous la TV : affiche, heure de fin, progression) et qui passe la
 * tablette en mode séance (Fully Kiosk). La pièce est celle de la TV
 * appairée : le serveur la connaît par le jeton.
 *
 * Événements : play (début), pause, resume, progress (toutes les 30 s
 * pendant la lecture, et aussitôt après un changement de piste ou une
 * commande de la tablette), stop (fin ou sortie du lecteur).
 *
 * En plus de ce qu'envoyait Kodi : formats (4K, Dolby Vision, Atmos…),
 * pistes, chapitre, « Passer l'intro », générique, épisode suivant, fiche
 * (résumé, distribution) et `remote` : cette TV accepte la télécommande
 * tactile de la tablette.
 */
@Serializable
data class Scrobble(
    val event: String = "progress",
    val title: String = "",
    @SerialName("media_type") val mediaType: String = "movie", // « movie » ou « episode »
    @SerialName("tmdb_id") val tmdbId: Long? = null, // film : l'écran retrouve l'affiche
    val season: Int? = null,
    val episode: Int? = null,
    @SerialName("episode_title") val episodeTitle: String = "",
    val year: Int? = null,
    val percentage: Double = 0.0,
    val position: Int? = null, // secondes
    val total: Int? = null, // secondes
    val paused: Boolean? = null,
    // ── Écran enrichi (appli Android) ──
    val video: String = "", // « 4K · Dolby Vision »
    val audio: String = "", // « Français · TrueHD Atmos · 7.1 »
    @SerialName("subtitle_track") val subtitleTrack: String = "",
    val chapter: String = "",
    @SerialName("credits_at") val creditsAt: Double = 0.0, // début du générique (s), 0 : inconnu
    @SerialName("next_up") val nextUp: String = "", // « S02E04 · Titre »
    val skips: List<ScrobbleSkip> = emptyList(),
    val overview: String = "",
    @SerialName("meta_line") val metaLine: String = "",
    val cast: List<ScrobbleCast> = emptyList(),
    @SerialName("subtitle_tracks") val subtitleTracks: List<ScrobbleTrack> = emptyList(),
    @SerialName("audio_tracks") val audioTracks: List<ScrobbleTrack> = emptyList(),
    val remote: Boolean = false,
)

/** Passage à sauter (intro, récap) : la tablette affiche « Passer l'intro » dedans. */
@Serializable
data class ScrobbleSkip(val kind: String, val label: String, val start: Double, val end: Double)

@Serializable
data class ScrobbleCast(val name: String, val character: String = "", val photo: String = "")

/** Piste proposée sur la tablette ; [index] : rang dans la liste du menu pause. */
@Serializable
data class ScrobbleTrack(val index: Int, val label: String, val detail: String = "", val selected: Boolean = false)

/** Commande de la tablette (voir le serveur, tv_remote.py). */
@Serializable
data class RemoteCommand(val id: Long = 0, val action: String = "", val value: JsonElement? = null) {
    /** « seek » : décalage en secondes. */
    val seconds: Int? get() = (value as? JsonPrimitive)?.intOrNull

    /** « track » : (« text » | « audio », rang), rang −1 = sous-titres coupés. */
    val track: Pair<String, Int>? get() {
        val obj = value as? JsonObject ?: return null
        val type = (obj["type"] as? JsonPrimitive)?.content ?: return null
        val index = (obj["index"] as? JsonPrimitive)?.intOrNull ?: return null
        return type to index
    }
}

@Serializable
data class RemotePage(@SerialName("last_id") val lastId: Long = 0, val commands: List<RemoteCommand> = emptyList())

object ScrobbleLogic {

    /** Délai entre deux relevés pendant la lecture (l'écran extrapole entre les deux). */
    const val PROGRESS_EVERY_MS = 30_000L

    /**
     * Corps à envoyer, à partir de [what] (titre, épisode…) : même règles que
     * l'add-on Kodi. « stop » : 100 % si la vidéo est allée au bout, sinon le
     * pourcentage atteint (le serveur note « vu » à partir de 90 %).
     */
    fun payload(event: String, what: Scrobble, positionS: Double, totalS: Double, paused: Boolean = false, ended: Boolean = false): Scrobble {
        val position = positionS.coerceAtLeast(0.0)
        val total = totalS.coerceAtLeast(0.0)
        val percent = if (total > 0) Math.round(position / total * 1000) / 10.0 else 0.0
        if (event == "stop") {
            // Fin de séance : l'identité suffit, pas la fiche ni les pistes
            return Scrobble(
                event = event, title = what.title, mediaType = what.mediaType, tmdbId = what.tmdbId,
                season = what.season, episode = what.episode, episodeTitle = what.episodeTitle, year = what.year,
                percentage = if (ended) 100.0 else percent,
            )
        }
        return what.copy(
            event = event,
            percentage = percent,
            position = position.toInt(),
            total = total.toInt(),
            paused = paused || event == "pause",
        )
    }

    /**
     * Format de l'image : « 4K · Dolby Vision », « 1080p · SDR (converti) ».
     * [height] : hauteur de la piste lue ; [fileBadges] : pastilles de la fiche
     * (Radarr / Sonarr) en secours ; [videoRange] : VideoRangeType de Jellyfin.
     */
    fun videoLabel(height: Int?, fileBadges: List<String>, videoRange: String, toneMapped: Boolean): String {
        val resolution = when {
            height == null || height <= 0 -> fileBadges.firstOrNull { it == "4K" || it.endsWith("p") }
            height >= 2000 -> "4K"
            height >= 1000 -> "1080p"
            height >= 700 -> "720p"
            else -> "SD"
        }
        val range = when {
            toneMapped -> "SDR (converti)"
            videoRange.startsWith("DOVI") -> "Dolby Vision"
            videoRange == "HDR10Plus" -> "HDR10+"
            videoRange == "HDR10" || videoRange == "HDR" -> "HDR10"
            videoRange == "HLG" -> "HLG"
            else -> fileBadges.firstOrNull { it == "Dolby Vision" || it == "HDR10+" || it == "HDR" }
        }
        return listOfNotNull(resolution, range).joinToString(" · ")
    }

    private val GENERIC_CHAPTER = Regex("""^(chapitre|chapter)\s*\d+$""", RegexOption.IGNORE_CASE)

    /** Nom du chapitre en cours (vide pour « Chapitre 3 », qui n'apprend rien). */
    fun chapterAt(chapters: List<Chapter>, positionS: Double): String {
        val name = chapters.lastOrNull { it.start <= positionS }?.name.orEmpty().trim()
        return if (GENERIC_CHAPTER.matches(name)) "" else name
    }

    /**
     * Ce qui passe à l'écran : titre du film ou de la SÉRIE (l'écran retrouve
     * l'affiche avec), numéros et titre de l'épisode.
     * [subtitle] : « S02E03 · Static » (menu pause) → « Static ».
     */
    fun identity(kind: String, id: Long, season: Int, episode: Int, title: String, subtitle: String?, localSeries: Boolean): Scrobble {
        val isEpisode = kind == "episode" || localSeries
        return Scrobble(
            title = title,
            mediaType = if (isEpisode) "episode" else "movie",
            tmdbId = id.takeIf { kind == "movie" && it > 0 },
            season = season.takeIf { isEpisode && (season > 0 || episode > 0) },
            episode = episode.takeIf { isEpisode && episode > 0 },
            episodeTitle = subtitle?.substringAfter(" · ", "").orEmpty(),
        )
    }
}
