package fr.arrmada.app.amp

import android.accessibilityservice.AccessibilityService
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.view.KeyEvent
import android.view.accessibility.AccessibilityEvent
import android.widget.Toast
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.data.VolumeKeyLogic
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import java.util.concurrent.atomic.AtomicInteger

/**
 * Touches volume / muet de la télécommande → ampli Yamaha de la pièce.
 *
 * Pourquoi un service d'accessibilité : sur Android TV, le système garde les
 * touches volume pour lui (HDMI-CEC, IR) et ne les donne JAMAIS à l'appli au
 * premier plan. Un service d'accessibilité, activé une fois par
 * l'utilisateur (Paramètres › Accessibilité › ArrMada), les voit passer
 * avant le système : il les garde et les envoie au serveur, qui pilote
 * l'ampli de la pièce de cette TV (ADR-013). Marche aussi quand une autre
 * appli est à l'écran (Netflix, YouTube…).
 *
 * Sécurités : rien n'est intercepté si le réglage est coupé, si la TV n'est
 * pas appairée, sur un téléphone, ou pendant 10 min après une réponse « pas
 * d'ampli dans cette pièce » (1 min si le serveur ne répond pas) : les
 * touches reviennent alors au système, comme avant.
 */
class AmpVolumeService : AccessibilityService() {

    private val gate = VolumeKeyLogic.Gate()
    private val pending = AtomicInteger(0) // appuis pas encore envoyés (+ / −)
    private var batch: Job? = null
    private val main = Handler(Looper.getMainLooper())
    private var toast: Toast? = null

    private val app: ArrMadaApplication get() = application as ArrMadaApplication

    override fun onKeyEvent(event: KeyEvent): Boolean {
        val key = VolumeKeyLogic.keyOf(event.keyCode) ?: return false
        val prefs = app.prefs
        val enabled = prefs.ampVolumeKeys && prefs.token != null && prefs.serverUrl != null && isTv(this)
        if (!gate.handles(enabled, SystemClock.elapsedRealtime())) return false
        if (event.action == KeyEvent.ACTION_DOWN) {
            when (key) {
                VolumeKeyLogic.Key.UP -> queue(+1)
                VolumeKeyLogic.Key.DOWN -> queue(-1)
                VolumeKeyLogic.Key.MUTE -> if (event.repeatCount == 0) send("mute", JsonPrimitive("toggle"))
            }
        }
        return true // gardée (appui et relâché) : le système ne la traite pas en plus
    }

    /** Touche maintenue ou appuis rapides : un seul envoi pour la rafale. */
    private fun queue(delta: Int) {
        pending.addAndGet(delta)
        if (batch?.isActive == true) return
        batch = app.appScope.launch {
            delay(VolumeKeyLogic.BATCH_MS)
            val presses = pending.getAndSet(0)
            if (presses != 0) send("volume_step", JsonPrimitive(VolumeKeyLogic.step(presses)))
        }
    }

    private fun send(action: String, value: JsonElement) {
        app.appScope.launch {
            val level = runCatching { app.repository.ampKey(action, value) }.getOrNull()
            gate.onResult(level?.status, SystemClock.elapsedRealtime())
            val text = when (level?.status) {
                "ok" -> VolumeKeyLogic.label(level)
                "no_amp" -> "Pas d’ampli dans cette pièce : volume de la TV"
                else -> "Ampli injoignable : volume de la TV pendant 1 min"
            } ?: return@launch
            main.post { show(text) }
        }
    }

    private fun show(text: String) {
        toast?.cancel()
        toast = Toast.makeText(this, text, Toast.LENGTH_SHORT).also { it.show() }
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    companion object {
        private fun isTv(context: Context): Boolean =
            context.packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)

        /** Le service est-il activé dans les réglages d'accessibilité d'Android ? */
        fun isEnabled(context: Context): Boolean {
            val enabled = Settings.Secure.getString(context.contentResolver, Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES).orEmpty()
            val me = ComponentName(context, AmpVolumeService::class.java)
            return enabled.split(':').any { ComponentName.unflattenFromString(it) == me }
        }
    }
}
