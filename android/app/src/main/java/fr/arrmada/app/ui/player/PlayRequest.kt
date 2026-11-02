package fr.arrmada.app.ui.player

/** Ce qu'il faut lancer : un film (TMDB) ou un épisode (TVDB + numéros). */
data class PlayRequest(
    val kind: String, // « movie » ou « episode »
    val id: Long, // TMDB du film, ou TVDB de la série
    val season: Int = 0,
    val episode: Int = 0,
    val radarrId: String? = null, // film : fiche Radarr (logo, distribution) pour le menu pause
    val sonarrId: String? = null, // épisode : fiche Sonarr (logo, épisode suivant)
    val startSeconds: Int = 0,
    val file: String? = null, // « file » : jeton de la vidéo (écran Vidéos)
    val localSeries: Int = 0, // « file » d'une série maison : titre, épisode suivant
)

/** Un titre est « vu » passé 90 % (le générique de fin ne compte pas). */
internal const val WATCHED_RATIO = 0.90

/** Épisode à enchaîner, avec ce qu'en montre la carte « Épisode suivant ». */
data class UpNext(val request: PlayRequest, val code: String, val title: String, val image: String?)
