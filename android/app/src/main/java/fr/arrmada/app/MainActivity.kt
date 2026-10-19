package fr.arrmada.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import androidx.tv.material3.MaterialTheme
import androidx.tv.material3.Text
import fr.arrmada.app.data.ResumeEntry
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.detail.MovieScreen
import fr.arrmada.app.ui.home.HomeScreen
import fr.arrmada.app.ui.home.HomeViewModel
import fr.arrmada.app.ui.home.LibraryScreen
import fr.arrmada.app.ui.player.PlayRequest
import fr.arrmada.app.ui.player.PlayerScreen
import fr.arrmada.app.ui.setup.PairScreen
import fr.arrmada.app.ui.setup.ServerScreen
import fr.arrmada.app.ui.theme.ArrColors
import fr.arrmada.app.ui.theme.ArrMadaTheme

/**
 * Unique fenêtre de l'appli : elle affiche l'écran courant et gère le
 * passage de l'un à l'autre (navigation), comme la pile de fenêtres de Kodi.
 * La touche Retour revient à l'écran précédent.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as ArrMadaApplication
        setContent {
            ArrMadaTheme { ArrMadaNavigation(app) }
        }
    }
}

/** Les écrans et leurs adresses (« routes »). */
private object Routes {
    const val SERVER = "server"
    const val PAIR = "pair"
    const val HOME = "home"
    const val MOVIES = "movies"
    const val SETTINGS = "settings"
    const val MOVIE = "movie/{radarrId}"
    const val PLAY = "play/{kind}/{id}/{season}/{episode}/{start}?radarr={radarr}"

    fun movie(radarrId: String) = "movie/$radarrId"
    fun play(r: PlayRequest) = "play/${r.kind}/${r.id}/${r.season}/${r.episode}/${r.startSeconds}" +
        (r.radarrId?.let { "?radarr=$it" } ?: "")
}

@Composable
private fun ArrMadaNavigation(app: ArrMadaApplication) {
    val nav = rememberNavController()
    val paired by app.prefs.paired.collectAsStateWithLifecycle()
    val start = when {
        app.prefs.serverUrl == null -> Routes.SERVER
        !paired -> Routes.PAIR
        else -> Routes.HOME
    }

    // TV révoquée dans la web app (réponse 401) : retour à l'appairage
    LaunchedEffect(paired) {
        if (!paired && app.prefs.serverUrl != null && nav.currentDestination?.route !in listOf(Routes.PAIR, Routes.SERVER, null)) {
            nav.navigate(Routes.PAIR) { popUpTo(0) }
        }
    }

    NavHost(navController = nav, startDestination = start) {
        composable(Routes.SERVER) {
            ServerScreen(app.prefs) { nav.navigate(Routes.PAIR) { popUpTo(0) } }
        }
        composable(Routes.PAIR) {
            PairScreen(
                prefs = app.prefs,
                repository = app.repository,
                onPaired = { nav.navigate(Routes.HOME) { popUpTo(0) } },
                onChangeServer = { nav.navigate(Routes.SERVER) { popUpTo(0) } },
            )
        }
        composable(Routes.HOME) {
            val viewModel: HomeViewModel = viewModel { HomeViewModel(app.repository) }
            HomeScreen(
                viewModel = viewModel,
                api = app.api,
                onOpenMovie = { nav.navigate(Routes.movie(it.externalId)) },
                onOpenMovieById = { nav.navigate(Routes.movie(it.toString())) },
                onResume = { entry -> nav.navigate(Routes.play(resumeRequest(entry))) },
                onMovies = { nav.navigate(Routes.MOVIES) },
                onSettings = { nav.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.MOVIES) {
            LibraryScreen(app.repository, app.api) { nav.navigate(Routes.movie(it.externalId)) }
        }
        composable(Routes.MOVIE, arguments = listOf(navArgument("radarrId") { type = NavType.StringType })) { entry ->
            val radarrId = entry.arguments?.getString("radarrId").orEmpty()
            MovieScreen(radarrId, app.repository, app.api) { movie, start ->
                val tmdb = movie.tmdbId ?: return@MovieScreen
                nav.navigate(Routes.play(PlayRequest("movie", tmdb, radarrId = radarrId, startSeconds = start)))
            }
        }
        composable(
            Routes.PLAY,
            arguments = listOf(
                navArgument("kind") { type = NavType.StringType },
                navArgument("id") { type = NavType.LongType },
                navArgument("season") { type = NavType.IntType },
                navArgument("episode") { type = NavType.IntType },
                navArgument("start") { type = NavType.IntType },
                navArgument("radarr") { type = NavType.StringType; nullable = true; defaultValue = null },
            ),
        ) { entry ->
            val args = requireNotNull(entry.arguments)
            val request = PlayRequest(
                kind = args.getString("kind").orEmpty(),
                id = args.getLong("id"),
                season = args.getInt("season"),
                episode = args.getInt("episode"),
                radarrId = args.getString("radarr"),
                startSeconds = args.getInt("start"),
            )
            PlayerScreen(request, app) { nav.popBackStack() }
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(
                app = app,
                onChangeServer = { nav.navigate(Routes.SERVER) { popUpTo(0) } },
                onRepair = {
                    app.prefs.forgetPairing()
                    nav.navigate(Routes.PAIR) { popUpTo(0) }
                },
            )
        }
    }
}

/** « Reprendre » : relance le film ou l'épisode là où il s'était arrêté. */
private fun resumeRequest(entry: ResumeEntry): PlayRequest {
    val state = entry.state
    return PlayRequest(
        kind = if (entry.isEpisode) "episode" else "movie",
        id = state.id.toLongOrNull() ?: 0,
        season = state.season ?: 0,
        episode = state.episode ?: 0,
        radarrId = entry.item?.externalId?.takeIf { !entry.isEpisode },
        startSeconds = state.position,
    )
}

@Composable
private fun SettingsScreen(app: ArrMadaApplication, onChangeServer: () -> Unit, onRepair: () -> Unit) {
    val focus = remember { FocusRequester() }
    Column(Modifier.fillMaxSize().background(ArrColors.Night).padding(horizontal = 96.dp, vertical = 48.dp)) {
        Text("Réglages", style = MaterialTheme.typography.headlineMedium)
        Text("Serveur : ${app.prefs.serverUrl.orEmpty()}", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 18.dp))
        Text("Cette TV : ${app.prefs.deviceName ?: "—"}", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 6.dp))
        Text("Version : ${BuildConfig.VERSION_NAME}", style = MaterialTheme.typography.bodyLarge, color = ArrColors.TextSecondary, modifier = Modifier.padding(top = 6.dp))
        Row(Modifier.padding(top = 28.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            ArrButton("Changer de serveur", onChangeServer, modifier = Modifier.focusRequester(focus))
            ArrButton("Refaire l’appairage", onRepair)
        }
    }
    LaunchedEffect(Unit) { runCatching { focus.requestFocus() } }
}
