package fr.arrmada.app.ui.player

import fr.arrmada.app.data.FileInfo
import fr.arrmada.app.data.MovieDetail
import fr.arrmada.app.data.Person
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.SeriesDetail
import fr.arrmada.app.data.TrackLanguageLogic

/**
 * Ce que le menu pause affiche du titre en cours, qu'il s'agisse d'un film
 * (fiche Radarr) ou d'un épisode (fiche Sonarr de la série).
 */
data class PlaybackMeta(
    val title: String,
    val subtitle: String? = null, // « S02E03 · Static » pour un épisode
    val logo: String? = null, // adresse brute (rendue absolue à l'affichage)
    val overview: String? = null,
    val metaLine: String? = null, // « 2021 · Science-fiction · Réalisé par … »
    val cast: List<Person> = emptyList(),
    val file: FileInfo? = null, // pour les pastilles 4K, Atmos…
    val originalLanguage: String? = null, // « fr », « en »… : pistes choisies d'office
)

fun MovieDetail.toMeta() = PlaybackMeta(
    title = title,
    logo = images.bestLogo,
    overview = overview,
    metaLine = listOfNotNull(
        year?.toString(),
        genres.take(3).joinToString(", ").ifBlank { null },
        crew.firstOrNull { it.job == "Director" }?.let { "Réalisé par ${it.name}" },
    ).joinToString("  ·  "),
    cast = cast,
    file = file,
    originalLanguage = TrackLanguageLogic.isoCode(originalLanguage),
)

fun SeriesDetail.toMeta(season: Int, episode: Int, info: PlayInfo?): PlaybackMeta {
    val ep = seasons.firstOrNull { it.seasonNumber == season }?.episodes?.firstOrNull { it.episodeNumber == episode }
    val episodeTitle = ep?.title?.takeIf { it.isNotBlank() } ?: info?.title
    return PlaybackMeta(
        title = title,
        subtitle = "S%02dE%02d".format(season, episode) + (episodeTitle?.let { " · $it" } ?: ""),
        logo = images.bestLogo,
        overview = ep?.overview?.takeIf { it.isNotBlank() } ?: info?.overview,
        metaLine = listOfNotNull(year?.toString(), network?.takeIf { it.isNotBlank() }, genres.take(2).joinToString(", ").ifBlank { null })
            .joinToString("  ·  "),
        file = ep?.file,
        originalLanguage = TrackLanguageLogic.isoCode(originalLanguage),
    )
}
