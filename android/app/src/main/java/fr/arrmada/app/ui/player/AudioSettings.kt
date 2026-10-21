package fr.arrmada.app.ui.player

import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.tapToClick
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.media3.common.C
import androidx.media3.common.Tracks
import androidx.tv.material3.Border
import androidx.tv.material3.ClickableSurfaceDefaults
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Surface
import androidx.tv.material3.Text
import fr.arrmada.app.data.AmpDevice
import fr.arrmada.app.data.AmpLogic
import fr.arrmada.app.data.SoundAdvisor
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.serialization.json.JsonPrimitive

/**
 * Ce que l'écran Réglages audio sait de la pièce et du son en cours.
 * [room] : « Salle de cinéma · enceintes 7.2.2 », ou « Pas d'ampli dans cette pièce ».
 */
data class AudioContext(
    val room: String,
    val hasAmp: Boolean,
    val advice: SoundAdvisor.Advice,
    val auto: Boolean,
)

/**
 * Réglages audio (bouton « Audio » du menu pause) : le son conseillé pour
 * ce film dans cette pièce (et le décodage auto), la piste audio, puis
 * l'ampli : programme, volume, voix, mode nuit, basses. Sans ampli : le
 * conseil (son de la TV) et la piste seulement.
 */
@Composable
fun AudioSettings(
    audio: AudioContext,
    tracks: Tracks,
    amp: AmpDevice?,
    onSelectTrack: (TrackChoice?) -> Unit,
    onAmp: (action: String, value: JsonPrimitive) -> Unit,
    onAuto: (Boolean) -> Unit,
    onApplyAdvice: () -> Unit,
    onClose: () -> Unit,
) {
    val focus = remember { FocusRequester() }
    val advice = audio.advice
    Column(
        Modifier
            .fillMaxSize()
            .background(Color(0xF00A0E16))
            .verticalScroll(rememberScrollState())
            .padding(horizontal = gutter, vertical = 28.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Réglages audio", style = MaterialTheme.typography.headlineMedium)
                Text(audio.room, style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary)
            }
            // Sans réglage d'ampli à proposer, le focus part de ce bouton
            ArrButton("Retour au menu", onClose, modifier = if (audio.hasAmp && advice.program != null) Modifier else Modifier.focusRequester(focus))
        }

        // ── Son conseillé ──
        Column(
            Modifier.fillMaxWidth().background(ArrColors.CardDeep, RoundedCornerShape(14.dp)).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text("Son conseillé", style = MaterialTheme.typography.labelMedium, color = ArrColors.AccentText)
            Text(advice.headline, style = MaterialTheme.typography.titleLarge)
            if (advice.detail.isNotBlank()) {
                Text(advice.detail, style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary, modifier = Modifier.widthIn(max = 760.dp))
            }
            if (audio.hasAmp && advice.program != null) {
                Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(28.dp), verticalAlignment = Alignment.Bottom) {
                    AmpGroup("Décodage auto") {
                        AmpChip("Activé", selected = audio.auto, modifier = Modifier.focusRequester(focus)) { onAuto(true) }
                        AmpChip("Désactivé", selected = !audio.auto) { onAuto(false) }
                    }
                    when {
                        amp?.soundProgram == advice.program -> Text(
                            "Appliqué : ${AmpLogic.programName(advice.program)}",
                            style = MaterialTheme.typography.labelLarge,
                            color = ArrColors.Seen,
                            modifier = Modifier.padding(bottom = 8.dp),
                        )
                        audio.auto -> Text(
                            "S’applique tout seul au lancement et à chaque changement de piste",
                            style = MaterialTheme.typography.labelMedium,
                            color = ArrColors.TextSecondary,
                            modifier = Modifier.padding(bottom = 8.dp),
                        )
                        else -> AmpChip("Appliquer : ${AmpLogic.programName(advice.program)}", selected = false, onClick = onApplyAdvice)
                    }
                }
            }
        }

        // ── Piste audio du film ──
        Column {
            Text("Piste audio", style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(bottom = 6.dp))
            TracksPanel(trackChoices(tracks, C.TRACK_TYPE_AUDIO), allowOff = false, sidePadding = 0.dp, onSelect = onSelectTrack)
        }

        // ── Ampli ──
        if (amp != null && amp.online) {
            Text("Ampli · ${AmpLogic.summary(amp)}", style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary)
            Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
                AmpGroup("Programme sonore") {
                    AmpLogic.PROGRAMS.forEach { (id, label) ->
                        AmpChip(label, selected = amp.soundProgram == id) { onAmp("sound_program", JsonPrimitive(id)) }
                    }
                }
                AmpGroup("Volume") {
                    AmpChip("Vol −", selected = false) { onAmp("volume_step", JsonPrimitive(-AmpLogic.VOLUME_STEP)) }
                    AmpChip("Vol +", selected = false) { onAmp("volume_step", JsonPrimitive(AmpLogic.VOLUME_STEP)) }
                    AmpChip(if (amp.mute) "Remettre le son" else "Muet", selected = amp.mute) { onAmp("mute", JsonPrimitive(!amp.mute)) }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
                amp.dialogLevel?.let { level ->
                    AmpGroup("Voix plus claires") {
                        AmpLogic.DIALOG_LEVELS.forEach { (value, label) ->
                            AmpChip(label, selected = level == value) { onAmp("dialog_level", JsonPrimitive(value)) }
                        }
                    }
                }
                amp.adaptiveDrc?.let { night ->
                    AmpGroup("Mode nuit") {
                        AmpChip("Activé", selected = night) { onAmp("adaptive_drc", JsonPrimitive(true)) }
                        AmpChip("Désactivé", selected = !night) { onAmp("adaptive_drc", JsonPrimitive(false)) }
                    }
                }
            }
            if (amp.extraBass != null || amp.subwooferVolume != null) {
                Row(horizontalArrangement = Arrangement.spacedBy(28.dp)) {
                    amp.extraBass?.let { bass ->
                        AmpGroup("Extra Bass") {
                            AmpChip("Activé", selected = bass) { onAmp("extra_bass", JsonPrimitive(true)) }
                            AmpChip("Désactivé", selected = !bass) { onAmp("extra_bass", JsonPrimitive(false)) }
                        }
                    }
                    amp.subwooferVolume?.let { level ->
                        AmpGroup("Caisson de basses · ${AmpLogic.subwooferLabel(level)}") {
                            AmpChip("Basses −", selected = false) { onAmp("subwoofer_volume", JsonPrimitive(level - 1)) }
                            AmpChip("Basses +", selected = false) { onAmp("subwoofer_volume", JsonPrimitive(level + 1)) }
                            AmpChip("Neutre", selected = level == 0) { onAmp("subwoofer_volume", JsonPrimitive(0)) }
                        }
                    }
                }
            }
        } else if (audio.hasAmp) {
            Text("L’ampli ne répond pas : vérifie qu’il est allumé et sur le réseau.", style = MaterialTheme.typography.bodyMedium, color = ArrColors.Warning)
        }

        Text("Retour : revenir au menu pause", style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary)
    }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
}

