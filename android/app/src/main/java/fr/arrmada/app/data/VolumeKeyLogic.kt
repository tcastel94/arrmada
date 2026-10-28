package fr.arrmada.app.data

import android.view.KeyEvent
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Réponse de POST /api/yamaha/control pour le volume et le muet. */
@Serializable
data class AmpLevel(
    val status: String = "error", // « ok », « no_amp » (pièce sans ampli), « error »
    @SerialName("volume_pct") val volumePct: Int? = null,
    val mute: Boolean? = null,
    @SerialName("actual_db") val actualDb: Double? = null,
)

/**
 * Touches volume de la télécommande → ampli Yamaha (testé sans écran).
 *
 * Android TV garde ces touches pour lui (HDMI-CEC, IR) : une appli ne les
 * reçoit jamais. Le service d'accessibilité d'ArrMada (amp/AmpVolumeService),
 * une fois activé, les lit avant le système et les envoie au serveur.
 */
object VolumeKeyLogic {
    enum class Key { UP, DOWN, MUTE }

    const val NO_AMP_PAUSE_MS = 10 * 60_000L // pièce sans ampli : on ne réessaie qu'au bout de 10 min
    const val ERROR_PAUSE_MS = 60_000L // serveur ou ampli injoignable : 1 min
    const val BATCH_MS = 150L // appuis rapprochés (touche maintenue) : un seul envoi

    fun keyOf(keyCode: Int): Key? = when (keyCode) {
        KeyEvent.KEYCODE_VOLUME_UP -> Key.UP
        KeyEvent.KEYCODE_VOLUME_DOWN -> Key.DOWN
        KeyEvent.KEYCODE_VOLUME_MUTE -> Key.MUTE
        else -> null
    }

    /** Pas Yamaha (0,5 dB) pour [presses] appuis, signe compris : comme « Vol + / Vol − » du menu pause. */
    fun step(presses: Int): Int = presses * AmpLogic.VOLUME_STEP

    /** « Ampli : 42 % », « Ampli : muet » ; null si le serveur n'a rien dit. */
    fun label(level: AmpLevel): String? = when {
        level.mute == true -> "Ampli : muet"
        level.volumePct != null -> "Ampli : ${level.volumePct} %" + (level.actualDb?.let { "  (" + AmpLogic.decibels(it) + ")" } ?: "")
        else -> null
    }

    /**
     * Garde-fou : quand l'ampli ne répond pas (ou que la pièce n'en a pas),
     * les touches retournent au système pendant un moment, au lieu de ne
     * plus rien faire du tout.
     */
    class Gate {
        private var pausedUntil = 0L

        fun handles(enabled: Boolean, nowMs: Long): Boolean = enabled && nowMs >= pausedUntil

        fun onResult(status: String?, nowMs: Long) {
            pausedUntil = when (status) {
                "ok" -> 0L
                "no_amp" -> nowMs + NO_AMP_PAUSE_MS
                else -> nowMs + ERROR_PAUSE_MS
            }
        }
    }
}
