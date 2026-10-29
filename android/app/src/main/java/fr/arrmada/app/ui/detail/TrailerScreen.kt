package fr.arrmada.app.ui.detail

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.annotation.OptIn
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView
import fr.arrmada.app.data.Api
import fr.arrmada.app.data.Repository
import fr.arrmada.app.data.TrailerInfo
import fr.arrmada.app.data.TrailerLogic
import fr.arrmada.app.data.TrailerSource
import fr.arrmada.app.ui.components.MessageScreen
import okhttp3.OkHttpClient

/**
 * Bande-annonce d'un film, en plein écran (bouton de la fiche, appui long).
 *
 * Fichier du NAS : lu ici avec le son et les commandes du lecteur (OK :
 * pause, gauche / droite : avancer, Retour : fiche). Sinon l'appli YouTube
 * s'ouvre par-dessus et cet écran se referme : Retour depuis YouTube ramène
 * à la fiche.
 */
@Composable
fun TrailerScreen(tmdbId: Long, radarrYoutubeId: String?, repository: Repository, api: Api, onClose: () -> Unit) {
    val context = LocalContext.current
    var info by remember { mutableStateOf<TrailerInfo?>(null) }
    var local by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }

    /** YouTube, ou un message si aucune appli ne sait l'ouvrir. */
    fun youtube(id: String?) {
        when {
            id == null -> message = "Pas de bande-annonce pour ce film."
            openYoutubeTrailer(context, id) -> onClose()
            else -> message = "Installe l’appli YouTube (ou SmartTube) pour voir la bande-annonce."
        }
    }

    LaunchedEffect(tmdbId) {
        val loaded = runCatching { repository.movieTrailer(tmdbId) }.getOrNull()
        info = loaded
        when (val source = TrailerLogic.choose(loaded, radarrYoutubeId)) {
            is TrailerSource.Local -> local = api.baseUrl + source.stream
            is TrailerSource.YouTube -> youtube(source.id)
            TrailerSource.None -> message = "Pas de bande-annonce pour ce film."
        }
    }

    BackHandler { onClose() }
    val url = local
    when {
        message != null -> MessageScreen("Bande-annonce", message, "Retour", onClose)
        url != null -> LocalTrailer(url, api.http, onEnded = onClose) {
            // Fichier illisible ici : YouTube en secours
            local = null
            youtube(TrailerLogic.youtubeId(info?.youtube, radarrYoutubeId))
        }
        else -> MessageScreen("Chargement de la bande-annonce…")
    }
}

/** Ouvre la bande-annonce dans une appli YouTube ; false si aucune ne répond. */
fun openYoutubeTrailer(context: Context, youtubeId: String): Boolean {
    for ((app, uri) in TrailerLogic.youtubeTargets(youtubeId)) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(uri)).apply { if (app != null) setPackage(app) }
        try {
            context.startActivity(intent)
            return true
        } catch (_: ActivityNotFoundException) {
            // appli absente : adresse suivante
        } catch (_: SecurityException) {
            // appli présente mais fermée aux autres : adresse suivante
        }
    }
    return false
}

/** Lecteur plein écran du fichier du NAS, avec ses commandes (Media3). */
@OptIn(UnstableApi::class)
@Composable
private fun LocalTrailer(url: String, http: OkHttpClient, onEnded: () -> Unit, onError: () -> Unit) {
    val context = LocalContext.current
    val player = remember(url) {
        ExoPlayer.Builder(context)
            .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(http)))
            .build()
            .apply {
                setMediaItem(MediaItem.fromUri(url))
                prepare()
                playWhenReady = true
            }
    }
    val ended by rememberUpdatedState(onEnded)
    val failed by rememberUpdatedState(onError)
    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_ENDED) ended()
            }

            override fun onPlayerError(error: PlaybackException) = failed()
        }
        player.addListener(listener)
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }
    AndroidView(
        factory = { ctx ->
            PlayerView(ctx).apply {
                this.player = player
                useController = true
                keepScreenOn = true
                setShowBuffering(PlayerView.SHOW_BUFFERING_WHEN_PLAYING)
                // La télécommande pilote le lecteur (OK, gauche / droite)
                isFocusable = true
                isFocusableInTouchMode = true
                requestFocus()
            }
        },
        modifier = Modifier.fillMaxSize().background(Color.Black),
    )
}
