package fr.arrmada.app.ui.apps

import fr.arrmada.app.ui.components.gutter
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.drawable.Drawable
import android.widget.Toast
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.ui.components.FocusPanel
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Une appli installée : nom, tuile (bannière TV, sinon icône), comment la lancer. */
data class InstalledApp(val label: String, val packageName: String, val banner: ImageBitmap?, val isBanner: Boolean)

/**
 * Onglet « Applis » : l'équivalent sur Android TV des add-ons Kodi
 * (YouTube, IPTV…) de l'add-on, ce sont les applis installées sur la
 * Shield. OK lance l'appli ; Retour sur la télécommande ramène à ArrMada.
 */
@Composable
fun AppsScreen() {
    val context = LocalContext.current
    var apps by remember { mutableStateOf<List<InstalledApp>?>(null) }
    LaunchedEffect(Unit) { apps = withContext(Dispatchers.IO) { installedApps(context) } }
    AppsContent(apps) { app ->
        val intent = context.packageManager.getLeanbackLaunchIntentForPackage(app.packageName)
            ?: context.packageManager.getLaunchIntentForPackage(app.packageName)
        if (intent == null) {
            Toast.makeText(context, "Impossible de lancer ${app.label}", Toast.LENGTH_SHORT).show()
        } else {
            context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }
}

@Composable
fun AppsContent(apps: List<InstalledApp>?, onLaunch: (InstalledApp) -> Unit) {
    val focus = remember { FocusRequester() }
    Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
        ScreenHeader("Applis", apps?.let { "${it.size} applis installées sur cet appareil" } ?: "Lecture des applis…")
        LazyVerticalGrid(
            columns = GridCells.Adaptive(150.dp),
            contentPadding = PaddingValues(horizontal = gutter, vertical = 20.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            items(apps.orEmpty(), key = { it.packageName }) { app ->
                Column {
                    FocusPanel(
                        onClick = { onLaunch(app) },
                        scale = 1.08f,
                        modifier = Modifier.fillMaxWidth().height(90.dp)
                            .then(if (app == apps?.first()) Modifier.focusRequester(focus) else Modifier),
                    ) {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            val image = app.banner
                            if (image != null) {
                                Image(
                                    image,
                                    app.label,
                                    contentScale = if (app.isBanner) ContentScale.Crop else ContentScale.Fit,
                                    modifier = if (app.isBanner) Modifier.fillMaxSize() else Modifier.size(54.dp),
                                )
                            } else {
                                Text(app.label, style = MaterialTheme.typography.titleMedium, textAlign = TextAlign.Center)
                            }
                        }
                    }
                    Text(
                        app.label,
                        style = MaterialTheme.typography.labelMedium,
                        color = ArrColors.TextSecondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
            }
        }
    }
    LaunchedEffect(apps?.size) { runCatching { focus.requestFocus() } }
}

/** Applis à tuile TV (lanceur Android TV) d'abord, puis les applis classiques ; sans ArrMada. */
private fun installedApps(context: Context): List<InstalledApp> {
    val pm = context.packageManager
    val seen = mutableSetOf(context.packageName)
    val result = mutableListOf<InstalledApp>()
    for (category in listOf(Intent.CATEGORY_LEANBACK_LAUNCHER, Intent.CATEGORY_LAUNCHER)) {
        val intent = Intent(Intent.ACTION_MAIN).addCategory(category)
        for (info in pm.queryIntentActivities(intent, PackageManager.MATCH_ALL)) {
            val pkg = info.activityInfo.packageName
            if (!seen.add(pkg)) continue
            val banner = info.activityInfo.loadBanner(pm) ?: info.activityInfo.applicationInfo.loadBanner(pm)
            val drawable = banner ?: info.loadIcon(pm)
            result += InstalledApp(
                label = info.loadLabel(pm).toString(),
                packageName = pkg,
                banner = drawable?.let { toBitmap(it, if (banner != null) 320 else 128, if (banner != null) 180 else 128) },
                isBanner = banner != null,
            )
        }
    }
    return result.sortedBy { it.label.lowercase() }
}

/** Icône Android (Drawable) → image Compose, à la taille voulue. */
private fun toBitmap(drawable: Drawable, width: Int, height: Int): ImageBitmap {
    val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    drawable.setBounds(0, 0, width, height)
    drawable.draw(canvas)
    return bitmap.asImageBitmap()
}
