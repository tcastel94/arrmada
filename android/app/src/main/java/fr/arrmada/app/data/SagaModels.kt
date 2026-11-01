package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/*
 * Sagas de films (GET /api/sagas/…, ADR-016) : les collections de Radarr
 * (TMDB), croisées avec la bibliothèque. Mêmes réponses que pour la web app.
 */

/**
 * Un film d'une saga. [state] : « available » (sur le NAS), « wanted »
 * (dans Radarr, recherché), « missing » (sorti, pas dans Radarr),
 * « upcoming » (annoncé), « excluded » (écarté dans Radarr).
 */
@Serializable
data class SagaFilm(
    @SerialName("tmdb_id") val tmdbId: Long = 0,
    @SerialName("movie_id") val movieId: Int? = null, // identifiant Radarr : ouvre la fiche du film
    val title: String = "",
    val year: Int? = null,
    val overview: String? = null,
    val runtime: Int? = null,
    val poster: String? = null,
    val state: String = "missing",
)

@Serializable
data class Saga(
    val id: Int = 0,
    @SerialName("tmdb_id") val tmdbId: Long = 0,
    val title: String = "",
    val overview: String? = null,
    val poster: String? = null,
    val fanart: String? = null,
    val posters: List<String> = emptyList(), // trois affiches pour l'éventail
    val total: Int = 0,
    val available: Int = 0,
    val wanted: Int = 0,
    val missing: Int = 0,
    val upcoming: Int = 0,
    val complete: Boolean = false,
    val years: List<Int> = emptyList(),
    val films: List<SagaFilm> = emptyList(), // seulement dans la fiche d'une saga
)

@Serializable
data class SagaList(
    val sagas: List<Saga> = emptyList(),
    val total: Int = 0,
    val incomplete: Int = 0,
    val upcoming: Int = 0,
)

@Serializable
data class SagaCompleteBody(@SerialName("tmdb_ids") val tmdbIds: List<Long>? = null)

@Serializable
data class SagaCompleteResult(
    val status: String = "",
    val added: List<String> = emptyList(),
    val message: String = "",
)

/** Libellés des sagas (sans interface : testés par SagaRulesTest). */
object SagaRules {
    /** Badge d'une saga : ce qui manque d'abord, puis ce qui est attendu. */
    fun badge(s: Saga): String = when {
        s.missing > 0 -> "${Fr.plural(s.missing, "film")} manquant${if (s.missing > 1) "s" else ""}"
        s.wanted > 0 -> "${s.wanted} en recherche"
        s.upcoming > 0 -> "${Fr.plural(s.upcoming, "film")} annoncé${if (s.upcoming > 1) "s" else ""}"
        else -> "Complète"
    }

    /** « 8 films · 2001 – 2011 · 6 sur le NAS ». */
    fun facts(s: Saga): String = listOfNotNull(
        Fr.plural(s.total, "film"),
        s.years.distinct().joinToString(" – ").ifBlank { null },
        "${s.available} sur le NAS",
    ).joinToString(" · ")

    /** Part de la saga sur le NAS (barre de progression). */
    fun progress(s: Saga): Float = if (s.total > 0) s.available.toFloat() / s.total else 0f

    /** Étiquette d'un film sur son affiche (null : sur le NAS, rien à signaler). */
    fun tag(f: SagaFilm): String? = when (f.state) {
        "wanted" -> "En recherche"
        "missing" -> "+ Ajouter"
        "upcoming" -> f.year?.let { "Annoncé $it" } ?: "Annoncé"
        "excluded" -> "Exclu"
        else -> null
    }

    /** Affiche grisée : pas sur le NAS et pas en route. */
    fun dimmed(f: SagaFilm): Boolean = f.state == "missing" || f.state == "upcoming" || f.state == "excluded"

    /** « 1 · 2001 ». */
    fun position(index: Int, f: SagaFilm): String = "${index + 1} · ${f.year ?: "?"}"
}
