package fr.arrmada.app.notify

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideInVertically
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.EventLogic
import fr.arrmada.app.data.PlayAnnounce
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay
import java.time.LocalDateTime

/**
 * Tout ce qui s'affiche par-dessus les écrans : bulles, « Prêt à regarder »,
 * alerte caméra. Posé une fois au-dessus de la navigation (MainActivity).
 * Les bulles ne prennent jamais le focus : la télécommande continue de
 * piloter l'écran en dessous.
 */
@Composable
fun BoxScope.EventOverlays(center: EventCenter, absolute: (String?) -> String?, onWatch: (PlayAnnounce) -> Unit) {
    val toasts by center.toasts.collectAsState()
    val ready by center.ready.collectAsState()
    val camera by center.camera.collectAsState()

    // ── Bulle (une à la fois, la suivante après la précédente) ──
    val current = toasts.firstOrNull()
    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(current) {
        if (current == null) return@LaunchedEffect
        visible = true
        delay(current.millis)
        visible = false
        delay(260) // fin du fondu de sortie
        center.dismissToast(current)
    }
    AnimatedVisibility(
        visible = visible && current != null,
        enter = fadeIn(tween(320)) + slideInVertically(tween(320)) { it / 3 },
        exit = fadeOut(tween(240)),
        modifier = Modifier.align(Alignment.BottomEnd).padding(end = 20.dp, bottom = 20.dp),
    ) {
        current?.let { BubbleCard(it, absolute) }
    }

    // ── Caméra pendant un film : en haut à gauche, 5 s ──
    LaunchedEffect(camera) {
        if (camera != null) {
            delay(5_000)
            center.dismissCamera()
        }
    }
    AnimatedVisibility(
        visible = camera != null,
        enter = fadeIn(tween(400)) + slideInHorizontally(tween(400)) { -it },
        exit = fadeOut(tween(240)),
        modifier = Modifier.align(Alignment.TopStart).padding(24.dp),
    ) {
        camera?.let { CameraCard(it) }
    }

    // ── « Prêt à regarder » ──
    ready?.let { r -> ReadyDialog(r, absolute, onWatch = { center.dismissReady(); onWatch(r) }, onLater = center::dismissReady) }
}

/** Bulle de l'add-on : carte sombre, anneau bleu (rouge si erreur), affiche ou photo, titre, message. */
@Composable
fun BubbleCard(toast: Toast, absolute: (String?) -> String?) {
    val bubble = toast.bubble
    val ring = if (bubble.error) Color(0x99F87171) else Color(0x804A9EFF)
    Row(
        Modifier
            .width(322.dp)
            .shadow(16.dp, RoundedCornerShape(12.dp), ambientColor = ArrColors.Accent, spotColor = ArrColors.Accent)
            .background(Color(0xF7121826), RoundedCornerShape(12.dp))
            .border(1.dp, ring, RoundedCornerShape(12.dp))
            .padding(9.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        when {
            toast.photo != null -> Image(toast.photo, null, Modifier.size(64.dp, 44.dp).clip(RoundedCornerShape(6.dp)), contentScale = ContentScale.Crop)
            bubble.icon != null -> ArtImage(absolute(bubble.icon) ?: bubble.icon, bubble.heading, Modifier.size(32.dp, 48.dp).clip(RoundedCornerShape(5.dp)))
        }
        Column(Modifier.weight(1f)) {
            Text(
                bubble.heading,
                style = MaterialTheme.typography.titleMedium,
                color = if (bubble.error) Color(0xFFFCA5A5) else ArrColors.AccentText,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(bubble.message, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

/** Alerte caméra : point rouge, « Personne détectée », « Entrée · 21:42 », photo. */
@Composable
fun CameraCard(alert: CameraAlert) {
    Column(
        Modifier
            .width(240.dp)
            .background(Color(0xF20A0E16), RoundedCornerShape(12.dp))
            .border(1.dp, Color(0x33FFFFFF), RoundedCornerShape(12.dp))
            .padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.size(9.dp).clip(CircleShape).background(Color(0xFFEF4444)))
            Column {
                Text(EventLogic.cameraLabel(alert.event), style = MaterialTheme.typography.titleMedium, maxLines = 1)
                Text(EventLogic.cameraSubtitle(alert.event, LocalDateTime.now()), style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary)
            }
        }
        Box(Modifier.fillMaxWidth().height(124.dp).clip(RoundedCornerShape(8.dp)).background(ArrColors.Card), contentAlignment = Alignment.Center) {
            if (alert.photo != null) {
                Image(alert.photo, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
            } else {
                Text("Pas de photo pour cette détection", style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary)
            }
        }
    }
}

/**
 * « Prêt à regarder » : le titre demandé depuis cette TV est sur le NAS
 * (sous-titres compris). Regarder le lance ; sans réponse, la pop-up se
 * ferme seule au bout d'une minute.
 */
@Composable
fun ReadyDialog(ready: PlayAnnounce, absolute: (String?) -> String?, onWatch: () -> Unit, onLater: () -> Unit) {
    val focus = remember { FocusRequester() }
    val canPlay = ready.externalId != null
    LaunchedEffect(ready) {
        runCatching { focus.requestFocus() }
        delay(60_000)
        onLater()
    }
    Dialog(onDismissRequest = onLater, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Box(Modifier.fillMaxSize().padding(end = 24.dp, bottom = 24.dp), contentAlignment = Alignment.BottomEnd) {
            ReadyCard(ready, absolute, canPlay, onWatch, onLater, focus)
        }
    }
}

@Composable
fun ReadyCard(
    ready: PlayAnnounce,
    absolute: (String?) -> String?,
    canPlay: Boolean,
    onWatch: () -> Unit,
    onLater: () -> Unit,
    focus: FocusRequester = remember { FocusRequester() },
) {
    Row(
        Modifier
            .width(434.dp)
            .shadow(22.dp, RoundedCornerShape(16.dp), ambientColor = ArrColors.Seen, spotColor = ArrColors.Seen)
            .background(Color(0xF7121826), RoundedCornerShape(16.dp))
            .border(2.dp, ArrColors.Seen.copy(alpha = 0.7f), RoundedCornerShape(16.dp))
            .padding(14.dp),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        ArtImage(absolute(ready.poster) ?: ready.poster, ready.title, Modifier.size(100.dp, 150.dp).clip(RoundedCornerShape(8.dp)))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Prêt à regarder", style = MaterialTheme.typography.titleMedium, color = Color(0xFF6EE7B7))
            Text(EventLogic.readyTitle(ready), style = MaterialTheme.typography.headlineMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Text(EventLogic.readyDetail(ready), style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary, maxLines = 2)
            Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                if (canPlay) ArrButton("Regarder", onWatch, primary = true, leading = "▶", modifier = Modifier.focusRequester(focus))
                ArrButton("Plus tard", onLater, modifier = if (canPlay) Modifier else Modifier.focusRequester(focus))
            }
        }
    }
}
