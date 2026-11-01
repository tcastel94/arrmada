package fr.arrmada.app.ui.music

import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.Fr
import fr.arrmada.app.data.MusicAlbum
import fr.arrmada.app.data.MusicArtist
import fr.arrmada.app.data.MusicArtistDetail
import fr.arrmada.app.data.MusicArtistHit
import fr.arrmada.app.data.MusicStatus
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.Dim
import fr.arrmada.app.ui.components.FocusPanel
import fr.arrmada.app.ui.components.KenBurnsBackdrop
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.components.ScreenHeader
import fr.arrmada.app.ui.components.gutter
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/*
 * Musique sur la TV (ADR-015) : les artistes suivis par Lidarr, la fiche
 * d'un artiste avec ses albums, la recherche pour suivre un nouvel artiste.
 * L'écoute d'un album est dans MusicPlayerScreen.kt (pistes lues dans Jellyfin).
 */

/** Libellés des cartes, séparés pour les tests. */
object MusicRules {
    /** « 3 albums · 20/30 pistes ». */
    fun artistLine(artist: MusicArtist): String = listOfNotNull(
        Fr.plural(artist.albums, "album"),
        "${artist.tracksHave}/${artist.tracksTotal} pistes".takeIf { artist.tracksTotal > 0 },
    ).joinToString(" · ")

    /** Étiquette d'un album : rien s'il est complet, « 10/12 » s'il est partiel, « Absent » sinon. */
    fun albumTag(album: MusicAlbum): String? = when (album.status) {
        "complete" -> null
        "partial" -> "${album.tracksHave}/${album.tracksTotal}"
        else -> "Absent"
    }

    /** « Groupe · Electronic ». */
    fun hitLine(hit: MusicArtistHit): String = listOfNotNull(
        when (hit.type) {
            "Group" -> "Groupe"
            "Person" -> "Artiste"
            else -> null
        },
        *hit.genres.toTypedArray(),
    ).joinToString(" · ").ifBlank { "MusicBrainz" }
}

/** Grille des artistes suivis, avec « Ajouter un artiste ». */
@Composable
fun MusicScreen(
    repository: Repository,
    onArtist: (Int) -> Unit,
    onSearch: () -> Unit,
) {
    var status by remember { mutableStateOf<MusicStatus?>(null) }
    var artists by remember { mutableStateOf<List<MusicArtist>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableStateOf(0) }

    // Relu à chaque retour (un artiste ajouté depuis la recherche apparaît)
    LaunchedEffect(reload) {
        error = null
        runCatching { repository.musicStatus() }
            .onSuccess { status = it }
            .onFailure { error = it.message ?: "Serveur injoignable"; return@LaunchedEffect }
        if (status?.lidarr == true) {
            runCatching { repository.musicArtists() }
                .onSuccess { artists = it.artists }
                .onFailure { error = it.message ?: "Lidarr ne répond pas" }
        } else {
            artists = emptyList()
        }
    }

    val current = artists
    when {
        error != null && current == null -> MessageScreen("Musique indisponible", error, "Réessayer") { reload++ }
        current == null -> MessageScreen("Chargement…")
        status?.lidarr != true -> MessageScreen("Musique", status?.hint ?: "Lidarr n'est pas configuré dans ArrMada.")
        else -> MusicContent(current, status?.hint, onArtist, onSearch)
    }
}

@Composable
private fun MusicContent(
    artists: List<MusicArtist>,
    hint: String?,
    onArtist: (Int) -> Unit,
    onSearch: () -> Unit,
) {
    val first = remember { FocusRequester() }
    Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
        ScreenHeader("Musique", Fr.plural(artists.size, "artiste")) {
            ArrButton("Ajouter un artiste", onSearch, leading = "+", modifier = if (artists.isEmpty()) Modifier.focusRequester(first) else Modifier)
        }
        // Conseil (bibliothèque Musique absente de Jellyfin…) : écouter sera impossible
        hint?.let {
            Text(
                it,
                style = MaterialTheme.typography.bodyMedium,
                color = ArrColors.Warning,
                modifier = Modifier.padding(start = gutter, end = gutter, top = 10.dp),
            )
        }
        if (artists.isEmpty()) {
            Text(
                "Aucun artiste suivi. « Ajouter un artiste » le cherche sur MusicBrainz, Lidarr télécharge ses albums.",
                style = MaterialTheme.typography.bodyLarge,
                color = Dim,
                modifier = Modifier.padding(gutter),
            )
        } else {
            LazyVerticalGrid(
                columns = GridCells.Adaptive(120.dp),
                contentPadding = PaddingValues(horizontal = gutter, vertical = 18.dp),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                items(artists, key = { it.id }) { artist ->
                    Column {
                        PosterCard(
                            imageUrl = artist.poster,
                            title = artist.name,
                            width = 120.dp,
                            square = true,
                            onClick = { onArtist(artist.id) },
                            modifier = if (artist == artists.first()) Modifier.focusRequester(first) else Modifier,
                        )
                        Text(artist.name, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 6.dp))
                        Text(MusicRules.artistLine(artist), style = MaterialTheme.typography.labelSmall, color = Dim, maxLines = 1)
                    }
                }
            }
        }
    }
    LaunchedEffect(artists.size) { runCatching { first.requestFocus() } }
}

