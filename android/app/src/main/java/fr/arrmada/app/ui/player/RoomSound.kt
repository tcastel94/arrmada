package fr.arrmada.app.ui.player

import android.content.Context
import android.widget.Toast
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.data.AmpDevice
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.SoundAdvisor
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.JsonPrimitive

/**
 * Son de la pièce pendant la lecture : l'ampli (onglet « Ampli » du menu
 * pause), les enceintes déclarées pour la pièce et le décodage conseillé
 * (SoundAdvisor), appliqué tout seul à l'ampli si « Décodage auto » est
 * actif.
 *
 * Comme un petit service à part du lecteur : il garde son propre état (ampli
 * lu, pièce, enceintes, programme déjà appliqué) ; PlayerSurface lance ses
 * lectures ([readAmp], [readRoom], [autoProgram]) au bon moment et lui
 * transmet les commandes du menu pause ([ampCommand]).
 *
 * Une instance par lecture (créée avec `remember` dans PlayerSurface).
 */
@Stable
internal class RoomSound(
    app: ArrMadaApplication,
    private val repository: Repository,
    private val context: Context,
    private val uiScope: CoroutineScope,
    private val touch: Boolean,
) {
    // Ampli de la pièce (onglet « Ampli » du menu pause) : relu à l'ouverture du menu
    var amp by mutableStateOf<AmpDevice?>(null)
    var ampRead by mutableIntStateOf(0)

    // ── Son conseillé : enceintes de la pièce × son de la piste en cours ──
    var hasAmp by mutableStateOf(false)
    var layout by mutableStateOf<SoundAdvisor.Layout?>(null)
    var room by mutableStateOf("")
    var autoSound by mutableStateOf(app.prefs.autoSound)
    var appliedProgram by mutableStateOf<String?>(null)

    /** Relit l'état de l'ampli de la pièce (aucun ampli : null). */
    suspend fun readAmp() {
        val me = runCatching { repository.device() }.getOrNull()
        amp = if (me?.hasAmp == true) runCatching { repository.ampState().devices.firstOrNull() }.getOrNull() else null
    }

    /** Pièce de l'appareil, ses enceintes et son ampli (une fois, au démarrage). */
    suspend fun readRoom() {
        val me = runCatching { repository.device() }.getOrNull() ?: return
        hasAmp = me.hasAmp && !touch // l'ampli de la pièce ne concerne pas le téléphone
        if (!me.hasAmp) {
            room = if (touch) "Téléphone / tablette : son de l’appareil" else "Pas d’ampli dans cette pièce : son de la TV"
            return
        }
        val profiles = runCatching { repository.roomProfiles() }.getOrDefault(emptyMap())
        val profile = profiles[me.room] ?: profiles[if ("cin" in me.room.lowercase()) "cinema" else "salon"]
        // Enceintes non renseignées : on suppose un 5.1, le cas le plus courant
        layout = SoundAdvisor.layout(profile?.speakers) ?: SoundAdvisor.layout("5.1")
        room = listOfNotNull(
            profile?.name?.ifBlank { null } ?: me.room.replaceFirstChar { it.uppercase() },
            layout?.let { "enceintes ${it.label}" },
        ).joinToString(" · ")
    }

    /** Commande à l'ampli, puis relecture de son état (le réglage choisi s'entoure). */
    fun ampCommand(action: String, value: JsonPrimitive) {
        uiScope.launch {
            runCatching { repository.ampControl(action, value) }
                .onSuccess { if (!it.ok) Toast.makeText(context, it.message ?: "L’ampli a refusé le réglage", Toast.LENGTH_SHORT).show() }
                .onFailure { Toast.makeText(context, it.message ?: "Ampli injoignable", Toast.LENGTH_SHORT).show() }
            ampRead++
        }
    }

    /**
     * Décodage auto : dès que le son du film est connu (ou change de piste),
     * l'ampli prend le programme conseillé ([advice]), une fois le préréglage
     * terminé ([presetDone]).
     */
    suspend fun autoProgram(advice: SoundAdvisor.Advice, presetDone: CompletableDeferred<Unit>) {
        val program = advice.program ?: return
        if (!autoSound || !hasAmp || program == appliedProgram) return
        withTimeoutOrNull(10_000) { presetDone.await() }
        delay(800) // l'ampli finit d'appliquer le préréglage
        runCatching { repository.ampControl("sound_program", JsonPrimitive(program)) }.onSuccess {
            if (it.ok) {
                appliedProgram = program
                Toast.makeText(context, "Son : ${advice.headline}", Toast.LENGTH_SHORT).show()
            }
        }
        ampRead++
    }
}
