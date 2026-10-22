package fr.arrmada.app.ui.request

import fr.arrmada.app.ui.components.LocalScreen
import fr.arrmada.app.ui.components.gutter
import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.LibraryItem
import fr.arrmada.app.data.LookupItem
import fr.arrmada.app.data.Repository
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.ContentRow
import fr.arrmada.app.ui.components.PosterCard
import fr.arrmada.app.ui.theme.ArrColors
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay

/** Résultats d'une recherche : ce qu'on a déjà, ce qu'on peut demander. */
data class SearchState(
    val query: String = "",
    val searching: Boolean = false,
    val library: List<LibraryItem> = emptyList(),
    val toRequest: List<LookupItem> = emptyList(),
    val error: String? = null,
)

/**
 * Recherche : au clavier ou à la voix (bouton « Dicter », ou touche micro /
 * recherche de la télécommande quand elle arrive jusqu'à l'appli).
 * Deux rangées : « Dans la médiathèque » (OK : fiche ou écran Série) et
 * « À demander » (OK : feuille Télécharger).
 *
 * [startWithVoice] : ouvre directement la dictée (touche recherche).
 */
@Composable
fun SearchScreen(
    repository: Repository,
    absolute: (String?) -> String?,
    startWithVoice: Boolean,
    onOpen: (LibraryItem) -> Unit,
    onOpenTracked: (LookupItem) -> Unit, // titre déjà suivi par Radarr / Sonarr
    onRequest: (LookupItem) -> Unit,
) {
    val context = LocalContext.current
    var query by remember { mutableStateOf("") }
    var state by remember { mutableStateOf(SearchState()) }

    // Dictée : l'écran de reconnaissance vocale d'Android (Google sur la Shield)
    val voice = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)?.firstOrNull()?.let { query = it }
        }
    }
    fun dictate() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "fr-FR")
            .putExtra(RecognizerIntent.EXTRA_PROMPT, "Un film, une série…")
        try {
            voice.launch(intent)
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(context, "Pas de reconnaissance vocale sur cet appareil", Toast.LENGTH_LONG).show()
        }
    }
    LaunchedEffect(startWithVoice) { if (startWithVoice) dictate() }

    // Recherche 0,4 s après la dernière frappe (pas une requête par lettre)
    LaunchedEffect(query) {
        val text = query.trim()
        if (text.length < 2) {
            state = SearchState(query = text)
            return@LaunchedEffect
        }
        delay(400)
        state = state.copy(query = text, searching = true, error = null)
        state = coroutineScope {
            val library = async { runCatching { repository.searchLibrary(text).items } }
            val lookup = async { runCatching { repository.lookup(text) } }
            val found = library.await()
            val remote = lookup.await()
            SearchState(
                query = text,
                library = found.getOrDefault(emptyList()),
                toRequest = remote.getOrDefault(emptyList()),
                error = if (found.isFailure && remote.isFailure) found.exceptionOrNull()?.message else null,
            )
        }
    }

    SearchContent(query, { query = it }, state, absolute, ::dictate, onOpen, onOpenTracked, onRequest)
}

/** Affichage de la recherche (séparé pour les captures d'écran de test). */
@Composable
fun SearchContent(
    query: String,
    onQuery: (String) -> Unit,
    state: SearchState,
    absolute: (String?) -> String?,
    onDictate: () -> Unit,
    onOpen: (LibraryItem) -> Unit,
    onOpenTracked: (LookupItem) -> Unit,
    onRequest: (LookupItem) -> Unit,
) {
    val fieldFocus = remember { FocusRequester() }
    var fieldFocused by remember { mutableStateOf(false) }
    // Titres déjà suivis par Radarr / Sonarr (OK : leur fiche), sauf ceux déjà
    // montrés dans « Dans la médiathèque » (la recherche par titre les a trouvés)
    val shown = state.library.map { (if (it.isMovie) "movie" else "series") + it.externalId }.toSet()
    val tracked = state.toRequest.filter { it.inLibrary && it.arrId != null && (it.type + it.arrId) !in shown }
    val toRequest = state.toRequest.filter { !(it.inLibrary && it.arrId != null) }

    Column(Modifier.fillMaxSize().background(ArrColors.Night).padding(top = 24.dp)) {
        Row(Modifier.padding(horizontal = gutter), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            val phone = LocalScreen.current.isPhone
            if (!phone) Text("Rechercher", style = MaterialTheme.typography.headlineMedium)
            BasicTextField(
                value = query,
                onValueChange = onQuery,
                singleLine = true,
                textStyle = MaterialTheme.typography.titleLarge.copy(color = ArrColors.Text),
                cursorBrush = SolidColor(ArrColors.Accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = {}),
                decorationBox = { inner ->
                    if (query.isEmpty()) Text("Titre d’un film ou d’une série", style = MaterialTheme.typography.titleLarge, color = ArrColors.TextSecondary)
                    inner()
                },
                modifier = Modifier
                    .then(if (phone) Modifier.weight(1f) else Modifier.width(460.dp))
                    .focusRequester(fieldFocus)
                    .onFocusChanged { fieldFocused = it.isFocused }
                    .clip(RoundedCornerShape(6.dp))
                    .background(ArrColors.Card)
                    .border(BorderStroke(if (fieldFocused) 2.dp else 1.dp, if (fieldFocused) ArrColors.Accent else ArrColors.Track), RoundedCornerShape(6.dp))
                    .padding(horizontal = 16.dp, vertical = 10.dp),
            )
            ArrButton("Dicter", onDictate, primary = true)
        }

        val status = when {
            state.searching -> "Recherche…"
            state.error != null -> state.error
            state.query.length >= 2 && state.library.isEmpty() && state.toRequest.isEmpty() -> "Aucun résultat pour « ${state.query} »"
            state.query.length < 2 -> "Tape au moins 2 lettres, ou dicte un titre."
            else -> null
        }
        if (status != null) {
            Text(status, style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(start = gutter, top = 14.dp))
        }

        LazyColumn(contentPadding = PaddingValues(top = 16.dp, bottom = 40.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            item {
                ContentRow("Dans la médiathèque", state.library, key = { it.type + it.externalId }) { item ->
                    PosterCard(absolute(item.posterUrl), item.title, onClick = { onOpen(item) }, width = 100.dp)
                }
            }
            item {
                ContentRow("Aussi dans Radarr / Sonarr", tracked, key = { "t" + it.type + it.arrId }) { item ->
                    PosterCard(item.posterUrl, item.title, onClick = { onOpenTracked(item) }, width = 100.dp)
                }
            }
            item {
                ContentRow("À demander", toRequest, key = { it.type + (it.tmdbId ?: it.tvdbId ?: it.title.hashCode().toLong()) }) { item ->
                    PosterCard(item.posterUrl, "${item.title}${item.year?.let { " ($it)" } ?: ""}", onClick = { onRequest(item) }, width = 100.dp)
                }
            }
        }
    }
    LaunchedEffect(Unit) { runCatching { fieldFocus.requestFocus() } }
}
