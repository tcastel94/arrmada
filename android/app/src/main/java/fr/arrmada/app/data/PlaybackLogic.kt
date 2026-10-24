package fr.arrmada.app.data

/*
 * Règles « Passer l'intro » et « Épisode suivant », en Kotlin pur : testées
 * par PlaybackLogicTest sur la machine de build.
 *
 * Deux sources, comme dans l'add-on : les chapitres nommés du fichier
 * (« Intro », « Générique de fin »…) d'abord, puis les marqueurs calculés
 * par Jellyfin (plugin Intro Skipper) quand les chapitres ne disent rien.
 */
object PlaybackLogic {

    private val RECAP = Regex("(?i)(recap|récap|previously|précédemment|résumé)")
    private val INTRO = Regex("(?i)(intro|opening|ouverture|générique|generique)")
    private val CREDITS = Regex("(?i)(credits|crédits|générique|generique|outro|ending|end title)")

    /** Combien de secondes le bouton « Passer… » reste affiché au début du passage. */
    const val SKIP_BUTTON_SECONDS = 15.0

    /** Durée du compte à rebours de la carte « Épisode suivant ». */
    const val UP_NEXT_SECONDS = 10

    /** Sans générique repéré : la carte apparaît 30 s avant la fin. */
    private const val UP_NEXT_FALLBACK = 30.0

    /** Passages des chapitres nommés : [{kind: intro | recap | credits, start, end}]. */
    fun chapterSegments(chapters: List<Chapter>, duration: Double): List<Segment> {
        val sorted = chapters.sortedBy { it.start }
        return sorted.mapIndexedNotNull { i, chapter ->
            val end = sorted.getOrNull(i + 1)?.start ?: duration
            val firstHalf = chapter.start < duration / 2
            val kind = when {
                RECAP.containsMatchIn(chapter.name) -> "recap"
                firstHalf && INTRO.containsMatchIn(chapter.name) -> "intro"
                !firstHalf && CREDITS.containsMatchIn(chapter.name) -> "credits"
                else -> null
            }
            if (kind == null || end - chapter.start < 2) null else Segment(kind, chapter.start, end)
        }
    }

    /** Intro et récap à proposer de passer (chapitres d'abord, sinon Jellyfin). */
    fun skippable(info: PlayInfo, duration: Double): List<Segment> {
        val fromChapters = chapterSegments(info.chapters, duration).filter { it.kind != "credits" }
        if (fromChapters.isNotEmpty()) return fromChapters
        return info.segments.filter { it.kind == "intro" || it.kind == "recap" }
    }

    /** Passage en cours à proposer de passer, ou null (bouton visible ses 15 premières secondes). */
    fun activeSkip(skips: List<Segment>, position: Double): Segment? = skips.firstOrNull {
        position >= it.start && position < it.end - 1 && position < it.start + SKIP_BUTTON_SECONDS
    }

    fun skipLabel(segment: Segment): String = if (segment.kind == "recap") "Passer le récap" else "Passer l’intro"

    /** Début du générique de fin (chapitre nommé, sinon marqueur Jellyfin), ou null. */
    fun creditsStart(info: PlayInfo, duration: Double): Double? =
        chapterSegments(info.chapters, duration).firstOrNull { it.kind == "credits" }?.start
            ?: info.segments.firstOrNull { it.kind == "credits" }?.start

    /** Moment où la carte « Épisode suivant » apparaît. */
    fun upNextAt(info: PlayInfo, duration: Double): Double =
        creditsStart(info, duration) ?: (duration - UP_NEXT_FALLBACK).coerceAtLeast(0.0)
}
