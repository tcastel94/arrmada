package fr.arrmada.app.ui.settings

import android.content.Intent
import android.provider.Settings
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import fr.arrmada.app.amp.AmpVolumeService
import fr.arrmada.app.data.DefaultQuality
import fr.arrmada.app.data.HomeLayoutLogic
import fr.arrmada.app.home.HomeRowsWorker
import fr.arrmada.app.home.TvHomeRows
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.components.LocalScreen
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.player.ScreenCapabilities
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.launch
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.BuildConfig

// Écran Réglages de l'appli TV (serveur, appairage, accueil, touches volume…).

@Composable
internal fun SettingsScreen(app: ArrMadaApplication, onChangeServer: () -> Unit, onRepair: () -> Unit) {
    val focus = remember { FocusRequester() }
    // Défile au besoin : la liste des réglages dépasse la hauteur d'un téléphone en paysage
    Column(Modifier.fillMaxSize().background(ArrColors.Night).verticalScroll(rememberScrollState()).padding(horizontal = gutter * 2, vertical = 48.dp)) {
        Text("Réglages", style = MaterialTheme.typography.headlineMedium)
        Text("Serveur : ${app.prefs.serverUrl.orEmpty()}", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 18.dp))
        Text("Cette TV : ${app.prefs.deviceName ?: "—"}", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 6.dp))
        Text("Version : ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 6.dp))
        val settingsContext = LocalContext.current
        // Formats HDR de l'écran : sans « Dolby Vision », les films en Dolby Vision
        // profil 5 sont convertis en SDR par Jellyfin (sinon image violette)
        val screen = remember { ScreenCapabilities.label(settingsContext) }
        Text("Écran : $screen", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 6.dp))
        val settingsScope = rememberCoroutineScope()
        Row(Modifier.padding(top = 28.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ArrButton("Changer de serveur", onChangeServer, modifier = Modifier.focusRequester(focus))
            ArrButton("Refaire l’appairage", onRepair)
            // Mise à jour (ADR-009) : la fenêtre « disponible » s'ouvre d'elle-même si besoin
            ArrButton("Rechercher une mise à jour", {
                settingsScope.launch {
                    app.updates.checkNow()?.let { Toast.makeText(settingsContext, it, Toast.LENGTH_LONG).show() }
                }
            })
        }
        // Qualité de lecture par défaut (ADR-012) : l'original, ou le 1080p
        // converti par Jellyfin quand le réseau de cette TV ne suit pas la 4K
        var defaultQuality by remember { mutableStateOf(app.prefs.defaultQuality) }
        ArrButton(
            when (defaultQuality) {
                DefaultQuality.ORIGINAL -> "Qualité de lecture par défaut : Original"
                DefaultQuality.HD_1080 -> "Qualité de lecture par défaut : 1080p (20 Mb/s)"
            },
            {
                defaultQuality = if (defaultQuality == DefaultQuality.ORIGINAL) DefaultQuality.HD_1080 else DefaultQuality.ORIGINAL
                app.prefs.defaultQuality = defaultQuality
                app.prefs.qualityAsked = true // choisi ici : la question du lecteur ne se pose plus
            },
            leading = "◐",
            modifier = Modifier.padding(top = 16.dp),
        )
        Text(
            "Choisis 1080p si ta TV est en Wi-Fi ou si les films 4K coupent. L’original reste au menu pause › Qualité.",
            style = MaterialTheme.typography.bodyMedium,
            color = ArrColors.TextSecondary,
            modifier = Modifier.padding(top = 8.dp),
        )
        HomeLayoutSetting(app)
        // Touches volume de la télécommande → ampli Yamaha de la pièce (ADR-013)
        if (LocalScreen.current.isTv) AmpVolumeKeysSetting(app)
        // Accueil Android TV : rangée « À suivre » et chaîne « ArrMada · Ajouts récents »
        val context = LocalContext.current
        if (TvHomeRows.supported(context)) {
            var homeRows by remember { mutableStateOf(app.prefs.homeRows) }
            ArrButton(
                if (homeRows) "Accueil Android TV : rangées ArrMada affichées" else "Accueil Android TV : rangées ArrMada masquées",
                {
                    homeRows = !homeRows
                    app.prefs.homeRows = homeRows
                    HomeRowsWorker.syncSoon(context) // pose ou retire les rangées tout de suite
                },
                leading = if (homeRows) "✓" else "✕",
                modifier = Modifier.padding(top = 16.dp),
            )
            Text(
                "« À suivre » reprend un film en un clic, la chaîne ArrMada montre les derniers ajouts. Mises à jour en quittant l’appli et toutes les 30 min.",
                style = MaterialTheme.typography.bodyMedium,
                color = ArrColors.TextSecondary,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
    }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
}

/**
 * Réglage « Rangées de l'accueil » : OK sur une rangée l'affiche ou la
 * masque (✓ / ✕), ▲ la monte d'un cran. Enregistré tout de suite ; l'accueil
 * le relit en y revenant.
 */
@Composable
private fun HomeLayoutSetting(app: ArrMadaApplication) {
    var layout by remember { mutableStateOf(app.prefs.homeLayout) }
    fun save(next: List<HomeLayoutLogic.Slot>) {
        layout = next
        app.prefs.homeLayout = next
    }
    Text("Rangées de l’accueil", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 28.dp))
    Text(
        "OK affiche ou masque une rangée, ▲ la monte d’un cran.",
        style = MaterialTheme.typography.bodyMedium,
        color = ArrColors.TextSecondary,
        modifier = Modifier.padding(top = 4.dp),
    )
    layout.forEachIndexed { index, slot ->
        Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
            ArrButton(
                slot.row.label,
                { save(HomeLayoutLogic.toggle(layout, slot.row)) },
                primary = slot.visible,
                leading = if (slot.visible) "✓" else "✕",
                modifier = Modifier.width(220.dp),
            )
            if (index > 0) ArrButton("▲", { save(HomeLayoutLogic.moveUp(layout, slot.row)) }, compact = true)
        }
    }
}

