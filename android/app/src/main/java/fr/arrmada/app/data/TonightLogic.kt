package fr.arrmada.app.data

import java.time.LocalDateTime

/**
 * « Ce soir » : ce qu'on peut regarder avant l'heure choisie, comme
 * l'add-on (tonight_data.py). Onglets « Avant 22:00 », « Avant 22:30 »…
 * « Sans limite » ; on ne garde que ce qui sera FINI avant l'heure dite, en
 * partant de maintenant. C'est un `at` à l'envers : au lieu de « lance ça
 * à 22 h », on demande « qu'est-ce qui tient avant 22 h ».
 *
 * Candidats : ce qui est commencé (il reste durée − reprise), puis les films
 * jamais vus de la médiathèque, du plus récemment ajouté au plus ancien.
 */
object TonightLogic {
    private const val LEAD_MINUTES = 45L // le 1er horaire laisse au moins 45 min
    private const val STEP_MINUTES = 30L // puis un horaire toutes les 30 min
    private const val SLOTS = 5 // horaires proposés avant « Sans limite »
    private const val TARGET_MINUTES = 120L // onglet ouvert d'office : le 1er à 2 h ou plus
    private const val LIMIT = 40 // éléments examinés par groupe

    data class Slot(val label: String, val deadline: LocalDateTime?)

    enum class Group { RESUME, FRESH }

    data class Row(
        val title: String,
        val subtitle: String,
        val group: Group,
        val remaining: Int, // secondes ; 0 = durée inconnue
        val item: LibraryItem?, // film ou série de la médiathèque (images, fiche)
        val state: WatchState?, // reprise (groupe RESUME)
    )

    /** 22:14 à la minute la plus proche ; minuit → « minuit ». */
    fun clock(moment: LocalDateTime): String {
        val m = moment.plusSeconds(30)
        return if (m.hour == 0 && m.minute == 0) "minuit" else "%02d:%02d".format(m.hour, m.minute)
    }

    /** Heure ronde ou demi-heure suivante (22:07 → 22:30, 22:30 → 22:30). */
    private fun roundUp(moment: LocalDateTime): LocalDateTime {
        var base = moment.withSecond(0).withNano(0)
        if (moment.second > 0 || moment.nano > 0) base = base.plusMinutes(1)
        val extra = ((30 - base.minute % 30) % 30).toLong()
        return base.plusMinutes(extra)
    }

    /** À 20:47 : 20:47 + 45 min = 21:32, arrondi à 22:00 → Avant 22:00, 22:30, 23:00, 23:30, minuit, Sans limite. */
    fun slots(now: LocalDateTime): List<Slot> {
        val first = roundUp(now.plusMinutes(LEAD_MINUTES))
        return (0 until SLOTS).map { i ->
            val moment = first.plusMinutes(STEP_MINUTES * i)
            Slot("Avant ${clock(moment)}", moment)
        } + Slot("Sans limite", null)
    }

    /** Onglet ouvert d'office : le 1er qui laisse 2 h (la durée d'un film). */
    fun defaultSlot(slots: List<Slot>, now: LocalDateTime): Int {
        val index = slots.indexOfFirst { it.deadline != null && !it.deadline.isBefore(now.plusMinutes(TARGET_MINUTES)) }
        return if (index >= 0) index else slots.lastIndex.coerceAtLeast(0)
    }

    fun candidates(states: List<WatchState>, movies: List<LibraryItem>, series: List<LibraryItem>): List<Row> {
        val moviesByTmdb = movies.associateBy { it.tmdbId?.toString() }
        val seriesByTvdb = series.associateBy { it.tmdbId?.toString() } // tmdb_id = TVDB pour une série
        val resume = states
            .filter { !it.watched && it.position > 0 }
            .sortedByDescending { it.updatedAt }
            .distinctBy { if (it.mediaType == "episode") "s:${it.id}" else "m:${it.id}" }
            .take(LIMIT)
            .map { state ->
                val episode = state.mediaType == "episode"
                val item = if (episode) seriesByTvdb[state.id] else moviesByTmdb[state.id]
                Row(
                    title = item?.title ?: state.title,
                    subtitle = if (episode) "S%02dE%02d".format(state.season ?: 0, state.episode ?: 0) else item?.year?.toString().orEmpty(),
                    group = Group.RESUME,
                    remaining = if (state.total > 0) (state.total - state.position).coerceAtLeast(0) else 0,
                    item = item,
                    state = state,
                )
            }
        val known = states.filter { it.mediaType == "movie" && (it.watched || it.position > 0) }.map { it.id }.toSet()
        val fresh = movies
            .filter { it.hasFile && it.tmdbId?.toString() !in known }
            .take(LIMIT)
            .map { Row(it.title, it.year?.toString().orEmpty(), Group.FRESH, (it.runtime ?: 0) * 60, it, null) }
        return resume + fresh
    }

    private fun duration(seconds: Int): String {
        val h = seconds / 3600
        val m = (seconds % 3600) / 60
        return if (h > 0) "$h h ${"%02d".format(m)}" else "$m min"
    }

    private fun clockOf(seconds: Int): String {
        val h = seconds / 3600
        val m = (seconds % 3600) / 60
        val s = seconds % 60
        return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
    }

    /** « Reprise à 42:10 · reste 1 h 12 · fini vers 22:14 », « 1 h 52 · fini vers 22:40 ». */
    fun status(row: Row, now: LocalDateTime): String {
        val finish = if (row.remaining > 0) now.plusSeconds(row.remaining.toLong()) else null
        val head = when (row.group) {
            Group.RESUME -> "Reprise à ${clockOf(row.state?.position ?: 0)}"
            Group.FRESH -> if (row.remaining > 0) duration(row.remaining) else ""
        }
        val tail = when {
            finish == null -> "durée inconnue"
            row.group == Group.RESUME -> "reste ${duration(row.remaining)} · fini vers ${clock(finish)}"
            else -> "fini vers ${clock(finish)}"
        }
        return listOf(head, tail).filter { it.isNotEmpty() }.joinToString(" · ")
    }

    /** Ce qui sera fini avant l'heure de [slot] (durée inconnue : seulement « Sans limite »). */
    fun rows(rows: List<Row>, slot: Slot, now: LocalDateTime): List<Row> = rows.filter { row ->
        val deadline = slot.deadline ?: return@filter true
        row.remaining > 0 && !now.plusSeconds(row.remaining.toLong()).isAfter(deadline)
    }
}
