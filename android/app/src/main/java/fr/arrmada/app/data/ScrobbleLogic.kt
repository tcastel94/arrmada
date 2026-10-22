package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * « Lecture en cours » envoyée au serveur (POST /api/kodi/scrobble), comme le
 * faisait l'add-on Kodi : c'est elle qui alimente l'écran d'appoint (la
 * tablette sous la TV : affiche, heure de fin, progression) et qui passe la
 * tablette en mode séance (Fully Kiosk). La pièce est celle de la TV
 * appairée : le serveur la connaît par le jeton.
 *
 * Événements : play (début), pause, resume, progress (toutes les 30 s
 * pendant la lecture), stop (fin ou sortie du lecteur).
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
)

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
            return what.copy(event = event, percentage = if (ended) 100.0 else percent, position = null, total = null, paused = null)
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
