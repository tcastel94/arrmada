package fr.arrmada.app.data

import java.time.LocalDateTime
import java.time.ZoneId

/**
 * Écran Téléchargements : ce qu'affichent les cartes « Pour ce soir » et
 * les lignes de la file, et les actions de chacune. Mêmes règles que
 * l'add-on (board_data.py, screens_data.py), testées en JVM.
 */
object BoardLogic {

    /** Import + sous-titres après la fin du téléchargement : marge ajoutée à « Prêt vers ». */
    private const val READY_MARGIN_MINUTES = 2L

    val STEPS = listOf("Trouvé", "Télécharg.", "Import", "Sous-titres", "Prêt")

    enum class Step { DONE, NOW, ERROR, TODO }

    enum class Action(val label: String) {
        UNSTICK("Débloquer"),
        SEARCH("Relancer la recherche"),
        DETAIL("Fiche du titre"),
        CANCEL("Annuler ma demande"),
        TOP("Passer en tête"),
        PAUSE("Mettre en pause"),
        RESUME("Reprendre"),
    }

    /** Couleur d'une ligne de la file (bande à gauche, pastille d'état). */
    enum class Family { ACTIVE, PAUSED, QUEUED, IMPORT, ERROR, DONE }

    // ── Cartes « Pour ce soir » ──

    data class Card(
        val headline: String,
        val detail: String,
        val who: String,
        val steps: List<Step>,
        val progress: Float,
        val tone: Tone,
        val actions: List<Action>,
    )

    enum class Tone { NORMAL, READY, BLOCKED }

    private val HEADLINES = mapOf(
        "searching" to "Recherche d’une version…",
        "importing" to "Import sur le NAS…",
        "subtitles" to "Sous-titres en cours…",
        "ready" to "Prêt à regarder",
        "notfound" to "Introuvable pour l’instant",
    )

    private fun steps(phase: String): List<Step> {
        val d = Step.DONE
        val n = Step.NOW
        val t = Step.TODO
        return when (phase) {
            "searching" -> listOf(n, t, t, t, t)
            "downloading" -> listOf(d, n, t, t, t)
            "importing" -> listOf(d, d, n, t, t)
            "subtitles" -> listOf(d, d, d, n, t)
            "ready" -> listOf(d, d, d, d, d)
            "notfound" -> listOf(Step.ERROR, t, t, t, t)
            else -> listOf(t, t, t, t, t)
        }
    }

    /** « sous-titres français »… ; vide si rien à dire. */
    fun subtitlesLabel(code: String?): String = when (code) {
        "fr" -> "sous-titres français"
        "en" -> "sous-titres anglais seulement"
        "missing" -> "sous-titres pas encore trouvés"
        else -> ""
    }

    /** Heure à laquelle ce sera prêt (fin du téléchargement + import), arrondie à la minute supérieure. */
    fun readyAt(seconds: Long?, now: LocalDateTime): String {
        if (seconds == null) return ""
        var moment = now.plusSeconds(seconds).plusMinutes(READY_MARGIN_MINUTES)
        if (moment.second > 0 || moment.nano > 0) moment = moment.withSecond(0).withNano(0).plusMinutes(1)
        return "%02d:%02d".format(moment.hour, moment.minute)
    }

    fun cardActions(card: BoardCard): List<Action> = buildList {
        if (card.phase == "blocked" && card.blockedDownload != null) add(Action.UNSTICK)
        if (card.phase == "searching" || card.phase == "notfound") add(Action.SEARCH)
        if (card.arrId != null) add(Action.DETAIL)
        if (card.canCancel) add(Action.CANCEL)
    }

    fun card(card: BoardCard, now: LocalDateTime, zone: ZoneId = ZoneId.systemDefault()): Card {
        val phase = card.phase
        val pct = card.progress
        var states = steps(phase)
        if (phase == "blocked") {
            // Bloqué au téléchargement, ou à l'import s'il est complet
            states = if (pct >= 100) {
                listOf(Step.DONE, Step.DONE, Step.ERROR, Step.TODO, Step.TODO)
            } else {
                listOf(Step.DONE, Step.ERROR, Step.TODO, Step.TODO, Step.TODO)
            }
        }
        if (phase == "ready" && card.subtitles in listOf("missing", "off", "", null)) {
            states = states.toMutableList().also { it[3] = Step.TODO } // prêt sans sous-titres
        }
        val headline = when (phase) {
            "downloading" -> readyAt(card.timeLeftSeconds, now).let { if (it.isNotEmpty()) "Prêt vers $it" else "Téléchargement ${pct.toInt()} %" }
            "blocked" -> "Bloqué"
            else -> HEADLINES[phase].orEmpty()
        }
        val who = listOfNotNull(
            card.deviceName?.takeIf { it.isNotBlank() } ?: "TV",
            Fr.ago(card.requestedAt, now, zone).ifBlank { null },
            card.quality?.takeIf { it.isNotBlank() },
            card.sizeBytes.takeIf { it > 0 }?.let { Fr.bytes(it) },
        ).joinToString(" · ")
        val detail = when (phase) {
            "blocked" -> short(card.error.ifBlank { "Le téléchargement n’avance plus" })
            "downloading" -> "${pct.toInt()} %" + if (card.protocol == "torrent") " · torrent : pas de priorité possible" else ""
            "notfound" -> "Aucune release pour l’instant"
            "subtitles" -> "Recherche Bazarr : français, sinon anglais"
            "ready" -> subtitlesLabel(card.subtitles).replaceFirstChar { it.uppercase() }
            else -> ""
        }
        val tone = when (phase) {
            "ready" -> Tone.READY
            "blocked" -> Tone.BLOCKED
            else -> Tone.NORMAL
        }
        return Card(headline, detail, who, states, (pct / 100).toFloat().coerceIn(0f, 1f), tone, cardActions(card))
    }

