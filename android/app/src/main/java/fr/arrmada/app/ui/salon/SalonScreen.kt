package fr.arrmada.app.ui.salon

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.AmpProfile
import fr.arrmada.app.data.AmpState
import fr.arrmada.app.data.Device
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.SalonLogic
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.FocusPanel
import fr.arrmada.app.ui.components.Pill
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive

/** Relecture de l'état de l'ampli (l'add-on : 3 s). */
private const val REFRESH_MS = 3_000L

private val ROOM_NAMES = mapOf("salon" to "Salon", "cinema" to "Salle de cinéma", "bureau" to "Bureau")

/**
 * Salon : l'ampli Yamaha de la pièce de cette TV (marche / veille, volume,
 * muet, entrée, programme sonore) et les préréglages des pièces. Mêmes
 * commandes que l'add-on, à travers le serveur (`/api/yamaha/…`).
 */
@Composable
fun SalonScreen(repository: Repository) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var device by remember { mutableStateOf<Device?>(null) }
    var state by remember { mutableStateOf<AmpState?>(null) }
    var profiles by remember { mutableStateOf<Map<String, AmpProfile>>(emptyMap()) }
    var wake by remember { mutableIntStateOf(0) } // relance la lecture aussitôt après une commande

    LaunchedEffect(Unit) {
        device = runCatching { repository.device() }.getOrNull()
        profiles = runCatching { repository.ampProfiles() }.getOrDefault(emptyMap())
    }
    LaunchedEffect(wake) {
        while (true) {
            state = runCatching { repository.ampState() }.getOrNull()
            delay(REFRESH_MS)
        }
    }

    fun control(action: String, value: JsonPrimitive?) {
        scope.launch {
            runCatching { repository.ampControl(action, value) }
                .onSuccess { if (!it.ok) Toast.makeText(context, it.message ?: "L’ampli a refusé la commande", Toast.LENGTH_SHORT).show() }
                .onFailure { Toast.makeText(context, it.message ?: "Ampli injoignable", Toast.LENGTH_SHORT).show() }
            wake++
        }
    }

    fun preset(room: String) {
        scope.launch {
            runCatching { repository.applyRoomPreset(room) }
                .onSuccess { Toast.makeText(context, "Préréglage « ${profiles[room]?.name ?: room} » appliqué", Toast.LENGTH_SHORT).show() }
                .onFailure { Toast.makeText(context, it.message ?: "Échec", Toast.LENGTH_SHORT).show() }
            wake++
        }
    }

    SalonContent(
        device = device,
        state = state,
        profiles = profiles,
        onVolume = { step -> control("volume_step", JsonPrimitive(step)) },
        onMute = { control("mute", JsonPrimitive(!(state?.devices?.firstOrNull()?.mute ?: false))) },
        onPower = { on -> control("power", JsonPrimitive(if (on) "on" else "standby")) },
        onPreset = ::preset,
    )
}

/** Affichage (séparé pour les captures d'écran de test). */
@Composable
fun SalonContent(
    device: Device?,
    state: AmpState?,
    profiles: Map<String, AmpProfile>,
    onVolume: (Int) -> Unit,
    onMute: () -> Unit,
    onPower: (Boolean) -> Unit,
    onPreset: (String) -> Unit,
) {
    val hasAmp = device?.hasAmp ?: true
    val amp = state?.let { SalonLogic.amp(it) }
    val message = SalonLogic.message(state, hasAmp)
    val focus = remember { FocusRequester() }
    val roomName = device?.room?.let { ROOM_NAMES[it] ?: it.replaceFirstChar { c -> c.uppercase() } } ?: "—"

    Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
        ScreenHeader("Salon", "Pièce de cet appareil : $roomName")
        Row(Modifier.padding(horizontal = 48.dp, vertical = 20.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
            // ── Ampli ──
            Column(
                Modifier.width(520.dp).background(ArrColors.CardDeep, RoundedCornerShape(16.dp)).padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(amp?.name ?: "Ampli Yamaha", style = MaterialTheme.typography.headlineMedium, modifier = Modifier.weight(1f))
                    if (amp != null) {
                        Pill(
                            amp.power,
                            when {
                                amp.isOn -> ArrColors.Seen.copy(alpha = 0.3f)
                                amp.online -> ArrColors.Warning.copy(alpha = 0.3f)
                                else -> ArrColors.Error.copy(alpha = 0.3f)
                            },
                        )
                    }
                    if (amp?.mute == true) Pill("Muet", ArrColors.Error.copy(alpha = 0.3f))
                }
                if (amp != null && amp.online) {
                    Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("${amp.volumePct} %", style = MaterialTheme.typography.displayMedium)
                        Text(amp.decibels, style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(bottom = 6.dp))
                    }
                    ProgressBar(amp.volumePct / 100f, Modifier.fillMaxWidth(), height = 8.dp)
                    Text(
                        listOf("Entrée : ${amp.input}".takeIf { amp.input.isNotBlank() }, "Programme : ${amp.program}".takeIf { amp.program.isNotBlank() })
                            .filterNotNull().joinToString("   ·   "),
                        style = MaterialTheme.typography.bodyLarge,
                        color = ArrColors.TextSecondary,
                    )
                }
                message?.let { Text(it, style = MaterialTheme.typography.bodyLarge, color = ArrColors.Warning) }
                if (hasAmp && amp != null && amp.configured) {
                    Row(Modifier.padding(top = 6.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        ArrButton("Vol −", { onVolume(-SalonLogic.VOLUME_STEP) }, modifier = Modifier.focusRequester(focus))
                        ArrButton("Vol +", { onVolume(SalonLogic.VOLUME_STEP) })
                        ArrButton(if (amp.mute) "Son" else "Muet", onMute)
                        ArrButton(if (amp.isOn) "Veille" else "Allumer", { onPower(!amp.isOn) }, primary = !amp.isOn)
                    }
                }
            }

            // ── Préréglages des pièces ──
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Préréglages audio", style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary)
                val rooms = listOf("salon", "cinema").filter { it in profiles }
                if (rooms.isEmpty()) {
                    Text("Aucun préréglage (web app › Salon).", style = MaterialTheme.typography.bodyMedium, color = ArrColors.TextSecondary)
                }
                rooms.forEach { room ->
                    FocusPanel(
                        onClick = { onPreset(room) },
                        modifier = Modifier.fillMaxWidth().height(64.dp)
                            .then(if (!(hasAmp && amp?.configured == true) && room == rooms.first()) Modifier.focusRequester(focus) else Modifier),
                    ) {
                        Column(Modifier.padding(horizontal = 16.dp, vertical = 10.dp)) {
                            Text(profiles[room]?.name?.ifBlank { null } ?: ROOM_NAMES[room] ?: room, style = MaterialTheme.typography.titleMedium)
                            Text(
                                if (room == device?.room) "Pièce de cet appareil · Appliquer le préréglage" else "Appliquer le préréglage",
                                style = MaterialTheme.typography.labelSmall,
                                color = if (room == device?.room) ArrColors.AccentText else ArrColors.TextSecondary,
                            )
                        }
                    }
                }
                Text(
                    "Le préréglage de la pièce s’applique aussi tout seul au lancement d’un film ou d’un épisode.",
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0x99C9D3E0),
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
    LaunchedEffect(amp?.configured, profiles.isNotEmpty()) { runCatching { focus.requestFocus() } }
}