/** Fiche d'un artiste : présentation, puis ses albums (OK sur un album : l'écouter). */
@Composable
fun MusicArtistScreen(
    repository: Repository,
    id: Int,
    onAlbum: (MusicAlbum) -> Unit,
) {
    val context = LocalContext.current
    var artist by remember { mutableStateOf<MusicArtistDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableStateOf(0) }

    LaunchedEffect(id, reload) {
        runCatching { repository.musicArtist(id) }
            .onSuccess { artist = it; error = null }
            .onFailure { error = it.message ?: "Lidarr ne répond pas" }
    }

    val current = artist
    when {
        current == null && error != null -> MessageScreen("Artiste indisponible", error, "Réessayer") { reload++ }
        current == null -> MessageScreen("Chargement…")
        else -> ArtistContent(current) { album ->
            if (album.listenable) {
                onAlbum(album)
            } else {
                Toast.makeText(context, "« ${album.title} » n’est pas encore sur le NAS", Toast.LENGTH_SHORT).show()
            }
        }
    }
}

@Composable
private fun ArtistContent(artist: MusicArtistDetail, onAlbum: (MusicAlbum) -> Unit) {
    val first = remember { FocusRequester() }
    KenBurnsBackdrop(url = artist.fanart ?: artist.poster) {
        LazyVerticalGrid(
            columns = GridCells.Adaptive(120.dp),
            contentPadding = PaddingValues(start = gutter, end = gutter, top = 30.dp, bottom = 24.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
            modifier = Modifier.fillMaxSize(),
        ) {
            // En-tête sur toute la largeur de la grille
            item(span = { androidx.compose.foundation.lazy.grid.GridItemSpan(maxLineSpan) }) {
                Row(horizontalArrangement = Arrangement.spacedBy(20.dp), verticalAlignment = Alignment.Bottom, modifier = Modifier.padding(bottom = 10.dp)) {
                    ArtImage(artist.poster, artist.name, Modifier.size(132.dp).clip(RoundedCornerShape(16.dp)))
                    Column(Modifier.widthIn(max = 600.dp)) {
                        Text(artist.name, style = MaterialTheme.typography.displayMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            listOfNotNull(
                                Fr.plural(artist.albums, "album"),
                                "${artist.tracksHave}/${artist.tracksTotal} pistes sur le NAS".takeIf { artist.tracksTotal > 0 },
                                artist.genres.take(3).joinToString(", ").ifBlank { null },
                            ).joinToString("  ·  "),
                            style = MaterialTheme.typography.labelLarge,
                            color = Dim,
                            modifier = Modifier.padding(top = 6.dp),
                        )
                        artist.overview?.let {
                            Text(it, style = MaterialTheme.typography.bodyMedium, color = Dim, maxLines = 3, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 6.dp))
                        }
                    }
                }
            }
            items(artist.albumList, key = { it.id }) { album ->
                Column {
                    PosterCard(
                        imageUrl = album.cover,
                        title = album.title,
                        width = 120.dp,
                        square = true,
                        tag = MusicRules.albumTag(album),
                        onClick = { onAlbum(album) },
                        modifier = if (album == artist.albumList.firstOrNull { it.listenable } ?: artist.albumList.first()) Modifier.focusRequester(first) else Modifier,
                    )
                    Text(album.title, style = MaterialTheme.typography.labelLarge, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 6.dp))
                    Text(
                        listOfNotNull(album.year?.toString(), album.type.takeIf { it != "Album" }).joinToString(" · "),
                        style = MaterialTheme.typography.labelSmall,
                        color = Dim,
                        maxLines = 1,
                    )
                }
            }
        }
    }
    LaunchedEffect(artist.id) { if (artist.albumList.isNotEmpty()) runCatching { first.requestFocus() } }
}

