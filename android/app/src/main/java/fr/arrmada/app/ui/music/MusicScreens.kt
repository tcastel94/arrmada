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
import fr.arrmada.app.data.MusicActionResult
import fr.arrmada.app.data.MusicAlbum
import fr.arrmada.app.data.MusicArtist
import fr.arrmada.app.data.MusicArtistDetail
import fr.arrmada.app.data.MusicArtistHit
import fr.arrmada.app.data.MusicDownloadAlbum
import fr.arrmada.app.data.MusicDownloads
import fr.arrmada.app.data.MusicStatus
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ArtImage
import fr.arrmada.app.ui.components.ChoiceDialog
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

    /** Sous-titre du menu d'un album : où il en est. */
    fun albumState(album: MusicAlbum): String = when (album.status) {
        "complete" -> "Complet sur le NAS"
        "partial" -> "${album.tracksHave} pistes sur ${album.tracksTotal} sur le NAS"
        else -> if (album.monitored) "Pas encore sur le NAS (recherché par Lidarr)" else "Pas sur le NAS (non suivi)"
    }

    /** Recherche automatique proposée : récupérer, compléter, ou meilleure version d'un album complet. */
    fun searchLabel(album: MusicAlbum): String = when (album.status) {
        "complete" -> "Chercher une meilleure version"
        "partial" -> "Récupérer les pistes manquantes"
        else -> "Récupérer cet album"
    }

    /** « Radiohead – Kid A » (sinon le nom du dossier). */
    fun downloadTitle(item: MusicDownloadAlbum): String =
        listOfNotNull(item.artist, item.album).joinToString(" – ").ifBlank { item.name }

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
    onDownloads: () -> Unit,
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
        else -> MusicContent(current, status?.hint, onArtist, onSearch, onDownloads)
    }
}

