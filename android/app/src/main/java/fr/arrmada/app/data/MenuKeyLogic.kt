package fr.arrmada.app.data

import android.view.KeyEvent

/**
 * Touche OK dans un menu ouvert par l'appui long (testé sans écran).
 *
 * C'est le maintien de OK qui ouvre le menu : quand il apparaît, la touche
 * est encore enfoncée. Android envoie la fin de cet appui (répétitions, puis
 * relâchement) à la fenêtre qui a le focus, donc au menu, et un bouton de
 * Compose for TV se déclenche au relâchement : le premier choix se validait
 * tout seul. Le [Gate] ignore OK tant qu'un nouvel appui n'a pas commencé
 * dans le menu.
 */
object MenuKeyLogic {
    /** Touches qui valident un bouton de Compose for TV (les mêmes que `Surface`). */
    private val CONFIRM_KEYS = setOf(KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER, KeyEvent.KEYCODE_NUMPAD_ENTER)

    /** Un par ouverture de menu. Les autres touches (flèches, Retour) passent toujours. */
    class Gate {
        private var armed = false // un appui sur OK a commencé dans le menu

        /** true : événement à ignorer (suite de l'appui qui a ouvert le menu). */
        fun blocks(keyCode: Int, action: Int, repeatCount: Int): Boolean {
            if (keyCode !in CONFIRM_KEYS) return false
            if (action == KeyEvent.ACTION_DOWN && repeatCount == 0) armed = true
            return !armed
        }
    }
}
