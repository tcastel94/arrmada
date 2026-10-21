package fr.arrmada.app.ui.downloads

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Board
import fr.arrmada.app.data.BoardCard
import fr.arrmada.app.data.BoardLogic
import fr.arrmada.app.data.BoardLogic.Action
import fr.arrmada.app.data.BoardLogic.Family
import fr.arrmada.app.data.QueueItem
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.ChoiceDialog
import fr.arrmada.app.ui.components.FocusPanel
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.Pill
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.LocalDateTime

/** Rafraîchissement de l'écran, comme l'add-on (5 s). */
private const val REFRESH_MS = 5_000L

/** Couleurs de l'add-on : vert « prêt », rouge « bloqué ». */
private val ReadyGreen = Color(0xFF6EE7B7)
private val BlockedRed = Color(0xFFFCA5A5)

fun familyColor(family: Family): Color = when (family) {
    Family.ACTIVE -> ArrColors.Accent
    Family.PAUSED -> ArrColors.Warning
    Family.QUEUED -> Color(0x80C9D3E0)
    Family.IMPORT, Family.DONE -> ArrColors.Seen
    Family.ERROR -> ArrColors.Error
}

/**
 * Écran Téléchargements de l'add-on : en haut les demandes « Pour ce soir »
 * des TV (heure « Prêt vers 21:02 », étapes jusqu'à « Prêt à regarder »),
 * en dessous la file de Radarr / Sonarr. OK sur un élément : ses actions
 * (Débloquer, Passer en tête, Pause, Fiche, Annuler ma demande).
 */
