package fr.arrmada.app.ui.music

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.data.MusicAlbumTracks
import fr.arrmada.app.data.MusicTrack
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.Dim
import fr.arrmada.app.ui.components.FocusPanel
import fr.arrmada.app.ui.components.GlassButton
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.ProgressBar
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay

/**
 * Écouter un album (ADR-015) : pistes lues dans Jellyfin, relayées par
 * ArrMada (/api/music/stream/…), jouées par le même moteur que les films
 * (Media3 ExoPlayer). À gauche la pochette, le titre et les commandes ; à
 * droite la liste des pistes, la piste en cours en bleu (« en cours »).
 *
 * La musique s'arrête en quittant l'écran (pas de lecture en arrière-plan).
 */
@Composable
fun MusicPlayerScreen(app: ArrMadaApplication, albumId: Int, startIndex: Int = 0) {
    var album by remember { mutableStateOf<MusicAlbumTracks?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableIntStateOf(0) }

    LaunchedEffect(albumId, reload) {
        runCatching { app.repository.musicAlbumTracks(albumId) }
            .onSuccess { album = it; error = null }
            .onFailure { error = it.message ?: "Serveur injoignable" }
    }

    val current = album
    when {
        current == null && error != null -> MessageScreen("Album indisponible", error, "Réessayer") { reload++ }
        current == null -> MessageScreen("Chargement…")
        !current.available || current.tracks.isEmpty() ->
            MessageScreen(current.title.ifBlank { "Album" }, current.reason ?: "Rien à écouter pour l’instant")
        else -> AlbumPlayer(app, current, startIndex.coerceIn(0, current.tracks.lastIndex))
    }
}

@Composable
private fun AlbumPlayer(app: ArrMadaApplication, album: MusicAlbumTracks, startIndex: Int) {
    val context = LocalContext.current
    val player = remember {
        ExoPlayer.Builder(context)
            // Même client HTTP que l'API : le jeton d'appareil accompagne le flux
            .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(app.api.http)))
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                true, // met en pause si une autre appli prend le son
            )
            .build()
    }
    var index by remember { mutableIntStateOf(startIndex) }
    var playing by remember { mutableStateOf(false) }
    var position by remember { mutableLongStateOf(0L) }
    var duration by remember { mutableLongStateOf(0L) }
    val playFocus = remember { FocusRequester() }
    val listState = rememberLazyListState()

    // L'album entier en file : la piste suivante s'enchaîne toute seule
    DisposableEffect(player) {
        val items = album.tracks.map { track ->
            MediaItem.Builder()
                .setMediaId(track.id)
                .setUri(app.api.absolute(track.stream))
                .setMediaMetadata(MediaMetadata.Builder().setTitle(track.title).setArtist(album.artist).setAlbumTitle(album.title).build())
                .build()
        }
        val listener = object : Player.Listener {
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) {
                index = player.currentMediaItemIndex
            }

            override fun onIsPlayingChanged(isPlaying: Boolean) {
                playing = isPlaying
            }
        }
        player.addListener(listener)
        player.setMediaItems(items, startIndex, 0L)
        player.prepare()
        player.play()
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }

    // Position et durée relues deux fois par seconde (la barre avance)
    LaunchedEffect(player) {
        while (true) {
            position = player.currentPosition.coerceAtLeast(0L)
            duration = player.duration.takeIf { it != C.TIME_UNSET && it > 0 } ?: (album.tracks.getOrNull(index)?.duration?.times(1000L) ?: 0L)
            delay(500)
        }
    }
    LaunchedEffect(index) { runCatching { listState.animateScrollToItem((index - 2).coerceAtLeast(0)) } }
    LaunchedEffect(Unit) { runCatching { playFocus.requestFocus() } }

    val track = album.tracks.getOrNull(index)
    KenBurnsBackdrop(url = album.cover) {
        Row(
            Modifier.fillMaxSize().padding(horizontal = gutter, vertical = 36.dp),
            horizontalArrangement = Arrangement.spacedBy(36.dp),
        ) {
            // ── Pochette, titre, progression, commandes ──
            Column(Modifier.width(380.dp)) {
                ArtImage(album.cover, album.title, Modifier.size(260.dp).clip(RoundedCornerShape(18.dp)))
                Text(
                    track?.title.orEmpty(),
                    style = MaterialTheme.typography.headlineMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 16.dp),
                )
                Text(
                    "${album.artist}  ·  ${album.title}",
                    style = MaterialTheme.typography.labelLarge,
                    color = Dim,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.padding(top = 4.dp),
                )
                ProgressBar(
                    if (duration > 0) position.toFloat() / duration else 0f,
                    Modifier.fillMaxWidth().padding(top = 14.dp),
                    height = 4.dp,
                )
                Row(Modifier.fillMaxWidth().padding(top = 4.dp)) {
                    Text(formatClock(position / 1000), style = MaterialTheme.typography.labelMedium, color = Dim)
                    Text(
                        "−" + formatClock(((duration - position).coerceAtLeast(0L)) / 1000),
                        style = MaterialTheme.typography.labelMedium,
                        color = Dim,
                        modifier = Modifier.weight(1f),
                        textAlign = androidx.compose.ui.text.style.TextAlign.End,
                    )
                }
                Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    GlassButton("Précédent", { if (player.hasPreviousMediaItem()) player.seekToPreviousMediaItem() else player.seekTo(0L) }, glyph = "⏮")
                    GlassButton(
                        if (playing) "Pause" else "Lecture",
                        { if (player.isPlaying) player.pause() else player.play() },
                        glyph = if (playing) "⏸" else "▶",
                        primary = true,
                        modifier = Modifier.focusRequester(playFocus),
                    )
                    GlassButton("Suivant", { if (player.hasNextMediaItem()) player.seekToNextMediaItem() }, glyph = "⏭")
                }
            }

            // ── Pistes : OK sur une piste la joue ──
            LazyColumn(
                state = listState,
                contentPadding = PaddingValues(vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(6.dp),
                modifier = Modifier.weight(1f),
            ) {
                itemsIndexed(album.tracks, key = { _, t -> t.id }) { i, t ->
                    TrackRow(t, current = i == index, onClick = {
                        player.seekTo(i, 0L)
                        player.play()
                    })
                }
            }
        }
    }
}

@Composable
private fun TrackRow(track: MusicTrack, current: Boolean, onClick: () -> Unit) {
    FocusPanel(onClick = onClick, modifier = Modifier.fillMaxWidth().height(46.dp), container = ArrColors.CardDeep.copy(alpha = 0.6f)) {
        Row(Modifier.fillMaxSize().padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                if (current) "♪" else track.number?.toString().orEmpty(),
                style = MaterialTheme.typography.labelLarge,
                // Bleu = « en cours » : la piste qui joue
                color = if (current) ArrColors.AccentText else Dim,
                modifier = Modifier.width(24.dp),
            )
            Text(
                track.title,
                style = MaterialTheme.typography.titleMedium,
                color = if (current) ArrColors.AccentText else ArrColors.Text,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            if (track.duration > 0) {
                Text(formatClock(track.duration.toLong()), style = MaterialTheme.typography.labelMedium, color = Dim)
            }
        }
    }
}
