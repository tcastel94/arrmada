package fr.arrmada.app.data

/** Ce que joue le bouton « Bande-annonce » d'un film. */
sealed interface TrailerSource {
    /** Fichier « -trailer » rangé sur le NAS : lu dans l'appli, avec le son. */
    data class Local(val stream: String) : TrailerSource

    /** Vidéo YouTube : ouverte dans l'appli YouTube de la TV ou du téléphone. */
    data class YouTube(val id: String) : TrailerSource

    data object None : TrailerSource
}

/**
 * Choix de la bande-annonce (testé sans écran).
 *
 * Le fichier du NAS d'abord : il se lit sans appli YouTube, en qualité
 * d'origine. Sinon YouTube : celle de TMDB (française si elle existe), puis
 * celle de Radarr (souvent en anglais, absente pour certains films).
 */
object TrailerLogic {
    /** Même règle que la web app : 11 caractères [A-Za-z0-9_-] (tolérance 6 à 20). */
    private val YOUTUBE_ID = Regex("^[\\w-]{6,20}$")

    fun youtubeId(vararg candidates: String?): String? =
        candidates.map { it?.trim().orEmpty() }.firstOrNull { YOUTUBE_ID.matches(it) }

    fun choose(info: TrailerInfo?, radarrYoutubeId: String?): TrailerSource {
        if (info != null && info.status == "ok" && info.stream.startsWith("/api/")) return TrailerSource.Local(info.stream)
        return youtubeId(info?.youtube, radarrYoutubeId)?.let { TrailerSource.YouTube(it) } ?: TrailerSource.None
    }

    /** Le bouton est-il utile ? (avant la réponse du serveur : l'identifiant de Radarr suffit) */
    fun available(info: TrailerInfo?, radarrYoutubeId: String?): Boolean = choose(info, radarrYoutubeId) != TrailerSource.None

    /**
     * Adresses à essayer, dans l'ordre : (appli visée, adresse). YouTube pour
     * Android TV d'abord (elle n'ouvre pas toujours `vnd.youtube:` sur la
     * Shield), puis l'appli YouTube du téléphone, puis n'importe quelle appli
     * qui sait ouvrir un lien YouTube (SmartTube, navigateur…).
     */
    fun youtubeTargets(id: String): List<Pair<String?, String>> = listOf(
        "com.google.android.youtube.tv" to "https://www.youtube.com/watch?v=$id",
        null to "vnd.youtube:$id",
        null to "https://www.youtube.com/watch?v=$id",
    )
}
