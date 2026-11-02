package fr.arrmada.app.data

import android.view.KeyEvent
import fr.arrmada.app.data.PlayerKeyLogic.Action
import fr.arrmada.app.data.PlayerKeyLogic.Screen
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Touches pendant la lecture : OK fait ce que l'écran propose, sinon pause. */
class PlayerKeyLogicTest {

    private val ok = KeyEvent.KEYCODE_DPAD_CENTER

    @Test
    fun okPausesWhenNothingIsOffered() {
        assertEquals(Action.PAUSE_MENU, PlayerKeyLogic.action(ok, Screen()))
        assertEquals(Action.PAUSE_MENU, PlayerKeyLogic.action(KeyEvent.KEYCODE_ENTER, Screen()))
        assertEquals(Action.PAUSE_MENU, PlayerKeyLogic.action(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, Screen()))
    }

    @Test
    fun okDoesWhatTheScreenOffersInOrder() {
        // Tout affiché : l'épisode suivant passe d'abord, puis la qualité, puis l'intro
        assertEquals(Action.PLAY_NEXT, PlayerKeyLogic.action(ok, Screen(upNextShown = true, qualityCardShown = true, skipShown = true)))
        assertEquals(Action.ACCEPT_QUALITY, PlayerKeyLogic.action(ok, Screen(qualityCardShown = true, skipShown = true)))
        assertEquals(Action.SKIP_SEGMENT, PlayerKeyLogic.action(ok, Screen(skipShown = true)))
        // Lecture/Pause n'accepte rien : il met en pause
        assertEquals(Action.PAUSE_MENU, PlayerKeyLogic.action(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, Screen(skipShown = true)))
    }

    @Test
    fun arrowsAndMediaKeys() {
        assertEquals(Action.SEEK_BACK, PlayerKeyLogic.action(KeyEvent.KEYCODE_DPAD_LEFT, Screen()))
        assertEquals(Action.SEEK_FORWARD, PlayerKeyLogic.action(KeyEvent.KEYCODE_MEDIA_FAST_FORWARD, Screen()))
        assertEquals(Action.SHOW_BAR, PlayerKeyLogic.action(KeyEvent.KEYCODE_DPAD_UP, Screen()))
        assertEquals(Action.PLAY, PlayerKeyLogic.action(KeyEvent.KEYCODE_MEDIA_PLAY, Screen()))
        assertEquals(Action.EXIT, PlayerKeyLogic.action(KeyEvent.KEYCODE_MEDIA_STOP, Screen()))
        assertEquals(Action.NONE, PlayerKeyLogic.action(KeyEvent.KEYCODE_VOLUME_UP, Screen()))
    }

    @Test
    fun nextKeyOnlyWhenSomethingFollows() {
        assertEquals(Action.PLAY_NEXT, PlayerKeyLogic.action(KeyEvent.KEYCODE_MEDIA_NEXT, Screen(hasNext = true)))
        assertEquals(Action.NONE, PlayerKeyLogic.action(KeyEvent.KEYCODE_MEDIA_NEXT, Screen()))
    }

    @Test
    fun confirmKeys() {
        assertTrue(PlayerKeyLogic.isConfirm(ok))
        assertTrue(PlayerKeyLogic.isConfirm(KeyEvent.KEYCODE_ENTER))
        assertFalse(PlayerKeyLogic.isConfirm(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE))
    }
}
