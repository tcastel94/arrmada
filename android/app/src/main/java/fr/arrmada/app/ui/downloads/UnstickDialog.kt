package fr.arrmada.app.ui.downloads

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Diagnose
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch

/**
 * « Débloquer » (comme l'add-on) : le serveur diagnostique le téléchargement
 * (3 étapes au plus : téléchargé ? importable ? que faire ?) et propose une
 * réparation (« Importer », « Chercher une autre version »…). [onDone]
 * reçoit le message à afficher (null si l'on ferme sans rien faire).
 */
@Composable
fun UnstickDialog(repository: Repository, service: String, downloadId: String, onDone: (String?) -> Unit) {
    val scope = rememberCoroutineScope()
    var diag by remember { mutableStateOf<Diagnose?>(null) }
    var working by remember { mutableStateOf(false) }
    val focus = remember { FocusRequester() }

    LaunchedEffect(downloadId) {
        diag = runCatching { repository.diagnose(service, downloadId) }
            .getOrElse { Diagnose(status = "error", message = it.message ?: "Serveur injoignable") }
    }

    Dialog(onDismissRequest = { if (!working) onDone(null) }) {
        Column(
            Modifier.width(520.dp).background(ArrColors.CardDeep, RoundedCornerShape(16.dp)).padding(24.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("Débloquer", style = MaterialTheme.typography.titleLarge)
            val d = diag
            when {
                d == null -> Text("Diagnostic en cours…", color = ArrColors.TextSecondary)
                d.status != "ok" -> StepLine("err", "Diagnostic impossible", d.message ?: "Serveur injoignable")
                else -> {
                    if (d.title.isNotBlank()) Text(d.title, style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary)
                    d.steps.take(3).forEach { StepLine(it.state, it.text, it.detail.take(90)) }
                }
            }
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                val canFix = d != null && d.status == "ok" && d.canFix && d.action.isNotBlank()
                if (canFix) {
                    ArrButton(
                        if (working) "En cours…" else d!!.action,
                        {
                            if (!working) {
                                working = true
                                scope.launch {
                                    val message = runCatching { repository.unstick(service, downloadId) }
                                        .fold({ it.message ?: "C’est fait" }, { it.message ?: "Échec" })
                                    onDone(message)
                                }
                            }
                        },
                        primary = true,
                        modifier = Modifier.focusRequester(focus),
                    )
                }
                ArrButton(if (canFix) "Annuler" else "Fermer", { if (!working) onDone(null) }, modifier = if (canFix) Modifier else Modifier.focusRequester(focus))
            }
        }
    }
    LaunchedEffect(diag) { runCatching { focus.requestFocus() } }
}

/** Ligne du diagnostic : pastille verte (ok), rouge (problème) ou bleue (étape suivante). */
@Composable
private fun StepLine(state: String, text: String, detail: String) {
    val color = when (state) {
        "ok" -> ArrColors.Seen
        "err" -> ArrColors.Error
        else -> ArrColors.Accent
    }
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.Top) {
        Box(Modifier.padding(top = 5.dp).size(10.dp).clip(CircleShape).background(color))
        Column {
            Text(text, style = MaterialTheme.typography.titleMedium)
            if (detail.isNotBlank()) Text(detail, style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary)
        }
    }
}