/**
 * Réglage « Touches volume → ampli » : tant que le service d'accessibilité
 * n'est pas activé dans Android, un bouton y mène ; ensuite, un interrupteur.
 */
@Composable
private fun AmpVolumeKeysSetting(app: ArrMadaApplication) {
    val context = LocalContext.current
    var serviceOn by remember { mutableStateOf(AmpVolumeService.isEnabled(context)) }
    // Retour des Paramètres d'Android : l'état a pu changer
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { serviceOn = AmpVolumeService.isEnabled(context) }
    var keys by remember { mutableStateOf(app.prefs.ampVolumeKeys) }
    if (!serviceOn) {
        ArrButton(
            "Touches volume de la télécommande → ampli : activer",
            {
                try {
                    context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
                } catch (_: android.content.ActivityNotFoundException) {
                    Toast.makeText(context, "Paramètres › Préférences de l’appareil › Accessibilité › ArrMada", Toast.LENGTH_LONG).show()
                }
            },
            leading = "🔊",
            modifier = Modifier.padding(top = 16.dp),
        )
    } else {
        ArrButton(
            if (keys) "Touches volume de la télécommande : ampli Yamaha" else "Touches volume de la télécommande : volume de la TV",
            {
                keys = !keys
                app.prefs.ampVolumeKeys = keys
            },
            leading = if (keys) "✓" else "✕",
            modifier = Modifier.padding(top = 16.dp),
        )
    }
    Text(
        if (serviceOn) {
            "Vol + / Vol − / Muet règlent l’ampli de la pièce de cette TV, dans ArrMada comme dans les autres applis. Sans ampli dans la pièce ou serveur injoignable, les touches reviennent à la TV."
        } else {
            "Android TV garde les touches volume pour lui : pour qu’ArrMada les envoie à l’ampli Yamaha, active « ArrMada : volume de l’ampli » dans Paramètres › Accessibilité (une seule fois). Autre solution sans ArrMada : régler la télécommande de la Shield en IR sur l’ampli, ou activer le HDMI-CEC de l’ampli."
        },
        style = MaterialTheme.typography.bodyMedium,
        color = ArrColors.TextSecondary,
        modifier = Modifier.padding(top = 8.dp),
    )
}
