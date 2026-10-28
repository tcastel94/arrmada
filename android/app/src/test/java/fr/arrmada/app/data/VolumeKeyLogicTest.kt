package fr.arrmada.app.data

import android.view.KeyEvent
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Touches volume de la télécommande → ampli : touches gardées, pas, garde-fou, affichage. */
class VolumeKeyLogicTest {

    @Test
    fun onlyVolumeAndMuteKeys() {
        assertEquals(VolumeKeyLogic.Key.UP, VolumeKeyLogic.keyOf(KeyEvent.KEYCODE_VOLUME_UP))
        assertEquals(VolumeKeyLogic.Key.DOWN, VolumeKeyLogic.keyOf(KeyEvent.KEYCODE_VOLUME_DOWN))
        assertEquals(VolumeKeyLogic.Key.MUTE, VolumeKeyLogic.keyOf(KeyEvent.KEYCODE_VOLUME_MUTE))
        // Le reste de la télécommande n'est jamais touché
        assertNull(VolumeKeyLogic.keyOf(KeyEvent.KEYCODE_DPAD_CENTER))
        assertNull(VolumeKeyLogic.keyOf(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE))
        assertNull(VolumeKeyLogic.keyOf(KeyEvent.KEYCODE_MUTE)) // micro, pas le son
    }

    @Test
    fun stepsLikeThePauseMenu() {
        assertEquals(AmpLogic.VOLUME_STEP, VolumeKeyLogic.step(1))
        assertEquals(-3 * AmpLogic.VOLUME_STEP, VolumeKeyLogic.step(-3))
    }

    @Test
    fun gateGivesKeysBackToTheSystem() {
        val gate = VolumeKeyLogic.Gate()
        assertFalse(gate.handles(enabled = false, nowMs = 0))
        assertTrue(gate.handles(enabled = true, nowMs = 0))

        gate.onResult("no_amp", nowMs = 1_000)
        assertFalse(gate.handles(true, 1_000 + VolumeKeyLogic.NO_AMP_PAUSE_MS - 1))
        assertTrue(gate.handles(true, 1_000 + VolumeKeyLogic.NO_AMP_PAUSE_MS))

        gate.onResult(null, nowMs = 5_000) // serveur injoignable
        assertFalse(gate.handles(true, 5_000 + VolumeKeyLogic.ERROR_PAUSE_MS - 1))
        assertTrue(gate.handles(true, 5_000 + VolumeKeyLogic.ERROR_PAUSE_MS))

        gate.onResult("error", nowMs = 10_000)
        gate.onResult("ok", nowMs = 10_001) // l'ampli répond de nouveau : tout de suite
        assertTrue(gate.handles(true, 10_002))
    }

    @Test
    fun labelOfTheNewLevel() {
        assertEquals("Ampli : 42 %  (−38,5 dB)", VolumeKeyLogic.label(AmpLevel("ok", volumePct = 42, mute = false, actualDb = -38.5)))
        assertEquals("Ampli : 42 %", VolumeKeyLogic.label(AmpLevel("ok", volumePct = 42)))
        assertEquals("Ampli : muet", VolumeKeyLogic.label(AmpLevel("ok", volumePct = 42, mute = true)))
        assertNull(VolumeKeyLogic.label(AmpLevel("ok"))) // serveur ancien : pas de niveau en retour
    }

    @Test
    fun readsTheServerAnswer() {
        val json = Json { ignoreUnknownKeys = true }
        val level = json.decodeFromString(AmpLevel.serializer(), """{"status":"ok","action":"volume_step","volume_pct":43,"mute":false,"actual_db":-38.0}""")
        assertEquals(AmpLevel("ok", 43, false, -38.0), level)
        assertEquals("no_amp", json.decodeFromString(AmpLevel.serializer(), """{"status":"no_amp","detail":"Pas d'ampli dans cette pièce"}""").status)
    }
}
