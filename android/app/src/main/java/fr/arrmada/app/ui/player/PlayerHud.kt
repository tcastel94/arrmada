package fr.arrmada.app.ui.player

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.PlaybackLogic
import fr.arrmada.app.data.QualityLogic
import fr.arrmada.app.data.Segment
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.theme.ArrColors

/**
 * Ce qui s'affiche par-dessus l'image pendant la lecture (hors menu pause) :
 * barre d'avance rapide avec vignette, bouton « Passer l'intro », carte
 * « Épisode suivant » et carte de qualité « Passer en 1080p ? ».
 *
 * Simple affichage : PlayerSurface décide quand chaque élément apparaît et
 * lui passe l'état du moment ; les cartes elles-mêmes sont dans
 * PlayerOverlays.kt.
 */
@Composable
internal fun BoxScope.PlayerHud(
    info: PlayInfo,
    showMenu: Boolean,
    osdUntil: Long, // barre visible jusqu'à cet instant (après ← / →)
    scrubTarget: Long?, // instant visé pendant le défilement avec vignettes
    position: Long,
    duration: Long,
    activeSkip: Segment?,
    showUpNext: Boolean,
    upNext: UpNext?,
    countdown: Int,
    qualityCard: QualityCardKind?,
    absolute: (String?) -> String?,
    onAcceptQuality: () -> Unit,
    onDeclineQuality: () -> Unit,
) {
    // Barre discrète après une avance / un retour rapide
    AnimatedVisibility(
        visible = !showMenu && System.currentTimeMillis() < osdUntil,
        enter = fadeIn(),
        exit = fadeOut(),
        modifier = Modifier.align(Alignment.BottomCenter),
    ) {
        Column(
            Modifier
                .fillMaxWidth()
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color(0xCC000000))))
                .padding(horizontal = gutter, vertical = 24.dp)
        ) {
            val shown = scrubTarget ?: position // pendant le défilement : l'instant visé
            val fraction = if (duration > 0) (shown.toFloat() / duration).coerceIn(0f, 1f) else 0f
            val trickplay = info.trickplay
            if (scrubTarget != null && trickplay != null) {
                // Vignette au-dessus de l'instant visé, sans sortir de l'écran
                BoxWithConstraints(Modifier.fillMaxWidth().padding(bottom = 10.dp)) {
                    val thumb = 240.dp
                    val x = (maxWidth * fraction - thumb / 2).coerceIn(0.dp, (maxWidth - thumb).coerceAtLeast(0.dp))
                    Column(Modifier.offset(x = x)) {
                        TrickplayThumb(trickplay, shown / 1000.0, absolute, width = thumb)
                        Text(
                            formatClock(shown / 1000),
                            style = MaterialTheme.typography.titleMedium,
                            modifier = Modifier.padding(top = 4.dp).align(Alignment.CenterHorizontally),
                        )
                    }
                }
            }
            ProgressBar(fraction, Modifier.fillMaxWidth(), height = 4.dp)
            Row(Modifier.fillMaxWidth().padding(top = 6.dp)) {
                Text(formatClock(shown / 1000), style = MaterialTheme.typography.labelLarge)
                Text(" / " + formatClock(duration / 1000), style = MaterialTheme.typography.labelLarge, color = ArrColors.TextSecondary)
            }
        }
    }

    // « Passer l'intro » (en bas à droite, comme dans l'add-on)
    AnimatedVisibility(
        visible = activeSkip != null && !showMenu && !showUpNext,
        enter = fadeIn() + slideInHorizontally { it / 2 },
        exit = fadeOut(),
        modifier = Modifier.align(Alignment.BottomEnd).padding(end = gutter, bottom = 48.dp),
    ) {
        SkipButton(activeSkip?.let { PlaybackLogic.skipLabel(it) } ?: "")
    }

    // Carte « Épisode suivant »
    AnimatedVisibility(
        visible = showUpNext,
        enter = fadeIn() + slideInHorizontally { it },
        exit = fadeOut() + slideOutHorizontally { it },
        modifier = Modifier.align(Alignment.BottomEnd).padding(end = gutter, bottom = 48.dp),
    ) {
        upNext?.let { UpNextCard(it, countdown, absolute) }
    }

    // Carte « Le réseau ne suit pas ce fichier… Passer en 1080p ? » (ADR-012)
    AnimatedVisibility(
        visible = qualityCard != null && !showMenu && !showUpNext,
        enter = fadeIn() + slideInHorizontally { it },
        exit = fadeOut() + slideOutHorizontally { it },
        modifier = Modifier.align(Alignment.BottomEnd).padding(end = gutter, bottom = 48.dp),
    ) {
        when (qualityCard) {
            QualityCardKind.SUGGEST -> QualityCard(
                QualityLogic.suggestMessage(info.bitrate),
                accept = "Passer en 1080p",
                decline = "Non merci",
                onAccept = onAcceptQuality,
                onDecline = onDeclineQuality,
            )
            QualityCardKind.ALWAYS -> QualityCard(
                "Toujours lire en 1080p sur cette TV ?",
                accept = "Oui, toujours",
                decline = "Non",
                onAccept = onAcceptQuality,
                onDecline = onDeclineQuality,
            )
            null -> Unit
        }
    }
}
