package fr.arrmada.app.data

import java.util.Locale

/**
 * Libellé d'une note : « IMDb 8,5 », « TMDB 7,1 ».
 *
 * Le serveur choisit la note la plus fiable (IMDb dès 1 000 votes, sinon
 * TMDB dès 50 votes) et dit d'où elle vient (`rating_source`) : la source est
 * toujours écrite, un 7 sur IMDb et un 7 sur TMDB ne se valent pas.
 */
object RatingLogic {
    fun format(value: Double): String = String.format(Locale.FRANCE, "%.1f", value)

    /** null : pas de note fiable (ou serveur ancien sans source et sans note). */
    fun label(value: Double?, source: String?): String? {
        if (value == null || value <= 0.0) return null
        val name = when (source) {
            "imdb" -> "IMDb"
            "tmdb", null, "" -> "TMDB" // serveur d'avant 2.13 : c'était TMDB
            else -> return null
        }
        return "$name ${format(value)}"
    }

    /**
     * Badges de la fiche d'un film : IMDb d'abord ; TMDB seulement sans IMDb ;
     * puis les critiques (Metacritic /100, Rotten Tomatoes en %).
     */
    fun detailBadges(ratings: Ratings): List<String> = buildList {
        ratings.imdb?.takeIf { it > 0 }?.let { add("IMDb ${format(it)}") }
            ?: ratings.tmdb?.takeIf { it > 0 }?.let { add("TMDB ${format(it)}") }
        ratings.metacritic?.takeIf { it > 0 }?.let { add("Metacritic ${it.toInt()}") }
        ratings.rottenTomatoes?.takeIf { it > 0 }?.let { add("Rotten Tomatoes ${it.toInt()} %") }
    }
}
