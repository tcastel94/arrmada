package fr.arrmada.app.data

import android.view.KeyEvent
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Menu de l'appui long : le relâchement de OK qui l'a ouvert ne valide rien. */
class MenuKeyLogicTest {

    private val ok = KeyEvent.KEYCODE_DPAD_CENTER

    @Test
    fun heldOkThatOpenedTheMenuIsIgnored() {
        val gate = MenuKeyLogic.Gate()
        // OK toujours enfoncé à l'ouverture : répétitions puis relâchement
        assertTrue(gate.blocks(ok, KeyEvent.ACTION_DOWN, repeatCount = 2))
        assertTrue(gate.blocks(ok, KeyEvent.ACTION_DOWN, repeatCount = 3))
        assertTrue(gate.blocks(ok, KeyEvent.ACTION_UP, repeatCount = 0))
    }

    @Test
    fun newPressInTheMenuWorks() {
        val gate = MenuKeyLogic.Gate()
        gate.blocks(ok, KeyEvent.ACTION_UP, repeatCount = 0) // fin de l'appui long, ignorée
        assertFalse(gate.blocks(ok, KeyEvent.ACTION_DOWN, repeatCount = 0))
        assertFalse(gate.blocks(ok, KeyEvent.ACTION_UP, repeatCount = 0))
        // OK maintenu dans le menu : rien de bloqué non plus
        assertFalse(gate.blocks(ok, KeyEvent.ACTION_DOWN, repeatCount = 1))
    }

    @Test
    fun enterKeysToo() {
        assertTrue(MenuKeyLogic.Gate().blocks(KeyEvent.KEYCODE_ENTER, KeyEvent.ACTION_UP, repeatCount = 0))
        assertTrue(MenuKeyLogic.Gate().blocks(KeyEvent.KEYCODE_NUMPAD_ENTER, KeyEvent.ACTION_UP, repeatCount = 0))
    }

    @Test
    fun otherKeysAlwaysPass() {
        val gate = MenuKeyLogic.Gate()
        assertFalse(gate.blocks(KeyEvent.KEYCODE_DPAD_DOWN, KeyEvent.ACTION_DOWN, repeatCount = 0))
        assertFalse(gate.blocks(KeyEvent.KEYCODE_DPAD_UP, KeyEvent.ACTION_DOWN, repeatCount = 4))
        assertFalse(gate.blocks(KeyEvent.KEYCODE_BACK, KeyEvent.ACTION_UP, repeatCount = 0))
        // Les flèches n'arment pas OK : son relâchement reste ignoré
        assertTrue(gate.blocks(ok, KeyEvent.ACTION_UP, repeatCount = 0))
    }
}
