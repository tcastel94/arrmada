package fr.arrmada.app.ui.detail

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import fr.arrmada.app.data.PlayOnTv
import fr.arrmada.app.data.WatchlistTarget
import fr.arrmada.app.ui.components.WatchlistButton
import fr.arrmada.app.ui.request.SendToTvDialog
import fr.arrmada.app.ui.components.tapToClick
import fr.arrmada.app.ui.components.touchScroll
import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.gutter
import android.view.TextureView
import androidx.annotation.OptIn
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import fr.arrmada.app.ui.components.Motion
import kotlinx.coroutines.delay
import okhttp3.OkHttpClient
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import coil.compose.AsyncImage
import fr.arrmada.app.data.Api
import fr.arrmada.app.data.CaseLogic
import fr.arrmada.app.data.FileInfo
import fr.arrmada.app.data.MovieDetail
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.Badge
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.formatClock
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.async
import kotlinx.coroutines.launch

/**
 * Fiche d'un film : fond, logo, notes, pastilles techniques (4K, HDR,
 * Atmos…), résumé, boutons de lecture, bande-annonce et distribution ; à
 * droite, le boîtier et son disque qui sort en roulant (comme l'add-on).
 *
 * [tmdbId] (connu quand on vient d'une grille ou de l'accueil) permet de
 * demander en même temps la fiche et les infos de lecture, au lieu de l'une
 * après l'autre. [onPlay] reçoit la position de départ en secondes.
 */
