package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * Trakt (ADR-022) : note de fin de lecture, sur le compte Trakt du profil qui
 * regarde. Le serveur dit quoi proposer (film ; épisode, puis saison et série
 * au dernier épisode) ; la TV montre 5 étoiles à demi-étoiles, soit les 10
 * niveaux de Trakt. La lecture en direct (scrobble) ne passe pas par ici : le
 * serveur relaie le flux « lecture en cours » déjà envoyé pour la tablette.
 */

/** GET /api/trakt/prompt : notes à proposer à la fin (vide : profil sans compte Trakt). */
@Serializable
data class TraktPrompt(
    val linked: Boolean = false,
    val steps: List<TraktStep> = emptyList(),
)

/**
 * Une note à proposer : « movie », « episode », « season » ou « show », son
 * libellé, et la note déjà donnée ([current], 1 à 10) pour pré-remplir la carte.
 */
@Serializable
data class TraktStep(val kind: String = "", val label: String = "", val current: Int? = null)

/** GET /api/trakt/ratings : mes notes d'un film, ou d'une série (saisons « 2 », épisodes « 2x3 »). */
@Serializable
data class TraktMyRatings(
    val linked: Boolean = false,
    val movie: Int? = null,
    val show: Int? = null,
    val seasons: Map<String, Int> = emptyMap(),
    val episodes: Map<String, Int> = emptyMap(),
)

/** POST /api/trakt/rate. */
@Serializable
data class TraktRateBody(
    val kind: String,
    val rating: Int,
    @SerialName("tmdb_id") val tmdbId: Long? = null,
    @SerialName("tvdb_id") val tvdbId: Long? = null,
    val season: Int? = null,
    val episode: Int? = null,
    val title: String = "",
)

@Serializable
data class TraktRateResult(val ok: Boolean = false, val message: String = "")

object TraktLogic {
    /** Note Trakt de 0 (rien choisi) à 10 ; une demi-étoile = 1. */
    const val MAX = 10

    enum class Star { FULL, HALF, EMPTY }

    /** ← / → : une demi-étoile de moins / de plus, bornée entre 0 et 10. */
    fun step(rating: Int, forward: Boolean): Int = (rating + if (forward) 1 else -1).coerceIn(0, MAX)

    /** État de l'étoile [index] (0 à 4) pour une note de 0 à 10. */
    fun star(index: Int, rating: Int): Star = when {
        rating >= (index + 1) * 2 -> Star.FULL
        rating == index * 2 + 1 -> Star.HALF
        else -> Star.EMPTY
    }

    /** « 3,5 » pour 7. */
    fun stars(rating: Int): String = if (rating % 2 == 0) "${rating / 2}" else "${rating / 2},5"

    /** Libellés de Trakt, traduits (mêmes que le serveur). */
    private val LABELS = listOf(
        "", "Nul", "Très mauvais", "Mauvais", "Bof", "Moyen", "Correct", "Bien", "Très bien", "Excellent", "Chef-d'œuvre",
    )

    fun label(rating: Int): String = LABELS.getOrElse(rating) { "" }

    /** Les notes ne s'envoient que pour un film (TMDB) ou un épisode d'une série Sonarr (TVDB). */
    fun eligible(kind: String, id: Long, localSeries: Boolean): Boolean =
        id > 0 && !localSeries && (kind == "movie" || kind == "episode")

    /** Corps de la note d'une étape, pour le titre en cours de lecture. */
    fun body(step: TraktStep, rating: Int, kind: String, id: Long, season: Int, episode: Int, title: String): TraktRateBody =
        TraktRateBody(
            kind = step.kind,
            rating = rating,
            tmdbId = id.takeIf { kind == "movie" },
            tvdbId = id.takeIf { kind == "episode" },
            season = season.takeIf { kind == "episode" && step.kind in setOf("episode", "season") },
            episode = episode.takeIf { kind == "episode" && step.kind == "episode" },
            title = title,
        )

    /** Requête GET /api/trakt/prompt pour le titre en cours (TMDB du film : sa note actuelle). */
    fun promptPath(kind: String, id: Long, season: Int, episode: Int): String =
        if (kind == "movie") "/api/trakt/prompt?kind=movie&tmdb_id=$id"
        else "/api/trakt/prompt?kind=episode&tvdb_id=$id&season=$season&episode=$episode"

    /** Note de départ de la carte : celle déjà donnée, sinon rien de choisi. */
    fun initial(step: TraktStep): Int = (step.current ?: 0).coerceIn(0, MAX)

    /** Pastille de la fiche : « Ma note ★ 3,5 » ; null sans note (ou profil sans Trakt). */
    fun badge(rating: Int?): String? = rating?.takeIf { it in 1..MAX }?.let { "Ma note ★ ${stars(it)}" }

    /** GET /api/trakt/ratings d'un film (TMDB) ou d'une série (TVDB). */
    fun ratingsPath(movie: Boolean, id: Long): String =
        if (movie) "/api/trakt/ratings?kind=movie&tmdb_id=$id" else "/api/trakt/ratings?kind=show&tvdb_id=$id"
}