    private fun short(text: String, limit: Int = 70): String {
        val clean = text.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        return if (clean.length <= limit) clean else clean.take(limit - 1).trimEnd() + "…"
    }

    // ── Lignes de la file ──

    data class Row(
        val label: String,
        val family: Family,
        val meta: String,
        val percent: String,
        val progress: Float,
        val sizes: String,
        val eta: String,
        val actions: List<Action>,
    )

    private val STATUS = mapOf(
        "downloading" to ("En cours" to Family.ACTIVE),
        "paused" to ("En pause" to Family.PAUSED),
        "queued" to ("En attente" to Family.QUEUED),
        "delay" to ("En attente" to Family.QUEUED),
        "importpending" to ("Import en attente" to Family.IMPORT),
        "importing" to ("Import…" to Family.IMPORT),
        "importblocked" to ("Import bloqué" to Family.ERROR),
        "failed" to ("Échec" to Family.ERROR),
        "failedpending" to ("Échec" to Family.ERROR),
        "warning" to ("Attention" to Family.ERROR),
        "completed" to ("Terminé" to Family.DONE),
    )

    // États de *arr qui priment sur celui du client de téléchargement
    private val TRACKED_FIRST = setOf("importpending", "importing", "importblocked", "failedpending", "failed")

    /**
     * (libellé, famille) d'un élément de la file. Pendant le téléchargement,
     * *arr dit « downloading » même si SABnzbd est en pause : c'est alors
     * l'état du client qui dit vrai ; après, c'est l'étape d'import.
     */
    fun status(item: QueueItem): Pair<String, Family> {
        if (item.error.isNotBlank()) return "Erreur" to Family.ERROR
        val tracked = item.trackedState.lowercase()
        val client = item.status.lowercase()
        val order = if (tracked in TRACKED_FIRST) listOf(tracked, client) else listOf(client, tracked)
        return order.firstNotNullOfOrNull { STATUS[it] } ?: ("En cours" to Family.ACTIVE)
    }

    fun rowActions(item: QueueItem, family: Family): List<Action> = buildList {
        val usenet = !item.downloadId.isNullOrBlank() && item.protocol == "usenet"
        if (family == Family.ERROR && !item.downloadId.isNullOrBlank()) add(Action.UNSTICK)
        if (usenet && family in listOf(Family.ACTIVE, Family.QUEUED, Family.PAUSED)) {
            add(Action.TOP)
            add(if (family == Family.PAUSED) Action.RESUME else Action.PAUSE)
        }
        if (item.arrId != null) add(Action.DETAIL)
    }

    /** [speed] : débit estimé par l'écran (octets/s), 0 si inconnu. */
    fun row(item: QueueItem, speed: Double = 0.0): Row {
        val (label, family) = status(item)
        val meta = if (family == Family.ERROR && (item.error.isNotBlank() || item.detail.isNotBlank())) {
            short(item.error.ifBlank { item.detail }, 90)
        } else {
            listOfNotNull(
                item.serviceType.replaceFirstChar { it.uppercase() }.ifBlank { null },
                item.downloadClient?.takeIf { it.isNotBlank() },
                item.quality?.takeIf { it.isNotBlank() },
                item.indexer?.takeIf { it.isNotBlank() },
            ).joinToString(" · ")
        }
        val sizes = if (item.sizeBytes > 0) "${Fr.bytes(item.sizeBytes - item.sizeLeftBytes)} / ${Fr.bytes(item.sizeBytes)}" else ""
        val eta = listOf(Fr.timeLeft(item.timeLeft), if (speed > 0) "${Fr.bytes(speed)}/s" else "")
            .filter { it.isNotEmpty() }.joinToString(" · ")
        return Row(
            label = label,
            family = family,
            meta = meta,
            percent = "${item.progress.toInt()} %",
            progress = (item.progress / 100).toFloat().coerceIn(0f, 1f),
            sizes = sizes,
            eta = eta,
            actions = rowActions(item, family),
        )
    }

    /** En-tête : « 2 pour ce soir · 7 en file · 48,2 Mo/s · SABnzbd en pause (sauf ce soir) ». */
    fun summary(board: Board): String {
        val running = board.tonight.count { it.status == "open" }
        val parts = mutableListOf<String>()
        if (running > 0) parts += "$running pour ce soir"
        parts += if (board.queue.isNotEmpty()) "${board.queue.size} en file" else "file vide"
        board.sab?.let { sab ->
            val speed = sab.kbpersec * 1024
            if (speed > 0) parts += "${Fr.bytes(speed)}/s"
            if (sab.paused) parts += if (running > 0) "SABnzbd en pause (sauf ce soir)" else "SABnzbd en pause"
        }
        return parts.joinToString(" · ")
    }

    /** « OK : Débloquer · Fiche · Annuler » (indice sous l'élément sélectionné). */
    fun hint(actions: List<Action>): String {
        if (actions.isEmpty()) return ""
        val short = mapOf(
            Action.UNSTICK to "Débloquer", Action.SEARCH to "Rechercher", Action.DETAIL to "Fiche",
            Action.CANCEL to "Annuler", Action.TOP to "En tête", Action.PAUSE to "Pause", Action.RESUME to "Reprendre",
        )
        return "OK : " + actions.joinToString(" · ") { short.getValue(it) }
    }
}