@Composable
fun DownloadsScreen(
    repository: Repository,
    absolute: (String?) -> String?,
    onOpenMovie: (Int) -> Unit,
    onOpenSeries: (Int) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var board by remember { mutableStateOf<Board?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var refresh by remember { mutableIntStateOf(0) }
    // Débit estimé par élément : *arr ne le donne pas, on le déduit de la
    // baisse du « reste à télécharger » entre deux relevés (comme iftop)
    val samples = remember { mutableMapOf<String, Pair<Long, Double>>() }
    var speeds by remember { mutableStateOf<Map<String, Double>>(emptyMap()) }
    var menu by remember { mutableStateOf<Pair<String, List<Pair<String, () -> Unit>>>?>(null) }
    var unstick by remember { mutableStateOf<Pair<String, String>?>(null) } // (service, id SABnzbd)
    var confirmCancel by remember { mutableStateOf<BoardCard?>(null) }

    LaunchedEffect(refresh) {
        while (true) {
            runCatching { repository.board() }
                .onSuccess { b ->
                    val now = System.currentTimeMillis()
                    val next = mutableMapOf<String, Double>()
                    b.queue.forEach { item ->
                        val key = item.serviceType + ":" + item.id
                        samples[key]?.let { (then, left) ->
                            val elapsed = (now - then) / 1000.0
                            if (elapsed > 0 && left > item.sizeLeftBytes) next[key] = (left - item.sizeLeftBytes) / elapsed
                        }
                        samples[key] = now to item.sizeLeftBytes
                    }
                    speeds = next
                    board = b
                    error = null
                }
                .onFailure { if (board == null) error = it.message ?: "Serveur injoignable" }
            delay(REFRESH_MS)
        }
    }

    /** Lance une action, affiche la réponse du serveur, relit aussitôt. */
    fun act(call: suspend () -> fr.arrmada.app.data.ActionResult) {
        scope.launch {
            val message = runCatching { call() }.fold(
                onSuccess = { it.message ?: if (it.ok) "C’est fait" else "Échec" },
                onFailure = { it.message ?: "Échec" },
            )
            Toast.makeText(context, message, Toast.LENGTH_LONG).show()
            refresh++
        }
    }

    fun detail(service: String, arrId: Int?) {
        val id = arrId ?: return
        if (service == "sonarr") onOpenSeries(id) else onOpenMovie(id)
    }

    fun openCard(card: BoardCard) {
        val actions = BoardLogic.cardActions(card)
        val choices = actions.map { action ->
            choice(action.label) {
                when (action) {
                    Action.UNSTICK -> card.blockedDownload?.let { unstick = it.serviceType to it.downloadId }
                    Action.SEARCH -> act { repository.retryRequest(card.id) }
                    Action.DETAIL -> detail(card.serviceType, card.arrId)
                    Action.CANCEL -> { confirmCancel = card }
                    else -> Unit
                }
            }
        }
        if (actions == listOf(Action.DETAIL)) detail(card.serviceType, card.arrId) else if (choices.isNotEmpty()) menu = card.title to choices
    }

    fun openRow(item: QueueItem) {
        val row = BoardLogic.row(item)
        val id = item.downloadId.orEmpty()
        val choices = row.actions.map { action ->
            choice(action.label) {
                when (action) {
                    Action.UNSTICK -> { unstick = item.serviceType to id }
                    Action.TOP -> act { repository.queueAction(id, "top") }
                    Action.PAUSE -> act { repository.queueAction(id, "pause") }
                    Action.RESUME -> act { repository.queueAction(id, "resume") }
                    Action.DETAIL -> detail(item.serviceType, item.arrId)
                    else -> Unit
                }
            }
        }
        if (row.actions == listOf(Action.DETAIL)) {
            detail(item.serviceType, item.arrId)
        } else if (choices.isNotEmpty()) {
            menu = item.title to choices
        } else if (row.family == Family.ERROR) {
            Toast.makeText(context, item.error.ifBlank { item.detail }.ifBlank { row.label }, Toast.LENGTH_LONG).show()
        }
    }

    val b = board
    when {
        error != null && b == null -> return MessageScreen("Téléchargements indisponibles", error, "Réessayer") { error = null; refresh++ }
        b == null -> return MessageScreen("Chargement…")
    }
    val service = b!!.queue.firstOrNull()?.serviceType?.ifBlank { null } ?: "radarr"
    DownloadsContent(
        board = b,
        now = LocalDateTime.now(),
        speeds = speeds,
        absolute = absolute,
        onCard = ::openCard,
        onRow = ::openRow,
        onPauseAll = { act { repository.pauseAll(service) } },
        onResumeAll = { act { repository.resumeAll(service) } },
    )

    menu?.let { (title, choices) -> ChoiceDialog(title, choices, onDismiss = { menu = null }) }
    confirmCancel?.let { card ->
        ChoiceDialog(
            title = "Annuler ma demande",
            subtitle = "« ${card.title} » sort de la file. Les fichiers déjà dans la médiathèque restent.",
            choices = listOf(choice("Oui, annuler") { act { repository.cancelRequest(card.id) } }),
            onDismiss = { confirmCancel = null },
        )
    }
    unstick?.let { (svc, id) ->
        UnstickDialog(repository, svc, id, onDone = { message ->
            unstick = null
            message?.let { Toast.makeText(context, it, Toast.LENGTH_LONG).show() }
            refresh++
        })
    }
}

/** Une ligne du menu de OK : libellé + action. */
private fun choice(label: String, action: () -> Unit): Pair<String, () -> Unit> = label to action

/** Affichage (séparé du chargement pour les captures d'écran de test). */
@Composable
fun DownloadsContent(
    board: Board,
    now: LocalDateTime,
    speeds: Map<String, Double>,
    absolute: (String?) -> String?,
    onCard: (BoardCard) -> Unit,
    onRow: (QueueItem) -> Unit,
    onPauseAll: () -> Unit,
    onResumeAll: () -> Unit,
) {
    var backdrop by remember { mutableStateOf<String?>(null) }
    val firstFocus = remember { FocusRequester() }
    KenBurnsBackdrop(url = backdrop ?: absolute(board.tonight.firstOrNull()?.fanartUrl ?: board.queue.firstOrNull()?.fanartUrl)) {
        LazyColumn(contentPadding = PaddingValues(bottom = 36.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item {
                ScreenHeader("Téléchargements", BoardLogic.summary(board)) {
                    ArrButton("Pause sauf ce soir", onPauseAll)
                    ArrButton("Tout reprendre", onResumeAll)
                }
            }
            item {
                Text("Pour ce soir", style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(start = 48.dp, top = 14.dp))
            }
            item {
                if (board.tonight.isEmpty()) {
                    Column(Modifier.padding(start = 48.dp, top = 6.dp, end = 300.dp)) {
                        Text("Rien pour ce soir", style = MaterialTheme.typography.titleLarge)
                        Text(
                            "Lance un film ou un épisode depuis sa fiche, bouton Télécharger : il passera devant tous les autres téléchargements.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = ArrColors.TextSecondary,
                        )
                    }
                } else {
                    LazyRow(contentPadding = PaddingValues(horizontal = 48.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                        items(board.tonight, key = { "req:" + it.id }) { card ->
                            TonightCard(
                                card, BoardLogic.card(card, now), absolute,
                                onClick = { onCard(card) },
                                onFocus = { backdrop = absolute(card.fanartUrl) },
                                modifier = if (card == board.tonight.first()) Modifier.focusRequester(firstFocus) else Modifier,
                            )
                        }
                    }
                }
            }
            item {
                Text(
                    if (board.queue.isEmpty()) "File d’attente vide" else "File d’attente",
                    style = MaterialTheme.typography.titleMedium,
                    color = ArrColors.TextSecondary,
                    modifier = Modifier.padding(start = 48.dp, top = 10.dp),
                )
            }
            items(board.queue, key = { "q:" + it.serviceType + it.id }) { item ->
                QueueRow(
                    item, BoardLogic.row(item, speeds[item.serviceType + ":" + item.id] ?: 0.0), absolute,
                    onClick = { onRow(item) },
                    onFocus = { backdrop = absolute(item.fanartUrl) },
                    modifier = if (board.tonight.isEmpty() && item == board.queue.first()) Modifier.focusRequester(firstFocus) else Modifier,
                )
            }
        }
    }
    LaunchedEffect(board.tonight.isNotEmpty() || board.queue.isNotEmpty()) { runCatching { firstFocus.requestFocus() } }
}

/** Carte « Pour ce soir » : affiche, titre, TV d'origine, heure « Prêt vers », barre, étapes. */
@Composable
private fun TonightCard(
    card: BoardCard,
    view: BoardLogic.Card,
    absolute: (String?) -> String?,
    onClick: () -> Unit,
    onFocus: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var focused by remember { mutableStateOf(false) }
    val ring = when (view.tone) {
        BoardLogic.Tone.READY -> ArrColors.Seen
        BoardLogic.Tone.BLOCKED -> ArrColors.Error
        BoardLogic.Tone.NORMAL -> ArrColors.Accent
    }
    FocusPanel(
        onClick = onClick,
        onFocus = { focused = it; if (it) onFocus() },
        ring = ring,
        modifier = modifier.width(440.dp).height(160.dp),
    ) {
        Row(Modifier.fillMaxSize().padding(10.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ArtImage(absolute(card.posterUrl), card.title, Modifier.width(92.dp).fillMaxHeight().clip(RoundedCornerShape(6.dp)))
            Column(Modifier.weight(1f)) {
                Text(card.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(view.who, style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    view.headline,
                    style = MaterialTheme.typography.titleLarge,
                    color = when (view.tone) {
                        BoardLogic.Tone.READY -> ReadyGreen
                        BoardLogic.Tone.BLOCKED -> BlockedRed
                        BoardLogic.Tone.NORMAL -> ArrColors.Text
                    },
                    maxLines = 1,
                    modifier = Modifier.padding(top = 4.dp),
                )
                ProgressBar(view.progress, Modifier.fillMaxWidth().padding(top = 5.dp), height = 5.dp)
                Text(
                    if (focused && view.actions.isNotEmpty()) BoardLogic.hint(view.actions) else view.detail,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (focused) ArrColors.AccentText else ArrColors.TextSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 4.dp),
                )
                Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    BoardLogic.STEPS.zip(view.steps).forEach { (label, state) -> StepPill(label, state) }
                }
            }
        }
    }
}

@Composable
private fun StepPill(label: String, state: BoardLogic.Step) {
    val color = when (state) {
        BoardLogic.Step.DONE -> Color(0x3334D399)
        BoardLogic.Step.NOW -> Color(0x554A9EFF)
        BoardLogic.Step.ERROR -> Color(0x40F87171)
        BoardLogic.Step.TODO -> Color(0x14FFFFFF)
    }
    val text = if (state == BoardLogic.Step.TODO) ArrColors.TextSecondary.copy(alpha = 0.6f) else ArrColors.Text
    Pill(label, color, textColor = text)
}

/** Ligne de la file : bande de couleur, affiche, titre, détails, barre, %, reste et débit, état. */
@Composable
private fun QueueRow(
    item: QueueItem,
    row: BoardLogic.Row,
    absolute: (String?) -> String?,
    onClick: () -> Unit,
    onFocus: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var focused by remember { mutableStateOf(false) }
    val color = familyColor(row.family)
    FocusPanel(
        onClick = onClick,
        onFocus = { focused = it; if (it) onFocus() },
        scale = 1.015f,
        modifier = modifier.padding(horizontal = 48.dp).fillMaxWidth().height(58.dp),
    ) {
        Row(Modifier.fillMaxSize(), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(5.dp).fillMaxHeight().background(color))
            ArtImage(absolute(item.posterUrl), item.title, Modifier.padding(start = 8.dp).size(30.dp, 44.dp).clip(RoundedCornerShape(4.dp)))
            Column(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                Text(item.title, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    row.meta,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (row.family == Family.ERROR) ArrColors.Error else ArrColors.TextSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                ProgressBar(row.progress, Modifier.fillMaxWidth().padding(top = 4.dp), height = 3.dp)
            }
            Text(row.percent, style = MaterialTheme.typography.titleLarge, modifier = Modifier.width(64.dp))
            Column(Modifier.width(170.dp)) {
                Text(row.eta, style = MaterialTheme.typography.labelMedium, maxLines = 1)
                Text(
                    if (focused && row.actions.isNotEmpty()) BoardLogic.hint(row.actions) else row.sizes,
                    style = MaterialTheme.typography.labelSmall,
                    color = if (focused) ArrColors.AccentText else ArrColors.TextSecondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Pill(row.label, color.copy(alpha = 0.25f), Modifier.padding(end = 14.dp).width(110.dp))
        }
    }
}
