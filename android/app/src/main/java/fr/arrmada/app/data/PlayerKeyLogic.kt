package fr.arrmada.app.data

import android.view.KeyEvent

/**
 * Touches de la télécommande pendant la lecture (menu pause fermé), sans
 * écran : testé en JVM. Le lecteur demande « quelle action pour cette
 * touche ? », puis l'exécute ; la règle tient ici, en un seul endroit.
 *
 * OK fait d'abord ce que l'écran propose (carte « Épisode suivant », carte
 * de qualité, bouton « Passer l'intro »), sinon il met en pause.
 */
object PlayerKeyLogic {
    enum class Action {
        PLAY_NEXT, // épisode / film suivant, tout de suite
        ACCEPT_QUALITY, // « Passer en 1080p » accepté
        SKIP_SEGMENT, // fin de l'intro / du récap
        PAUSE_MENU, // pause + menu pause
        PLAY, // reprise (touche Lecture seule)
        SEEK_BACK, // −10 s (plus en restant appuyé)
        SEEK_FORWARD, // +30 s
        SHOW_BAR, // ↑ / ↓ : barre de progression quelques secondes
        EXIT, // Stop : quitter la lecture
        NONE, // touche laissée à Android
    }

    /** Ce que l'écran affiche au moment de l'appui. */
    data class Screen(
        val upNextShown: Boolean = false, // carte « Épisode suivant »
        val qualityCardShown: Boolean = false, // carte « Passer en 1080p ? »
        val skipShown: Boolean = false, // bouton « Passer l'intro / le récap »
        val hasNext: Boolean = false, // un épisode / film suivant existe
    )

    /** OK de la télécommande (et Entrée d'un clavier). */
    fun isConfirm(keyCode: Int): Boolean = keyCode == KeyEvent.KEYCODE_DPAD_CENTER || keyCode == KeyEvent.KEYCODE_ENTER

    /** Action d'un appui (touche enfoncée) sur [keyCode]. */
    fun action(keyCode: Int, screen: Screen): Action {
        if (isConfirm(keyCode)) {
            when {
                screen.upNextShown -> return Action.PLAY_NEXT
                screen.qualityCardShown -> return Action.ACCEPT_QUALITY
                screen.skipShown -> return Action.SKIP_SEGMENT
            }
        }
        return when (keyCode) {
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, KeyEvent.KEYCODE_MEDIA_PAUSE,
            KeyEvent.KEYCODE_SPACE -> Action.PAUSE_MENU
            KeyEvent.KEYCODE_MEDIA_PLAY -> Action.PLAY
            KeyEvent.KEYCODE_DPAD_LEFT, KeyEvent.KEYCODE_MEDIA_REWIND -> Action.SEEK_BACK
            KeyEvent.KEYCODE_DPAD_RIGHT, KeyEvent.KEYCODE_MEDIA_FAST_FORWARD -> Action.SEEK_FORWARD
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_DOWN -> Action.SHOW_BAR
            // Rien à enchaîner : la touche Suivant est laissée à Android
            KeyEvent.KEYCODE_MEDIA_NEXT -> if (screen.hasNext) Action.PLAY_NEXT else Action.NONE
            KeyEvent.KEYCODE_MEDIA_STOP -> Action.EXIT
            else -> Action.NONE
        }
    }
}
