package fr.arrmada.app.ui.player

import fr.arrmada.app.ui.components.LocalScreen
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.PlaybackLogic
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.CardShape
import fr.arrmada.app.ui.components.Dim
import fr.arrmada.app.ui.components.GlassCard
import fr.arrmada.app.ui.components.Ink
import fr.arrmada.app.ui.components.KeyHint
import fr.arrmada.app.ui.components.PillShape
import fr.arrmada.app.ui.components.ProgressBar

// Cartes et boutons posés sur la vidéo pendant la lecture (style « verre ») :
// « Passer l'intro », « Épisode suivant », « Passer en 1080p ? ».

/**
 * Bouton « Passer l'intro » : pastille blanche à texte sombre, comme un
 * bouton qui a le focus dans le reste du lecteur (OK le déclenche), avec
 * le rappel de la touche à droite.
 */
@Composable
fun SkipButton(label: String) {
    Row(
        Modifier
            .background(Color.White, PillShape)
            .padding(start = 22.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(label, style = MaterialTheme.typography.titleMedium, color = Ink)
        Text(
            "OK",
            style = MaterialTheme.typography.labelSmall,
            color = Color.White,
            modifier = Modifier.background(Ink, PillShape).padding(horizontal = 9.dp, vertical = 3.dp),
        )
    }
}

/** Carte de qualité : proposition du 1080p, puis « Toujours lire en 1080p ? ». */
internal enum class QualityCardKind { SUGGEST, ALWAYS }

/** La carte de qualité s'efface seule au bout de 20 s. */
internal const val QUALITY_CARD_MS = 20_000L

/**
 * Carte non bloquante façon « Épisode suivant » : à la télécommande, OK
 * accepte et Retour refuse (le focus reste sur le lecteur) ; au doigt, les
 * deux boutons.
 */
@Composable
internal fun QualityCard(message: String, accept: String, decline: String, onAccept: () -> Unit, onDecline: () -> Unit) {
    val touch = LocalScreen.current.isTouch
    GlassCard(Modifier.widthIn(max = 440.dp)) {
        Column {
            Text("Qualité de lecture", style = MaterialTheme.typography.labelLarge, color = Dim)
            Text(message, style = MaterialTheme.typography.titleMedium, color = Color.White, modifier = Modifier.padding(top = 4.dp))
            Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                if (touch) {
                    // Au doigt : de vrais boutons (pastilles de verre)
                    ArrButton(accept, onAccept, primary = true)
                    ArrButton(decline, onDecline)
                } else {
                    // À la télécommande : rien à viser, OK et Retour suffisent
                    KeyHint("OK", accept, primary = true)
                    KeyHint("Retour", decline)
                }
            }
        }
    }
}

/**
 * Carte « Épisode suivant dans N s » (OK : maintenant ; Retour : non
 * merci) : carte de verre sur la vidéo, vignette, compte à rebours en
 * barre fine (bleue : c'est « en cours »), rappels de touches.
 */
@Composable
fun UpNextCard(next: UpNext, countdown: Int, absolute: (String?) -> String?) {
    GlassCard(Modifier.widthIn(max = 460.dp)) {
        Row(horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
            ArtImage(absolute(next.image), next.title, Modifier.width(156.dp).height(88.dp).clip(CardShape))
            Column(Modifier.weight(1f)) {
                // Film d'une saga : « Film suivant » (ADR-016), sinon « Épisode suivant »
                val what = if (next.request.kind == "movie") "Film suivant" else "Épisode suivant"
                Text("$what · dans $countdown s", style = MaterialTheme.typography.labelLarge, color = Dim)
                Text(
                    "${next.code} · ${next.title}",
                    style = MaterialTheme.typography.titleMedium,
                    color = Color.White,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 2.dp),
                )
                ProgressBar(
                    1f - countdown.toFloat() / PlaybackLogic.UP_NEXT_SECONDS,
                    Modifier.fillMaxWidth().padding(top = 8.dp),
                )
                Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    KeyHint("OK", "Maintenant", primary = true)
                    KeyHint("Retour", "Non merci")
                }
            }
        }
    }
}
