package fr.arrmada.app

import android.content.Intent
import fr.arrmada.app.data.HomeRowsLogic
import fr.arrmada.app.home.HomeRowsWorker
import android.os.Bundle
import android.view.KeyEvent
import androidx.compose.runtime.CompositionLocalProvider
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.rememberScreenLayout
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import fr.arrmada.app.ui.theme.ArrMadaTheme
import kotlinx.coroutines.flow.MutableStateFlow

/**
 * Unique fenêtre de l'appli : elle affiche l'écran courant et gère le
 * passage de l'un à l'autre (navigation), comme la pile de fenêtres de Kodi.
 * La touche Retour revient à l'écran précédent.
 */
class MainActivity : ComponentActivity() {

    /** Compteur incrémenté à chaque appui sur la touche recherche / micro. */
    private val searchRequests = MutableStateFlow(0)

    /** Intro animée à l'écran : une touche la passe (sans agir sur l'écran dessous). */
    private val intro = IntroKeys()

    /** Lien arrmada://… reçu d'une carte de l'accueil Android TV, en attente d'ouverture. */
    private val links = MutableStateFlow<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as ArrMadaApplication
        if (savedInstanceState == null) receive(intent)
        // Ouvert depuis une carte de l'accueil : on va droit au titre, sans l'intro
        if (links.value != null) app.introSeen = true
        // Rangées de l'accueil Android TV : passe toutes les 30 minutes
        HomeRowsWorker.schedule(this)
        setContent {
            // TV, tablette ou téléphone : transmis à tous les écrans
            CompositionLocalProvider(LocalScreen provides rememberScreenLayout()) {
                ArrMadaTheme { ArrMadaNavigation(app, searchRequests, intro, links) }
            }
        }
    }

    /** Appli déjà ouverte (singleTask) et clic sur une carte de l'accueil : même fenêtre, nouveau lien. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        receive(intent)
    }

    private fun receive(intent: Intent?) {
        intent?.dataString?.takeIf { HomeRowsLogic.parse(it) != null }?.let { links.value = it }
    }

    // Relevé des événements du serveur : seulement quand l'appli est à l'écran
    override fun onStart() {
        super.onStart()
        (application as ArrMadaApplication).events.start()
    }

    override fun onStop() {
        (application as ArrMadaApplication).events.stop()
        // Retour à l'accueil Android : « À suivre » montre ce qu'on vient d'arrêter
        HomeRowsWorker.syncSoon(this)
        super.onStop()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (intro.active.value) {
            if (event.action == KeyEvent.ACTION_UP) intro.skip.value = true
            return true // la touche n'atteint pas l'écran d'accueil
        }
        return super.dispatchKeyEvent(event)
    }

    /**
     * Touche « recherche » ou micro de la télécommande, quand Android la
     * transmet à l'appli (sur certaines télécommandes, l'Assistant Google la
     * garde pour lui) : ouvre la recherche en mode dictée.
     */
    override fun onSearchRequested(): Boolean {
        searchRequests.value++
        return true
    }
}

/** Intro à l'écran ([active]) et demande de la passer ([skip]), partagées avec l'activité. */
internal class IntroKeys {
    val active = MutableStateFlow(false)
    val skip = MutableStateFlow(false)
}