@Composable
fun MovieScreen(
    radarrId: String,
    tmdbId: Long?,
    repository: Repository,
    api: Api,
    onPlay: (movie: MovieDetail, startSeconds: Int) -> Unit,
    onDownload: (MovieDetail) -> Unit = {},
    // « Bande-annonce » : écran plein écran (fichier du NAS, sinon YouTube)
    onTrailer: (tmdbId: Long, radarrYoutubeId: String?) -> Unit = { _, _ -> },
    // Clic sur un acteur : sa filmographie
    onPerson: (tmdbId: Long) -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    var movie by remember { mutableStateOf<MovieDetail?>(null) }
    var play by remember { mutableStateOf<PlayInfo?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(radarrId) {
        try {
            // Les deux requêtes partent ensemble (souvent déjà en cache grâce
            // au préchargement de la carte survolée)
            val early = tmdbId?.let { id -> async { runCatching { repository.playMovie(id) }.getOrNull() } }
            val detail = repository.movie(radarrId)
            if (detail.error != null) {
                error = detail.error
                return@LaunchedEffect
            }
            movie = detail
            play = early?.await() ?: detail.tmdbId?.let { runCatching { repository.playMovie(it) }.getOrNull() }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    // Retour du lecteur : la position de reprise a changé, on la relit
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) {
        val id = movie?.tmdbId ?: return@LifecycleEventEffect
        scope.launch { runCatching { repository.playMovie(id) }.getOrNull()?.let { play = it } }
    }

    // Bande-annonce du NAS en fond, après 2,5 s sur la fiche (muette, une fois).
    // Les infos servent aussi au bouton « Bande-annonce » (YouTube de TMDB, en français)
    var trailer by remember { mutableStateOf<String?>(null) }
    var trailerDone by remember { mutableStateOf(false) }
    var trailerInfo by remember { mutableStateOf<fr.arrmada.app.data.TrailerInfo?>(null) }
    LaunchedEffect(movie?.tmdbId) {
        val id = movie?.tmdbId ?: return@LaunchedEffect
        val info = runCatching { repository.movieTrailer(id) }.getOrNull() ?: return@LaunchedEffect
        trailerInfo = info
        if (!Motion.enabled) return@LaunchedEffect
        if (info.status == "ok" && info.stream.isNotBlank()) {
            delay(2_500)
            trailer = api.baseUrl + info.stream
        }
    }

    val m = movie
    if (error != null) return MessageScreen("Fiche indisponible", error)
    if (m == null) return MessageScreen("Chargement…")
    val video = trailer?.takeIf { !trailerDone }
    val context = LocalContext.current
    var sending by remember { mutableStateOf(false) }
    MovieContent(
        m, play, api::absolute, onPlay, onDownload,
        backdropVideo = video?.let { url -> @Composable { TrailerVideo(url, api.http) { trailerDone = true } } },
        // Téléphone / tablette : « Sur la TV »
        onSendToTv = if (LocalScreen.current.isTouch && m.tmdbId != null) { { sending = true } } else null,
        onTrailer = m.tmdbId
            ?.takeIf { fr.arrmada.app.data.TrailerLogic.available(trailerInfo, m.trailerId) }
            ?.let { tmdb -> { onTrailer(tmdb, m.trailerId) } },
        onPerson = onPerson,
        // Liste « À voir » du profil qui regarde
        extraActions = {
            m.tmdbId?.let { tmdb ->
                WatchlistButton(WatchlistTarget("movie", tmdb, m.title, m.year, m.images.poster), repository)
            }
        },
    )
    if (sending) {
        SendToTvDialog(
            repository = repository,
            title = m.title,
            onDismiss = { sending = false },
            onSend = { target ->
                scope.launch {
                    val what = PlayOnTv("movie", m.tmdbId.toString(), title = m.title, resume = true)
                    val message = runCatching { repository.playOnTv(target.id, what) }
                        .fold({ it.message ?: "Envoyé sur ${target.name}" }, { it.message ?: "Échec" })
                    Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
                }
            },
        )
    }
}

/**
 * Bande-annonce en fond : lue sans le son, en fondu par-dessus le fond, puis
 * l'image revient à la fin. Dessinée dans une TextureView (et non la
 * SurfaceView habituelle) : c'est ce qui permet le fondu et les voiles
 * par-dessus la vidéo.
 */
@OptIn(UnstableApi::class)
@Composable
private fun TrailerVideo(url: String, http: OkHttpClient, onEnded: () -> Unit) {
    val context = LocalContext.current
    var shown by remember { mutableStateOf(false) }
    val player = remember {
        ExoPlayer.Builder(context)
            .setMediaSourceFactory(DefaultMediaSourceFactory(OkHttpDataSource.Factory(http)))
            .build()
            .apply {
                volume = 0f // muette : la fiche reste silencieuse
                setMediaItem(MediaItem.fromUri(url))
                prepare()
                playWhenReady = true
            }
    }
    val finish by rememberUpdatedState(onEnded)
    DisposableEffect(player) {
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_READY) shown = true
                if (state == Player.STATE_ENDED) finish()
            }

            override fun onPlayerError(error: PlaybackException) = finish()
        }
        player.addListener(listener)
        onDispose {
            player.removeListener(listener)
            player.release()
        }
    }
    val alpha by animateFloatAsState(if (shown) 1f else 0f, tween(900), label = "trailer")
    AndroidView(
        factory = { ctx -> TextureView(ctx).also { player.setVideoTextureView(it) } },
        modifier = Modifier.fillMaxSize().graphicsLayer { this.alpha = alpha },
    )
}

