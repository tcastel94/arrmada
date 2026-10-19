package fr.arrmada.app.ui.detail

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
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
import coil.compose.AsyncImage
import fr.arrmada.app.data.Api
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

/**
 * Fiche d'un film : fond, logo, notes, pastilles techniques (4K, HDR,
 * Atmos…), résumé, boutons de lecture, bande-annonce et distribution.
 *
 * [onPlay] reçoit la position de départ en secondes (0 = depuis le début).
 */
@Composable
fun MovieScreen(
    radarrId: String,
    repository: Repository,
    api: Api,
    onPlay: (movie: MovieDetail, startSeconds: Int) -> Unit,
) {
    var movie by remember { mutableStateOf<MovieDetail?>(null) }
    var play by remember { mutableStateOf<PlayInfo?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val context = LocalContext.current
    val playFocus = remember { FocusRequester() }

    LaunchedEffect(radarrId) {
        try {
            val detail = repository.movie(radarrId)
            if (detail.error != null) {
                error = detail.error
                return@LaunchedEffect
            }
            movie = detail
            // Disponible dans Jellyfin ? Où en était-on ? (une seule requête)
            detail.tmdbId?.let { play = runCatching { repository.playMovie(it) }.getOrNull() }
        } catch (e: Exception) {
            error = e.message ?: "Serveur injoignable"
        }
    }

    val m = movie
    if (error != null) return MessageScreen("Fiche indisponible", error)
    if (m == null) return MessageScreen("Chargement…")

    val resumeAt = play?.resume?.takeIf { !it.watched && it.position > 0 }?.position
    val playable = play?.status == "ok"

    KenBurnsBackdrop(url = api.absolute(m.images.fanart ?: m.images.landscape)) {
        Column(Modifier.fillMaxSize().padding(start = 48.dp, top = 36.dp, end = 48.dp)) {
            // ── Logo ou titre ──
            val logo = api.absolute(m.images.bestLogo)
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
                m.ratings.tmdb?.let { Badge("TMDB %.1f".format(it)) }
                m.ratings.imdb?.let { Badge("IMDb %.1f".format(it)) }
                m.ratings.rottenTomatoes?.let { Badge("RT %d %%".format(it.toInt())) }
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

            // ── Actions ──
            Row(Modifier.padding(top = 18.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                val notReady = { Toast.makeText(context, play?.reason ?: "Lecture impossible : Jellyfin ne répond pas", Toast.LENGTH_LONG).show() }
                if (resumeAt != null) {
                    ArrButton("Reprendre à ${formatClock(resumeAt.toLong())}", { if (playable) onPlay(m, resumeAt) else notReady() }, primary = true, leading = "▶", modifier = Modifier.focusRequester(playFocus))
                    ArrButton("Depuis le début", { if (playable) onPlay(m, 0) else notReady() })
                } else {
                    ArrButton("Lire", { if (playable) onPlay(m, 0) else notReady() }, primary = true, leading = "▶", modifier = Modifier.focusRequester(playFocus))
                }
                m.trailerId?.takeIf { it.isNotBlank() }?.let { id ->
                    ArrButton("Bande-annonce", { openTrailer(context, id) })
                }
            }
            if (play != null && !playable) {
                Text(play?.reason ?: "", style = MaterialTheme.typography.labelMedium, color = ArrColors.Warning, modifier = Modifier.padding(top = 8.dp))
            }

            // ── Distribution ──
            if (m.cast.isNotEmpty()) {
                Text("Distribution", style = MaterialTheme.typography.titleMedium, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 22.dp, bottom = 8.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(16.dp), contentPadding = PaddingValues(end = 48.dp)) {
                    items(m.cast.take(15)) { person -> // pas de clé : deux rôles peuvent avoir le même nom
                        Column(Modifier.width(76.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(Modifier.size(60.dp).clip(CircleShape).background(ArrColors.Card)) {
                                if (person.photo != null) {
                                    AsyncImage(model = person.photo, contentDescription = person.name, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                                }
                            }
                            Text(person.name, style = MaterialTheme.typography.labelMedium, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center, modifier = Modifier.padding(top = 4.dp))
                            Text(person.character, style = MaterialTheme.typography.labelSmall, color = ArrColors.TextSecondary, maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
                        }
                    }
                }
            }
        }
    }
    LaunchedEffect(m.id) { runCatching { playFocus.requestFocus() } }
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

/** Bande-annonce dans l'appli YouTube (ou le navigateur s'il n'y en a pas). */
private fun openTrailer(context: android.content.Context, youtubeId: String) {
    val app = Intent(Intent.ACTION_VIEW, Uri.parse("vnd.youtube:$youtubeId"))
    val web = Intent(Intent.ACTION_VIEW, Uri.parse("https://www.youtube.com/watch?v=$youtubeId"))
    try {
        context.startActivity(app)
    } catch (_: ActivityNotFoundException) {
        try {
            context.startActivity(web)
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(context, "Installe l’appli YouTube pour voir la bande-annonce", Toast.LENGTH_LONG).show()
        }
    }
}