@Composable
internal fun AmpGroup(label: String, chips: @Composable () -> Unit) {
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = ArrColors.TextSecondary, maxLines = 1)
        Row(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) { chips() }
    }
}

/** Pastille de réglage : bleue au focus, entourée quand c'est le réglage actuel. */
@Composable
internal fun AmpChip(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val shape = RoundedCornerShape(8.dp)
    Surface(
        onClick = onClick,
        modifier = modifier.height(34.dp).tapToClick(onClick),
        shape = ClickableSurfaceDefaults.shape(shape),
        scale = ClickableSurfaceDefaults.scale(focusedScale = 1.06f),
        border = ClickableSurfaceDefaults.border(
            border = if (selected) Border(BorderStroke(2.dp, ArrColors.Accent), shape = shape) else Border.None,
        ),
        colors = ClickableSurfaceDefaults.colors(
            containerColor = if (selected) ArrColors.Accent.copy(alpha = 0.22f) else Color(0x26FFFFFF),
            contentColor = ArrColors.Text,
            focusedContainerColor = ArrColors.Accent,
            focusedContentColor = ArrColors.Night,
        ),
    ) {
        Box(Modifier.fillMaxHeight().padding(horizontal = 14.dp), contentAlignment = Alignment.Center) {
            Text(label, style = MaterialTheme.typography.labelLarge, maxLines = 1)
        }
    }
}
