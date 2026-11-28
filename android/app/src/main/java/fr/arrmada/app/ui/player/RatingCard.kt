package fr.arrmada.app.ui.player

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.nativeKeyCode
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.PlayerKeyLogic
import fr.arrmada.app.data.TraktLogic
import fr.arrmada.app.data.TraktStep
import fr.arrmada.app.ui.components.Dim
import fr.arrmada.app.ui.components.GlassCard
import fr.arrmada.app.ui.components.KeyHint

// Note de fin de lecture pour Trakt (ADR-022) : 5 étoiles, demi-étoiles
// (les 10 niveaux de Trakt). ← / → par demi-étoile, OK valide, Retour passe.
// Au doigt : un appui sur la moitié gauche / droite d'une étoile.

/** Notes en cours à la sortie d'un titre : [steps] dans l'ordre, puis [after] (épisode suivant, retour…). */
data class RatingSession(val steps: List<TraktStep>, val index: Int, val after: () -> Unit)

private val StarGold = Color(0xFFFFC93C)
private val StarEmpty = Color(0x40FFFFFF)

/**
 * Carte de note posée sur l'image figée. [step] : ce qu'on note (« Ce film »,
 * « Épisode S01E04 », « Saison 1 de … », « La série … ») ; [position] / [count] :
 * étape en cours (épisode, puis saison, puis série). [onRate] reçoit 1 à 10.
 */
@Composable
fun RatingCard(
    step: TraktStep,
    position: Int,
    count: Int,
    onRate: (Int) -> Unit,
    onSkip: () -> Unit,
) {
    // Une carte neuve à chaque étape : la note déjà donnée (revisionnage), sinon rien
    var rating by remember(step) { mutableIntStateOf(TraktLogic.initial(step)) }
    val focus = remember { FocusRequester() }
    LaunchedEffect(step) { runCatching { focus.requestFocus() } }

    Box(
        Modifier
            .fillMaxSize()
            .background(Color(0x99000000))
            .focusRequester(focus)
            .focusable()
            .onPreviewKeyEvent { event ->
                if (event.type != KeyEventType.KeyDown) return@onPreviewKeyEvent false
                val code = event.key.nativeKeyCode
                when {
                    code == android.view.KeyEvent.KEYCODE_DPAD_LEFT -> { rating = TraktLogic.step(rating, forward = false); true }
                    code == android.view.KeyEvent.KEYCODE_DPAD_RIGHT -> { rating = TraktLogic.step(rating, forward = true); true }
                    PlayerKeyLogic.isConfirm(code) -> { if (rating > 0) onRate(rating) else onSkip(); true }
                    // Chiffres de la télécommande : 1 à 5 étoiles pleines d'un coup
                    code in android.view.KeyEvent.KEYCODE_1..android.view.KeyEvent.KEYCODE_5 -> {
                        rating = (code - android.view.KeyEvent.KEYCODE_0) * 2
                        true
                    }
                    else -> false // Retour : BackHandler du lecteur (passer)
                }
            },
        contentAlignment = Alignment.Center,
    ) {
        GlassCard(Modifier.widthIn(min = 420.dp, max = 560.dp)) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    if (count > 1) "Ta note sur Trakt · ${position + 1}/$count" else "Ta note sur Trakt",
                    style = MaterialTheme.typography.labelLarge,
                    color = Dim,
                )
                Text(
                    step.label,
                    style = MaterialTheme.typography.titleLarge,
                    color = Color.White,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (index in 0 until 5) {
                        StarCell(TraktLogic.star(index, rating), onHalf = { rating = index * 2 + 1 }, onFull = { rating = index * 2 + 2 })
                    }
                }
                step.current?.takeIf { it in 1..TraktLogic.MAX }?.let { previous ->
                    Text(
                        "Ta note actuelle : ${TraktLogic.stars(previous)} ★",
                        style = MaterialTheme.typography.labelLarge,
                        color = Dim,
                    )
                }
                Text(
                    if (rating == 0) "Choisis avec ← →" else "${TraktLogic.stars(rating)} ★ · ${TraktLogic.label(rating)}",
                    style = MaterialTheme.typography.titleMedium,
                    color = if (rating == 0) Dim else Color.White,
                )
                Row(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    KeyHint("← →", "Demi-étoile")
                    KeyHint("OK", if (rating > 0) "Noter" else "Passer", primary = true)
                    KeyHint("Retour", "Passer")
                }
            }
        }
    }
}

/** Une étoile : pleine, moitié (moitié gauche dorée) ou vide ; au doigt, chaque moitié se touche. */
@Composable
private fun StarCell(state: TraktLogic.Star, onHalf: () -> Unit, onFull: () -> Unit) {
    Box(Modifier.size(52.dp), contentAlignment = Alignment.Center) {
        Text("★", fontSize = 46.sp, color = if (state == TraktLogic.Star.FULL) StarGold else StarEmpty)
        if (state == TraktLogic.Star.HALF) {
            Text(
                "★",
                fontSize = 46.sp,
                color = StarGold,
                modifier = Modifier.drawWithContent {
                    clipRect(right = size.width / 2) { this@drawWithContent.drawContent() }
                },
            )
        }
        // Zones tactiles sans focus (sinon la télécommande pourrait s'y arrêter)
        Row(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f).fillMaxSize().pointerInput(Unit) { detectTapGestures { onHalf() } })
            Box(Modifier.weight(1f).fillMaxSize().pointerInput(Unit) { detectTapGestures { onFull() } })
        }
    }
}
