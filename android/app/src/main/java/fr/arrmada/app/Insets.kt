package fr.arrmada.app

import android.view.View
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

/**
 * Depuis Android 15, l'appli dessine sous la barre d'état et la barre de
 * navigation. On décale donc le contenu de la hauteur de ces barres (et du
 * clavier à l'écran quand il est ouvert), sinon le haut et le bas seraient
 * masqués. Renvoie aussi, via [onImeVisible], si le clavier est affiché.
 */
fun applySystemBarPadding(root: View, onImeVisible: ((Boolean) -> Unit)? = null) {
    ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
        val bars = insets.getInsets(
            WindowInsetsCompat.Type.systemBars() or
                WindowInsetsCompat.Type.displayCutout() or
                WindowInsetsCompat.Type.ime()
        )
        view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
        onImeVisible?.invoke(insets.isVisible(WindowInsetsCompat.Type.ime()))
        WindowInsetsCompat.CONSUMED
    }
}
