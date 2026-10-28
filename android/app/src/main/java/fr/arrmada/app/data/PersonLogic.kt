package fr.arrmada.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Filmographie d'un acteur (GET /api/media/person/{tmdb}), la même que la
 * fenêtre « acteur » de la web app : ses films déjà dans Radarr d'un côté,
 * les autres (à télécharger) de l'autre. Titres et biographie en français
 * (TMDB fr-FR côté serveur).
 */
@Serializable
data class PersonInfo(
    @SerialName("tmdb_id") val tmdbId: Long = 0,
    val name: String = "",
    val photo: String? = null,
    val biography: String = "",
    @SerialName("known_for") val knownFor: String = "",
    val birthday: String? = null, // « 1964-09-02 »
    @SerialName("place_of_birth") val placeOfBirth: String? = null,
)

@Serializable
data class FilmCredit(
    @SerialName("tmdb_id") val tmdbId: Long = 0,
    val title: String = "",
    val year: Int? = null,
    val character: String = "",
    val poster: String? = null,
    @SerialName("vote_average") val voteAverage: Double = 0.0,
    @SerialName("radarr_id") val radarrId: Int? = null, // seulement « Dans ta médiathèque »
    @SerialName("has_file") val hasFile: Boolean = false,
)

@Serializable
data class Filmography(
    val error: String? = null,
    val person: PersonInfo? = null,
    @SerialName("in_library") val inLibrary: List<FilmCredit> = emptyList(),
    val discover: List<FilmCredit> = emptyList(),
)

/** Ce que fait OK sur une affiche de la filmographie. */
sealed interface CreditOpen {
    data class Movie(val radarrId: String, val tmdbId: Long) : CreditOpen
    data class Download(val target: DownloadTarget) : CreditOpen
}

/** Textes et choix de l'écran acteur (testés sans écran). */
object PersonLogic {
    private val DAY = DateTimeFormatter.ofPattern("d MMMM yyyy", Locale.FRENCH)

    private val JOBS = mapOf(
        "Acting" to "Acteur, actrice",
        "Directing" to "Réalisation",
        "Writing" to "Scénario",
        "Production" to "Production",
        "Sound" to "Musique",
    )

    /** « Acteur, actrice  ·  né(e) le 2 septembre 1964  ·  Beyrouth, Liban ». */
    fun meta(person: PersonInfo): String = listOfNotNull(
        JOBS[person.knownFor] ?: person.knownFor.ifBlank { null },
        birth(person.birthday)?.let { "né(e) le $it" },
        person.placeOfBirth?.takeIf { it.isNotBlank() },
    ).joinToString("  ·  ")

    /** « 1964-09-02 » → « 2 septembre 1964 » ; null si illisible. */
    fun birth(date: String?): String? = date?.takeIf { it.isNotBlank() }?.let {
        runCatching { LocalDate.parse(it.take(10)).format(DAY) }.getOrNull()
    }

    /** Ligne sous le titre du film survolé : « 1999  ·  Neo  ·  Sur le NAS ». */
    fun subtitle(credit: FilmCredit): String = listOfNotNull(
        credit.year?.toString(),
        credit.character.takeIf { it.isNotBlank() },
        when {
            credit.radarrId == null -> "Pas encore dans ta médiathèque"
            credit.hasFile -> "Sur le NAS"
            else -> "Demandé, pas encore téléchargé"
        },
    ).joinToString("  ·  ")

    /** OK : la fiche si le film est dans Radarr, sinon la feuille « Télécharger ». */
    fun open(credit: FilmCredit): CreditOpen {
        val radarr = credit.radarrId
        return if (radarr != null) {
            CreditOpen.Movie(radarr.toString(), credit.tmdbId)
        } else {
            CreditOpen.Download(
                DownloadTarget(kind = "movie", title = credit.title, year = credit.year, tmdbId = credit.tmdbId, poster = credit.poster)
            )
        }
    }
}
