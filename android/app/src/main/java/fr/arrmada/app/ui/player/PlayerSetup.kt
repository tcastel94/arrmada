package fr.arrmada.app.ui.player

import android.content.Context
import android.content.pm.ActivityInfo
import androidx.annotation.OptIn
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.platform.LocalContext
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.trackselection.DefaultTrackSelector
import fr.arrmada.app.ArrMadaApplication

// Mise en place du lecteur, une fois par lecture : création d'ExoPlayer
// (langues préférées, décodeurs, accès au serveur) et, au téléphone ou à la
// tablette, passage en plein écran à l'horizontale. Appelés par PlayerSurface.

/**
 * Crée le lecteur ExoPlayer d'une lecture (appelé une fois, avec `remember`).
 * Il démarre seul dès qu'un flux lui est donné (PlayerSurface, par load()).
 */
@OptIn(UnstableApi::class)
internal fun createPlayer(context: Context, app: ArrMadaApplication): ExoPlayer {
    val trackSelector = DefaultTrackSelector(context).apply {
        setParameters(
            buildUponParameters()
                // Français d'abord, sinon la piste par défaut du fichier.
                // Pas de langue de sous-titres préférée : seuls les sous-titres
                // « forcés » (passages en langue étrangère) s'affichent d'office ;
                // les autres se choisissent dans le menu pause.
                .setPreferredAudioLanguages("fr", "en")
        )
    }
    // Décodeurs d'Android d'abord (passthrough vers l'ampli intact), FFmpeg
    // ensuite : il ne sert que pour un son qu'Android ne sait pas décoder,
    // ou en secours quand son décodeur plante (voir onPlayerError).
    val renderers = DefaultRenderersFactory(context)
        .setExtensionRendererMode(DefaultRenderersFactory.EXTENSION_RENDERER_MODE_ON)
        .setEnableDecoderFallback(true) // autre décodeur Android si le premier ne démarre pas
    // Flux et sous-titres passent par OkHttp (jeton d'appareil) ; DefaultDataSource
    // lit en plus les fichiers de l'appli : les pistes texte reçues en avance de
    // Jellyfin (LateSubtitleFetcher) sont posées à côté du flux depuis le disque
    val dataSources = DefaultDataSource.Factory(context, OkHttpDataSource.Factory(app.api.http))
    return ExoPlayer.Builder(context, renderers)
        .setMediaSourceFactory(DefaultMediaSourceFactory(dataSources))
        .setTrackSelector(trackSelector)
        .setAudioAttributes(
            AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MOVIE).build(),
            true,
        )
        .setSeekBackIncrementMs(10_000)
        .setSeekForwardIncrementMs(30_000)
        .build()
        // Le premier flux est chargé par load() (PlayerSurface), comme un changement
        // de flux : une lecture convertie dès le départ (réglage « 1080p »,
        // remux) pose les pistes texte du fichier à côté du flux, et doit
        // démarrer même si Jellyfin est encore en train de les extraire
        .apply { playWhenReady = true }
}

/** Téléphone / tablette ([touch]) : plein écran, à l'horizontale, pendant la lecture. */
@Composable
internal fun LandscapeFullscreen(touch: Boolean) {
    val context = LocalContext.current
    DisposableEffect(touch) {
        val activity = context.findActivity()
        if (!touch || activity == null) return@DisposableEffect onDispose {}
        val previous = activity.requestedOrientation
        activity.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE
        val bars = WindowCompat.getInsetsController(activity.window, activity.window.decorView)
        bars.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        bars.hide(WindowInsetsCompat.Type.systemBars())
        onDispose {
            bars.show(WindowInsetsCompat.Type.systemBars())
            activity.requestedOrientation = previous
        }
    }
}