/** Affichage de la fiche (séparé du chargement pour les captures d'écran de test). */
@Composable
fun MovieContent(
    m: MovieDetail,
    play: PlayInfo?,
    absolute: (String?) -> String?,
    onPlay: (movie: MovieDetail, startSeconds: Int) -> Unit,
    onDownload: (MovieDetail) -> Unit = {},
    backdropVideo: (@Composable () -> Unit)? = null,
    onSendToTv: (() -> Unit)? = null,
    onTrailer: (() -> Unit)? = null,
    onPerson: ((tmdbId: Long) -> Unit)? = null,
    // Boutons en plus, après « Sur la TV » (« Ma liste »)
    extraActions: @Composable () -> Unit = {},
) {
    val context = LocalContext.current
    val playFocus = remember { FocusRequester() }
    val resumeAt = play?.resume?.takeIf { !it.watched && it.position > 0 }?.position
    val playable = play?.status == "ok"

    KenBurnsBackdrop(url = absolute(m.images.fanart ?: m.images.landscape), video = backdropVideo) {
        // Boîtier + disque, colonne de droite (comme l'add-on) ; pas sur un écran étroit
        val wide = LocalScreen.current.wide
        if (wide) {
            DiscCase(
                format = CaseLogic.format(m.hasFile, m.file),
                poster = absolute(m.images.poster),
                discart = absolute(m.images.discart),
                title = m.title,
                modifier = Modifier.align(Alignment.TopEnd).padding(top = 46.dp, end = 40.dp),
            )
        }
        // Texte et boutons à gauche : la place du disque sorti est laissée libre
        Column(Modifier.fillMaxSize().touchScroll().padding(start = gutter, top = 36.dp, end = if (wide) 360.dp else gutter, bottom = 24.dp)) {
            // ── Logo ou titre ──
            val logo = absolute(m.images.bestLogo)
            if (logo != null) {
                AsyncImage(
                    model = logo,
                    contentDescription = m.title,
                    contentScale = ContentScale.Fit,
                    alignment = Alignment.CenterStart,
                    modifier = Modifier.heightIn(max = 80.dp).widthIn(max = 340.dp),
                )
            } else {
                Text(m.title, style = MaterialTheme.typography.displayMedium)
            }

            // ── Méta, notes, pastilles ──
            Text(
                listOfNotNull(
                    m.year?.toString(),
                    m.runtime?.let { "${it / 60} h ${"%02d".format(it % 60)}" },
                    m.certification?.takeIf { it.isNotBlank() },
                    m.genres.take(3).joinToString(", ").ifBlank { null },
                ).joinToString("  ·  "),
                style = MaterialTheme.typography.labelLarge,
                color = ArrColors.TextSecondary,
                modifier = Modifier.padding(top = 12.dp),
            )
            Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                // IMDb d'abord (la plus fiable), TMDB seulement sans IMDb, puis la critique
                fr.arrmada.app.data.RatingLogic.detailBadges(m.ratings).forEach { Badge(it) }
                techBadges(m.file).forEach { Badge(it, highlight = true) }
            }

            Text(
                m.overview.orEmpty(),
                style = MaterialTheme.typography.bodyLarge,
                color = ArrColors.TextSecondary,
                maxLines = 5,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.widthIn(max = 560.dp).padding(top = 12.dp),
            )

            // ── Actions ── La rangée défile (au doigt, ou en suivant le focus à
            // la télécommande) plutôt que d'écraser les derniers boutons : à la TV,
            // « Reprendre à… » + « Depuis le début » + « Dans ma liste » ne
            // laissaient presque plus de place à « Bande-annonce »
            Row(
                Modifier.padding(top = 18.dp).horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                val notReady = { Toast.makeText(context, play?.reason ?: "Lecture impossible : Jellyfin ne répond pas", Toast.LENGTH_LONG).show() }
                if (resumeAt != null) {
                    ArrButton("Reprendre à ${formatClock(resumeAt.toLong())}", { if (playable) onPlay(m, resumeAt) else notReady() }, primary = true, leading = "▶", modifier = Modifier.focusRequester(playFocus))
                    ArrButton("Depuis le début", { if (playable) onPlay(m, 0) else notReady() })
                } else if (m.hasFile) {
                    ArrButton("Lire", { if (playable) onPlay(m, 0) else notReady() }, primary = true, leading = "▶", modifier = Modifier.focusRequester(playFocus))
                } else {
                    // Suivi par Radarr mais pas encore sur le disque
                    ArrButton("Télécharger", { onDownload(m) }, primary = true, modifier = Modifier.focusRequester(playFocus))
                }
                if (onTrailer != null) ArrButton("Bande-annonce", onTrailer, leading = "🎬")
                if (onSendToTv != null && playable) ArrButton("Sur la TV", onSendToTv, leading = "📺")
                extraActions()
            }
            if (play != null && !playable) {
                Text(play?.reason ?: "", style = MaterialTheme.typography.labelMedium, color = ArrColors.Warning, modifier = Modifier.padding(top = 8.dp))
            }

            // ── Distribution ──
            if (m.cast.isNotEmpty()) {
                Text("Distribution", style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 22.dp, bottom = 8.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(16.dp), contentPadding = PaddingValues(end = gutter)) {
                    items(m.cast.take(15)) { person -> // pas de clé : deux rôles peuvent avoir le même nom
                        // OK sur un acteur : sa filmographie (comme la web app)
                        val tmdb = person.tmdbId
                        CastCard(person, if (onPerson != null && tmdb != null) { { onPerson(tmdb) } } else null)
                    }
                }
            }
        }
    }
    LaunchedEffect(m.id) { runCatching { playFocus.requestFocus() } }
}

