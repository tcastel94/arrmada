package fr.arrmada.app.data

/**
 * Ordre et visibilité des rangées de l'accueil, réglables dans Réglages
 * (à la façon des « widgets » des skins Kodi comme Arctic Fuse, sans aller
 * jusqu'à cent options : on range, on masque, c'est tout).
 *
 * Stockage : une ligne de texte dans les préférences, les rangées dans
 * l'ordre, un « - » devant une rangée masquée :
 *   « resume,watchlist,-recent,foryou,upcoming »
 * Lecture tolérante (comme un parseur de .conf) : un nom inconnu est
 * ignoré, une rangée absente (ajoutée dans une version plus récente) est
 * remise à la fin, visible.
 */
object HomeLayoutLogic {

    /** Rangées de l'accueil : identifiant stocké, titre affiché. */
    enum class Row(val id: String, val label: String) {
        RESUME("resume", "Reprendre"),
        WATCHLIST("watchlist", "Ma liste"),
        RECENT("recent", "Ajouts récents"),
        FOR_YOU("foryou", "Pour toi"),
        UPCOMING("upcoming", "Bientôt"),
    }

    /** Une rangée et son état dans le réglage. */
    data class Slot(val row: Row, val visible: Boolean = true)

    /** Ordre d'origine : toutes les rangées, toutes visibles. */
    val DEFAULT: List<Slot> = Row.entries.map { Slot(it) }

    private const val HIDDEN = "-"

    /** Lit le réglage stocké (null ou vide : ordre d'origine). */
    fun parse(saved: String?): List<Slot> {
        if (saved.isNullOrBlank()) return DEFAULT
        val slots = mutableListOf<Slot>()
        saved.split(",").map { it.trim() }.filter { it.isNotEmpty() }.forEach { token ->
            val hidden = token.startsWith(HIDDEN)
            val row = Row.entries.firstOrNull { it.id == token.removePrefix(HIDDEN) } ?: return@forEach
            if (slots.none { it.row == row }) slots += Slot(row, visible = !hidden)
        }
        // Rangées inconnues du réglage stocké : à la fin, visibles
        Row.entries.filter { row -> slots.none { it.row == row } }.forEach { slots += Slot(it) }
        return slots
    }

    /** Écrit le réglage dans le format lu par [parse]. */
    fun serialize(slots: List<Slot>): String =
        slots.joinToString(",") { (if (it.visible) "" else HIDDEN) + it.row.id }

    /** Rangées à afficher, dans l'ordre. */
    fun visible(slots: List<Slot>): List<Row> = slots.filter { it.visible }.map { it.row }

    /** Affiche ou masque une rangée. */
    fun toggle(slots: List<Slot>, row: Row): List<Slot> =
        slots.map { if (it.row == row) it.copy(visible = !it.visible) else it }

    /** Monte une rangée d'un cran (sans effet sur la première). */
    fun moveUp(slots: List<Slot>, row: Row): List<Slot> {
        val index = slots.indexOfFirst { it.row == row }
        if (index <= 0) return slots
        return slots.toMutableList().apply { add(index - 1, removeAt(index)) }
    }
}
