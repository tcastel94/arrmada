package fr.arrmada.app.ui.player

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
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
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.AmpDevice
import fr.arrmada.app.data.AmpLogic
import fr.arrmada.app.data.SoundAdvisor
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.gutter
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
 * Réglages audio (bouton « Audio » du menu pause), au style du menu pause
 * (GlassStyle.kt) : voile sur l'image figée, sections en cartes de verre,
 * pastilles blanches au focus et réglage actuel coché ✓.
 *
 * De haut en bas : le son conseillé pour ce film dans cette pièce (et le
 * décodage auto), la piste audio, puis l'ampli : programme, volume, voix,
 * mode nuit, basses. Sans ampli : le conseil (son de la TV) et la piste.
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
    val touch = LocalScreen.current.isTouch
    Column(
        Modifier
            .fillMaxSize()
            .background(SubMenuScrim)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = gutter, vertical = 28.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        // ── En-tête : titre, pièce, retour au menu ──
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Audio", style = MaterialTheme.typography.headlineMedium, color = Color.White)
                Text(audio.room, style = MaterialTheme.typography.bodyLarge, color = Dim)
            }
            // Sans réglage d'ampli à proposer, le focus part de ce bouton
            GlassButton(
                "Menu pause",
                onClose,
                glyph = "‹",
                modifier = if (audio.hasAmp && advice.program != null) Modifier else Modifier.focusRequester(focus),
            )
        }

        // ── Son conseillé ──
        GlassSection("Son conseillé") {
            Text(advice.headline, style = MaterialTheme.typography.titleLarge, color = Color.White)
            if (advice.detail.isNotBlank()) {
                Text(advice.detail, style = MaterialTheme.typography.bodyMedium, color = Dim, modifier = Modifier.widthIn(max = 760.dp))
            }
            if (audio.hasAmp && advice.program != null) {
                Row(
                    Modifier.padding(top = 4.dp).touchRowScroll(touch),
                    horizontalArrangement = Arrangement.spacedBy(28.dp),
                    verticalAlignment = Alignment.Bottom,
                ) {
                    AmpGroup("Décodage auto") {
                        AmpChip("Activé", selected = audio.auto, modifier = Modifier.focusRequester(focus)) { onAuto(true) }
                        AmpChip("Désactivé", selected = !audio.auto) { onAuto(false) }
                    }
                    when {
                        amp?.soundProgram == advice.program -> Text(
                            "✓ Appliqué : ${AmpLogic.programName(advice.program)}",
                            style = MaterialTheme.typography.labelLarge,
                            color = ArrColors.Seen,
                            modifier = Modifier.padding(bottom = 10.dp),
                        )
                        audio.auto -> Text(
                            "S’applique tout seul au lancement et à chaque changement de piste",
                            style = MaterialTheme.typography.labelMedium,
                            color = Dim,
                            modifier = Modifier.padding(bottom = 10.dp),
                        )
                        else -> AmpChip("Appliquer : ${AmpLogic.programName(advice.program)}", selected = false, onClick = onApplyAdvice)
                    }
                }
            }
        }

        // ── Piste audio du film (mêmes cartes que l'onglet Sous-titres) ──
        GlassSection("Piste audio") {
            // 6 dp : la carte grossie au focus n'est pas rognée par le bord de la rangée
            TracksPanel(trackChoices(tracks, C.TRACK_TYPE_AUDIO), allowOff = false, sidePadding = 6.dp, onSelect = onSelectTrack)
        }

        // ── Ampli ──
        if (amp != null && amp.online) {
            GlassSection("Ampli · ${AmpLogic.summary(amp)}") {
                Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                    Row(Modifier.touchRowScroll(touch), horizontalArrangement = Arrangement.spacedBy(28.dp)) {
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
                    Row(Modifier.touchRowScroll(touch), horizontalArrangement = Arrangement.spacedBy(28.dp)) {
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
                        Row(Modifier.touchRowScroll(touch), horizontalArrangement = Arrangement.spacedBy(28.dp)) {
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
                }
            }
        } else if (audio.hasAmp) {
            GlassSection("Ampli") {
                Text("L’ampli ne répond pas : vérifie qu’il est allumé et sur le réseau.", style = MaterialTheme.typography.bodyMedium, color = ArrColors.Warning)
            }
        }

        if (!touch) Text("Retour : revenir au menu pause", style = MaterialTheme.typography.labelMedium, color = Dim)
    }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
}

/** Téléphone : une rangée de pastilles défile au doigt plutôt que de déborder (une position par rangée). */
@Composable
private fun Modifier.touchRowScroll(touch: Boolean): Modifier =
    if (touch) horizontalScroll(rememberScrollState()) else this

/** Groupe de pastilles avec son nom au-dessus (« Mode nuit » : Activé / Désactivé). */
@Composable
internal fun AmpGroup(label: String, chips: @Composable () -> Unit) {
    Column {
        Text(label, style = MaterialTheme.typography.labelMedium, color = Dim, maxLines = 1)
        // Petit retrait : la pastille grossie au focus n'est pas rognée
        Row(Modifier.padding(top = 6.dp, start = 2.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) { chips() }
    }
}

/** Pastille de réglage de l'ampli : celle du style commun (blanche au focus, ✓ si actuelle). */
@Composable
internal fun AmpChip(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) =
    GlassChip(label, selected, modifier, onClick)