/** Un membre de la distribution ; cliquable (focus bleu) quand sa filmographie est connue. */
@Composable
private fun CastCard(person: fr.arrmada.app.data.Person, onClick: (() -> Unit)?) {
    val content = @Composable {
        Column(Modifier.width(76.dp).padding(vertical = 4.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.size(60.dp).clip(CircleShape).background(ArrColors.Card)) {
                if (person.photo != null) {
                    AsyncImage(model = person.photo, contentDescription = person.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                }
            }
            Text(person.name, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 4.dp))
            Text(person.character, style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
        }
    }
    if (onClick == null) return content()
    val shape = androidx.compose.foundation.shape.RoundedCornerShape(10.dp)
    androidx.tv.material3.Surface(
        onClick = onClick,
        modifier = Modifier.tapToClick(onClick),
        shape = androidx.tv.material3.ClickableSurfaceDefaults.shape(shape),
        scale = androidx.tv.material3.ClickableSurfaceDefaults.scale(focusedScale = 1.05f),
        border = androidx.tv.material3.ClickableSurfaceDefaults.border(
            focusedBorder = androidx.tv.material3.Border(androidx.compose.foundation.BorderStroke(3.dp, androidx.compose.ui.graphics.Color.White), shape = shape),
        ),
        colors = androidx.tv.material3.ClickableSurfaceDefaults.colors(
            containerColor = androidx.compose.ui.graphics.Color.Transparent,
            contentColor = ArrColors.Text,
            focusedContainerColor = ArrColors.Card,
            focusedContentColor = ArrColors.Text,
        ),
    ) { content() }
}

/** Pastilles « 4K », « Dolby Vision », « Atmos »… lues dans le fichier. */
fun techBadges(file: FileInfo?): List<String> {
    if (file == null) return emptyList()
    val badges = mutableListOf<String>()
    val height = file.height
    val quality = file.quality.orEmpty()
    val resolution = when {
        height != null && height >= 2000 -> "4K"
        height != null && height >= 1000 -> "1080p"
        height != null -> "${height}p"
        "2160" in quality -> "4K"
        "1080" in quality -> "1080p"
        else -> null
    }
    resolution?.let { badges.add(it) }
    val hdr = (file.dynamicRangeType ?: file.dynamicRange).orEmpty()
    when {
        "DV" in hdr -> badges.add("Dolby Vision")
        "HDR10+" in hdr || "HDR10Plus" in hdr -> badges.add("HDR10+")
        "HDR" in hdr -> badges.add("HDR")
    }
    val audio = file.audioCodec.orEmpty()
    when {
        "Atmos" in audio -> badges.add("Atmos")
        "TrueHD" in audio -> badges.add("TrueHD")
        "DTS-X" in audio || "DTS:X" in audio -> badges.add("DTS:X")
        "DTS" in audio -> badges.add("DTS")
    }
    val channels = file.audioChannels
    if (channels != null && channels > 2.0) badges.add("%.1f".format(java.util.Locale.ROOT, channels))
    return badges
}
