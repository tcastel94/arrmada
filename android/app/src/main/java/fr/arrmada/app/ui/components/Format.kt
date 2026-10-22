package fr.arrmada.app.ui.components

/*
 * Mise en forme des durées, sans dépendance Android (utilisée aussi par la
 * logique testée sur la machine de build).
 */

/** « 1 h 52 », « 47 min » */
fun formatDuration(seconds: Int): String {
    val h = seconds / 3600
    val m = (seconds % 3600) / 60
    return if (h > 0) "$h h ${"%02d".format(m)}" else "$m min"
}

/** « 1:02:05 », « 42:10 » */
fun formatClock(seconds: Long): String {
    val s = seconds.coerceAtLeast(0)
    val h = s / 3600
    val m = (s % 3600) / 60
    val sec = s % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, sec) else "%d:%02d".format(m, sec)
}
