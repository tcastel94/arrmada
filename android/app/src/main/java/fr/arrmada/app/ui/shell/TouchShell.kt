package fr.arrmada.app.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.FamilyProfile
import fr.arrmada.app.ui.components.FocusPanel
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.profiles.ProfileAvatar
import fr.arrmada.app.ui.theme.ArrColors

/** Onglet de la navigation tactile : écran (nom utilisé par `go`), libellé, pictogramme. */
data class ShellTab(val key: String, val label: String, val glyph: String)

/** Téléphone et tablette : ce qui est sous le pouce (le reste est dans « Plus »). */
val TOUCH_TABS = listOf(
    ShellTab("home", "Accueil", "⌂"),
    ShellTab("movies", "Films", "🎬"),
    ShellTab("series", "Séries", "📺"),
    ShellTab("search", "Rechercher", "🔍"),
    ShellTab("queue", "Téléch.", "⬇"),
    ShellTab("more", "Plus", "☰"),
)

/**
 * Navigation au doigt (téléphone, tablette) : barre en bas sur téléphone,
 * colonne à gauche sur tablette. À la TV, rien : le menu du haut de
 * l'accueil fait ce travail (comme l'add-on Kodi).
 *
 * [selected] : onglet de l'écran affiché ; [visible] faux sur les écrans
 * plein écran (fiche, lecteur, mise en route).
 */
@Composable
fun TouchShell(selected: String?, visible: Boolean, onGo: (String) -> Unit, content: @Composable () -> Unit) {
    val screen = LocalScreen.current
    if (!screen.isTouch) return content()
    if (screen.isPhone) {
        Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
            Box(Modifier.weight(1f).fillMaxWidth()) { content() }
            if (visible) {
                Row(
                    Modifier.fillMaxWidth().height(62.dp).background(ArrColors.CardDeep),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TOUCH_TABS.forEach { tab -> TabItem(tab, tab.key == selected, Modifier.weight(1f)) { onGo(tab.key) } }
                }
            }
        }
    } else {
        Row(Modifier.fillMaxSize().background(ArrColors.Night)) {
            if (visible) {
                Column(
                    Modifier.width(84.dp).fillMaxHeight().background(ArrColors.CardDeep).padding(vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    TOUCH_TABS.forEach { tab -> TabItem(tab, tab.key == selected, Modifier.fillMaxWidth().height(64.dp)) { onGo(tab.key) } }
                }
            }
            Box(Modifier.weight(1f).fillMaxHeight()) { content() }
        }
    }
}

@Composable
private fun TabItem(tab: ShellTab, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val color = if (selected) ArrColors.Accent else ArrColors.TextSecondary
    Column(
        modifier.clickable(onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(tab.glyph, fontSize = 20.sp, color = color, textAlign = TextAlign.Center)
        Text(tab.label, style = MaterialTheme.typography.labelSmall, color = color, maxLines = 1)
    }
}

/**
 * « Plus » (téléphone, tablette) : les écrans de la coquille qui n'ont pas
 * leur onglet en bas. [viewer] : profil en cours (null : pas de profils).
 */
@Composable
fun MoreScreen(viewer: FamilyProfile?, onGo: (String) -> Unit) {
    val entries = listOfNotNull(
        Triple("videos", "Vidéos", "Dossiers du NAS hors médiathèque (mangas Kai…)"),
        Triple("tonight", "Ce soir", "Ce qui sera fini avant l’heure choisie"),
        Triple("discover", "Découvrir", "Tendances et « Parce que tu as… »"),
        Triple("board", "Tableau de bord", "Médiathèque, stockage, services"),
        viewer?.let { Triple("profiles", "Changer de profil", "Profil en cours : ${it.name}") },
        Triple("settings", "Réglages", "Serveur, appairage, version"),
    )
    Column(Modifier.fillMaxSize().background(ArrColors.Night).verticalScroll(rememberScrollState())) {
        ScreenHeader("Plus", null)
        Column(Modifier.padding(horizontal = gutter, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            entries.forEach { (key, label, hint) ->
                FocusPanel(onClick = { onGo(key) }, modifier = Modifier.fillMaxWidth().height(68.dp)) {
                    Row(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                        if (key == "profiles" && viewer != null) {
                            ProfileAvatar(viewer, 36.dp, Modifier.padding(end = 12.dp))
                        }
                        Column {
                            Text(label, style = MaterialTheme.typography.titleMedium)
                            Text(hint, style = MaterialTheme.typography.labelSmall, color = Color(0xFFC9D3E0))
                        }
                    }
                }
            }
        }
    }
}