/** Chercher un artiste et le suivre (Lidarr télécharge ses albums). */
@Composable
fun MusicSearchScreen(repository: Repository) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val fieldFocus = remember { FocusRequester() }
    var query by remember { mutableStateOf("") }
    var fieldFocused by remember { mutableStateOf(false) }
    var results by remember { mutableStateOf<List<MusicArtistHit>>(emptyList()) }
    var searching by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val followed = remember { mutableStateListOf<String>() }

    // Recherche une demi-seconde après la dernière lettre (pas à chaque touche)
    LaunchedEffect(query) {
        val term = query.trim()
        if (term.length < 2) {
            results = emptyList()
            return@LaunchedEffect
        }
        delay(500)
        searching = true
        runCatching { repository.musicLookup(term) }
            .onSuccess { results = it.results; error = null }
            .onFailure { error = it.message ?: "Lidarr ne répond pas" }
        searching = false
    }

    Column(Modifier.fillMaxSize().background(ArrColors.Night).padding(top = 28.dp)) {
        Row(Modifier.padding(horizontal = gutter), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Text("Ajouter un artiste", style = MaterialTheme.typography.headlineMedium)
            BasicTextField(
                value = query,
                onValueChange = { query = it },
                singleLine = true,
                textStyle = MaterialTheme.typography.titleLarge.copy(color = ArrColors.Text),
                cursorBrush = SolidColor(ArrColors.Accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = {}),
                decorationBox = { inner ->
                    if (query.isEmpty()) Text("Nom d’un artiste ou d’un groupe", style = MaterialTheme.typography.titleLarge, color = Dim)
                    inner()
                },
                modifier = Modifier
                    .width(440.dp)
                    .focusRequester(fieldFocus)
                    .onFocusChanged { fieldFocused = it.isFocused }
                    .clip(RoundedCornerShape(14.dp))
                    .background(ArrColors.Card)
                    // Focus blanc, comme partout (le bleu est réservé à « en cours »)
                    .border(BorderStroke(if (fieldFocused) 2.dp else 1.dp, if (fieldFocused) Color.White else ArrColors.Track), RoundedCornerShape(14.dp))
                    .padding(horizontal = 16.dp, vertical = 10.dp),
            )
        }
        when {
            searching && results.isEmpty() -> Hint("Recherche sur MusicBrainz…")
            error != null -> Hint(error.orEmpty(), ArrColors.Error)
            query.trim().length >= 2 && results.isEmpty() && !searching -> Hint("Aucun artiste trouvé.")
        }
        LazyColumn(
            contentPadding = PaddingValues(horizontal = gutter, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(results, key = { it.mbid }) { hit ->
                val isFollowed = hit.inLibrary || hit.mbid in followed
                FocusPanel(
                    onClick = {
                        if (isFollowed) return@FocusPanel
                        scope.launch {
                            runCatching { repository.musicFollow(hit.mbid) }
                                .onSuccess {
                                    followed += hit.mbid
                                    Toast.makeText(context, "${hit.name} suivi : Lidarr cherche ses albums", Toast.LENGTH_LONG).show()
                                }
                                .onFailure { Toast.makeText(context, it.message ?: "Ajout impossible", Toast.LENGTH_LONG).show() }
                        }
                    },
                    modifier = Modifier.fillMaxWidth().height(64.dp),
                ) {
                    Row(Modifier.fillMaxSize().padding(horizontal = 12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        ArtImage(hit.poster, hit.name, Modifier.size(44.dp).clip(RoundedCornerShape(8.dp)))
                        Column(Modifier.weight(1f)) {
                            Text(hit.name, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                            Text(MusicRules.hitLine(hit), style = MaterialTheme.typography.labelMedium, color = Dim, maxLines = 1)
                        }
                        Box(contentAlignment = Alignment.CenterEnd) {
                            Text(
                                if (isFollowed) "✓ Suivi" else "OK pour suivre",
                                style = MaterialTheme.typography.labelLarge,
                                color = if (isFollowed) ArrColors.Seen else Dim,
                            )
                        }
                    }
                }
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { fieldFocus.requestFocus() } }
}

@Composable
private fun Hint(text: String, color: Color = Dim) {
    Text(text, style = MaterialTheme.typography.bodyLarge, color = color, modifier = Modifier.padding(start = gutter, end = gutter, top = 14.dp))
}