@Composable
private fun MusicContent(
    artists: List<MusicArtist>,
    hint: String?,
    onArtist: (Int) -> Unit,
    onSearch: () -> Unit,
    onDownloads: () -> Unit,
) {
    val first = remember { FocusRequester() }
    Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
        ScreenHeader("Musique", Fr.plural(artists.size, "artiste")) {
            ArrButton("Ajouter un artiste", onSearch, leading = "+", modifier = if (artists.isEmpty()) Modifier.focusRequester(first) else Modifier)
            // Albums restés dans le dossier de téléchargements, à importer
            ArrButton("Téléchargements", onDownloads, leading = "⇩")
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
    val scope = rememberCoroutineScope()
    var artist by remember { mutableStateOf<MusicArtistDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableStateOf(0) }
    var menu by remember { mutableStateOf<MusicAlbum?>(null) }

    LaunchedEffect(id, reload) {
        runCatching { repository.musicArtist(id) }
            .onSuccess { artist = it; error = null }
            .onFailure { error = it.message ?: "Lidarr ne répond pas" }
    }

    // Lance une recherche Lidarr et dit en clair ce qui se passe
    fun runAction(action: suspend () -> MusicActionResult) {
        scope.launch {
            runCatching { action() }
                .onSuccess { Toast.makeText(context, it.message, Toast.LENGTH_LONG).show(); reload++ }
                .onFailure { Toast.makeText(context, it.message ?: "Lidarr ne répond pas", Toast.LENGTH_LONG).show() }
        }
    }

    val current = artist
    when {
        current == null && error != null -> MessageScreen("Artiste indisponible", error, "Réessayer") { reload++ }
        current == null -> MessageScreen("Chargement…")
        else -> ArtistContent(
            artist = current,
            onAlbum = { album -> if (album.listenable) onAlbum(album) else menu = album },
            onAlbumMenu = { menu = it },
            onSearchMissing = { runAction { repository.musicSearchArtist(current.id) } },
            onRefresh = { runAction { repository.musicRefreshArtist(current.id) } },
        )
    }

    // OK sur un album absent, ou appui long sur n'importe quel album :
    // écouter, récupérer l'album / ses pistes manquantes, ou meilleure version
    menu?.let { album ->
        ChoiceDialog(
            title = album.title,
            subtitle = MusicRules.albumState(album),
            choices = listOfNotNull(
                ("Écouter" to { menu = null; onAlbum(album) }).takeIf { album.listenable },
                MusicRules.searchLabel(album) to { menu = null; runAction { repository.musicSearchAlbum(album.id) } },
            ),
            onDismiss = { menu = null },
        )
    }
}

@Composable
private fun ArtistContent(
    artist: MusicArtistDetail,
    onAlbum: (MusicAlbum) -> Unit,
    onAlbumMenu: (MusicAlbum) -> Unit,
    onSearchMissing: () -> Unit,
    onRefresh: () -> Unit,
) {
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
                        // Toujours proposés, comme pour un film ou une série :
                        // albums studio manquants (suivis au passage), discographie relue
                        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.padding(top = 10.dp)) {
                            ArrButton("Chercher les albums manquants", onSearchMissing, leading = "⇩", compact = true)
                            ArrButton("Actualiser", onRefresh, leading = "↻", compact = true)
                        }
                        Text(
                            "Appui long sur un album : le récupérer, compléter ses pistes ou chercher une meilleure version",
                            style = MaterialTheme.typography.labelMedium,
                            color = Dim,
                            modifier = Modifier.padding(top = 6.dp),
                        )
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
                        onLongClick = { onAlbumMenu(album) },
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

/**
 * Musique restée dans le dossier de téléchargements (SABnzbd) et ses
 * sous-dossiers, vue par Lidarr : OK sur un album prêt l'importe dans la
 * bibliothèque ; un album non reconnu montre la raison donnée par Lidarr.
 */
@Composable
fun MusicDownloadsScreen(repository: Repository) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var listing by remember { mutableStateOf<MusicDownloads?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var reload by remember { mutableStateOf(0) }
    val imported = remember { mutableStateListOf<String>() }
    val first = remember { FocusRequester() }

    LaunchedEffect(reload) {
        runCatching { repository.musicDownloads() }
            .onSuccess { listing = it; error = null }
            .onFailure { error = it.message ?: "Lidarr ne répond pas" }
    }

    val current = listing
    when {
        current == null && error != null -> MessageScreen("Téléchargements indisponibles", error, "Réessayer") { reload++ }
        current == null -> MessageScreen("Lidarr passe le dossier en revue…")
        current.albums.isEmpty() -> MessageScreen(
            "Rien à importer",
            "Aucune musique en attente dans " + current.folders.joinToString(" ou ").ifBlank { "le dossier de téléchargements" },
            "Relire le dossier",
        ) { reload++ }
        else -> Column(Modifier.fillMaxSize().background(ArrColors.Night)) {
            val ready = current.albums.count { it.ready }
            ScreenHeader(
                "Musique à importer",
                "${Fr.plural(current.albums.size, "album")} dans les téléchargements · ${Fr.plural(ready, "prêt")} à importer" +
                    if (current.ignored > 0) " · ${Fr.plural(current.ignored, "bonus de film")} ignoré${if (current.ignored > 1) "s" else ""}" else "",
            ) {
                ArrButton("Relire le dossier", { reload++ }, leading = "↻")
            }
            LazyColumn(
                contentPadding = PaddingValues(horizontal = gutter, vertical = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(current.albums, key = { it.folder }) { item ->
                    DownloadRow(
                        item = item,
                        done = item.folder in imported,
                        modifier = if (item == current.albums.first()) Modifier.focusRequester(first) else Modifier,
                        onClick = {
                            when {
                                item.folder in imported -> Unit
                                !item.ready -> Toast.makeText(context, item.reason ?: "Non reconnu par Lidarr", Toast.LENGTH_LONG).show()
                                else -> scope.launch {
                                    runCatching { repository.musicImport(item.folder) }
                                        .onSuccess { imported += item.folder; Toast.makeText(context, it.message, Toast.LENGTH_LONG).show() }
                                        .onFailure { Toast.makeText(context, it.message ?: "Import impossible", Toast.LENGTH_LONG).show() }
                                }
                            }
                        },
                    )
                }
            }
            LaunchedEffect(current) { runCatching { first.requestFocus() } }
        }
    }
}

@Composable
private fun DownloadRow(item: MusicDownloadAlbum, done: Boolean, modifier: Modifier, onClick: () -> Unit) {
    FocusPanel(onClick = onClick, modifier = modifier.fillMaxWidth().height(64.dp)) {
        Row(Modifier.fillMaxSize().padding(horizontal = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Column(Modifier.weight(1f)) {
                Text(MusicRules.downloadTitle(item), style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(
                    if (item.ready) {
                        "${Fr.plural(item.tracks, "piste")} · ${Fr.bytes(item.sizeBytes.toDouble())} · ${item.name}"
                    } else {
                        item.reason ?: "Non reconnu par Lidarr"
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = if (item.ready) Dim else ArrColors.Warning,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                when {
                    done -> "✓ Import lancé"
                    item.ready -> "OK pour importer"
                    else -> "À vérifier"
                },
                style = MaterialTheme.typography.labelLarge,
                color = if (done) ArrColors.Seen else Dim,
            )
        }
    }
}
