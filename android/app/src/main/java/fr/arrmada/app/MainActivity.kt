package fr.arrmada.app

import android.os.Bundle
import android.view.KeyEvent
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import fr.arrmada.app.data.FamilyProfile
import fr.arrmada.app.data.PlayAnnounce
import fr.arrmada.app.ui.profiles.ProfilesScreen
import fr.arrmada.app.data.TonightLogic
import fr.arrmada.app.notify.EventOverlays
import fr.arrmada.app.ui.apps.AppsScreen
import fr.arrmada.app.ui.board.DashboardScreen
import fr.arrmada.app.ui.components.Motion
import fr.arrmada.app.ui.downloads.DownloadsScreen
import fr.arrmada.app.ui.home.TonightScreen
import fr.arrmada.app.ui.intro.IntroAnimation
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
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
import fr.arrmada.app.data.DownloadTarget
import fr.arrmada.app.data.LibraryItem
import fr.arrmada.app.data.LookupItem
import fr.arrmada.app.data.ResumeEntry
import fr.arrmada.app.data.TmdbItem
import fr.arrmada.app.ui.components.ArrButton
import fr.arrmada.app.ui.components.MessageScreen
import fr.arrmada.app.ui.detail.MovieScreen
import fr.arrmada.app.ui.detail.SeriesScreen
import fr.arrmada.app.ui.home.DiscoverScreen
import fr.arrmada.app.ui.home.HomeActions
import fr.arrmada.app.ui.home.HomeScreen
import fr.arrmada.app.ui.home.HomeViewModel
import fr.arrmada.app.ui.home.LibraryScreen
import fr.arrmada.app.ui.player.PlayRequest
import fr.arrmada.app.ui.player.PlayerScreen
import fr.arrmada.app.ui.request.DownloadScreen
import fr.arrmada.app.ui.request.SearchScreen
import fr.arrmada.app.ui.setup.PairScreen
import fr.arrmada.app.ui.setup.ServerScreen
import fr.arrmada.app.ui.theme.ArrColors
import fr.arrmada.app.ui.theme.ArrMadaTheme
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch

/**
 * Unique fenêtre de l'appli : elle affiche l'écran courant et gère le
 * passage de l'un à l'autre (navigation), comme la pile de fenêtres de Kodi.
 * La touche Retour revient à l'écran précédent.
 */
class MainActivity : ComponentActivity() {

    /** Compteur incrémenté à chaque appui sur la touche recherche / micro. */
    private val searchRequests = MutableStateFlow(0)

    /** Intro animée à l'écran : une touche la passe (sans agir sur l'écran dessous). */
    private val intro = IntroKeys()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as ArrMadaApplication
        setContent {
            ArrMadaTheme { ArrMadaNavigation(app, searchRequests, intro) }
        }
    }

    // Relevé des événements du serveur : seulement quand l'appli est à l'écran
    override fun onStart() {
        super.onStart()
        (application as ArrMadaApplication).events.start()
    }

    override fun onStop() {
        (application as ArrMadaApplication).events.stop()
        super.onStop()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (intro.active.value) {
            if (event.action == KeyEvent.ACTION_UP) intro.skip.value = true
            return true // la touche n'atteint pas l'écran d'accueil
        }
        return super.dispatchKeyEvent(event)
    }

    /**
     * Touche « recherche » ou micro de la télécommande, quand Android la
     * transmet à l'appli (sur certaines télécommandes, l'Assistant Google la
     * garde pour lui) : ouvre la recherche en mode dictée.
     */
    override fun onSearchRequested(): Boolean {
        searchRequests.value++
        return true
    }
}

/** Les écrans et leurs adresses (« routes »). */
private object Routes {
    const val SERVER = "server"
    const val PAIR = "pair"
    const val HOME = "home"
    const val LIBRARY = "library/{type}" // grille Films ou Séries
    const val DISCOVER = "discover"
    const val SEARCH = "search?voice={voice}"
    const val DOWNLOAD = "download"
    const val SETTINGS = "settings"
    const val PROFILES = "profiles" // « Qui regarde ? » (ADR-008)
    const val DOWNLOADS = "downloads" // écran Téléchargements (file, « Pour ce soir »)
    const val BOARD = "board" // tableau de bord
    const val APPS = "apps"
    const val TONIGHT = "tonight"
    const val MOVIE = "movie/{radarrId}?tmdb={tmdb}"
    const val SHOW = "show/{sonarrId}"
    const val PLAY = "play/{kind}/{id}/{season}/{episode}/{start}?radarr={radarr}&sonarr={sonarr}"

    fun library(type: String) = "library/$type"
    fun search(voice: Boolean) = "search?voice=$voice"
    fun movie(radarrId: String, tmdbId: Long? = null) = "movie/$radarrId" + (tmdbId?.let { "?tmdb=$it" } ?: "")
    fun show(sonarrId: String) = "show/$sonarrId"
    fun play(r: PlayRequest) = "play/${r.kind}/${r.id}/${r.season}/${r.episode}/${r.startSeconds}" +
        "?radarr=${r.radarrId.orEmpty()}&sonarr=${r.sonarrId.orEmpty()}"
}

/** Intro à l'écran ([active]) et demande de la passer ([skip]), partagées avec l'activité. */
private class IntroKeys {
    val active = MutableStateFlow(false)
    val skip = MutableStateFlow(false)
}

private const val ENTER_MS = 180
private const val EXIT_MS = 120

/**
 * Précharge la fiche du titre survolé dès que le focus s'y arrête un instant
 * (0,35 s) : en appuyant sur OK, la fiche s'affiche sans attendre le serveur.
 * Un défilement rapide le long d'une rangée ne déclenche rien.
 */
private class Prefetcher(private val app: ArrMadaApplication) {
    private var pending: Job? = null

    fun focus(item: LibraryItem) {
        pending?.cancel()
        pending = app.appScope.launch {
            delay(350)
            // Lancé à part : une fois partie, la requête va au bout (et remplit le cache)
            app.appScope.launch { runCatching { app.repository.prefetch(item) } }
        }
    }
}

@Composable
private fun ArrMadaNavigation(app: ArrMadaApplication, searchRequests: MutableStateFlow<Int>, intro: IntroKeys) {
    val nav = rememberNavController()
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val paired by app.prefs.paired.collectAsStateWithLifecycle()
    val searchCount by searchRequests.collectAsStateWithLifecycle()
    val viewer by app.prefs.profile.collectAsStateWithLifecycle()
    val start = when {
        app.prefs.serverUrl == null -> Routes.SERVER
        !paired -> Routes.PAIR
        else -> Routes.PROFILES // « Qui regarde ? », passé tout seul sans profils
    }

    // TV révoquée dans la web app (réponse 401) : retour à l'appairage
    LaunchedEffect(paired) {
        if (!paired && app.prefs.serverUrl != null && nav.currentDestination?.route !in listOf(Routes.PAIR, Routes.SERVER, null)) {
            nav.navigate(Routes.PAIR) { popUpTo(0) }
        }
    }
    // Touche recherche / micro de la télécommande
    LaunchedEffect(searchCount) {
        if (searchCount > 0 && paired) nav.navigate(Routes.search(voice = true)) { launchSingleTop = true }
    }

    fun openItem(item: LibraryItem) {
        nav.navigate(if (item.isMovie) Routes.movie(item.externalId, item.tmdbId) else Routes.show(item.externalId))
    }

    val prefetcher = remember { Prefetcher(app) }

    fun openDownload(target: DownloadTarget) {
        app.pendingDownload = target
        nav.navigate(Routes.DOWNLOAD)
    }

    /** Titre TMDB (Pour toi, Découvrir) : sa fiche s'il est déjà là, sinon la feuille « Télécharger ». */
    fun openTmdb(item: TmdbItem) {
        if (!item.inLibrary) return openDownload(DownloadTarget.of(item))
        scope.launch {
            val found = runCatching {
                if (item.type == "movie") app.repository.allLibrary("movie").firstOrNull { it.tmdbId == item.tmdbId }
                else app.repository.allLibrary("series").firstOrNull { it.tmdbTvId == item.tmdbId }
            }.getOrNull()
            if (found != null) openItem(found) else openDownload(DownloadTarget.of(item))
        }
    }

    fun openLookup(item: LookupItem) {
        val arrId = item.arrId
        when {
            item.inLibrary && arrId != null && item.type == "movie" -> nav.navigate(Routes.movie(arrId.toString()))
            item.inLibrary && arrId != null -> nav.navigate(Routes.show(arrId.toString()))
            else -> openDownload(DownloadTarget.of(item))
        }
    }

    fun go(route: String) {
        when (route) {
            "movies" -> nav.navigate(Routes.library("movie"))
            "series" -> nav.navigate(Routes.library("series"))
            "discover" -> nav.navigate(Routes.DISCOVER)
            "search" -> nav.navigate(Routes.search(voice = false))
            "settings" -> nav.navigate(Routes.SETTINGS)
            "tonight" -> nav.navigate(Routes.TONIGHT)
            "apps" -> nav.navigate(Routes.APPS)
            "queue" -> nav.navigate(Routes.DOWNLOADS)
            "board" -> nav.navigate(Routes.BOARD)
            "profiles" -> nav.navigate(Routes.PROFILES)
        }
    }

    /**
     * « Prêt à regarder » / « Lire sur la TV » → ce qu'il faut lancer, avec
     * la position de reprise partagée si on reprend.
     */
    suspend fun announced(a: PlayAnnounce): PlayRequest? {
        val id = a.externalId ?: return null
        val season = a.season ?: 0
        val episode = a.episode ?: 0
        val start = if (!a.resume) {
            0
        } else {
            runCatching {
                if (a.isEpisode) app.repository.playEpisode(id, season, episode) else app.repository.playMovie(id, fresh = true)
            }.getOrNull()?.resume?.takeIf { !it.watched }?.position ?: 0
        }
        return PlayRequest(
            kind = if (a.isEpisode) "episode" else "movie",
            id = id,
            season = season,
            episode = episode,
            radarrId = a.arrId?.toString()?.takeIf { !a.isEpisode && a.serviceType != "sonarr" },
            sonarrId = a.arrId?.toString()?.takeIf { a.isEpisode && a.serviceType == "sonarr" },
            startSeconds = start,
        )
    }

    fun playAnnounced(a: PlayAnnounce) {
        scope.launch {
            val request = announced(a)
            if (request == null) {
                Toast.makeText(context, "Titre introuvable : lance-le depuis sa fiche", Toast.LENGTH_LONG).show()
            } else {
                nav.navigate(Routes.play(request))
            }
        }
    }

    // « Lire sur la TV » depuis la web app
    LaunchedEffect(Unit) { app.events.playRequests.collect { playAnnounced(it) } }

    // Intro animée au lancement (une fois), seulement vers l'accueil
    var showIntro by remember { mutableStateOf(!app.introSeen && start == Routes.PROFILES && Motion.enabled) }
    val skipIntro by intro.skip.collectAsStateWithLifecycle()
    LaunchedEffect(showIntro) { intro.active.value = showIntro }

    // Passage d'un écran à l'autre : fondu court (le fondu par défaut dure
    // 700 ms, ce qui donnait l'impression d'une appli lente)
    Box(Modifier.fillMaxSize()) {
    NavHost(
        navController = nav,
        startDestination = start,
        enterTransition = { fadeIn(tween(ENTER_MS)) },
        exitTransition = { fadeOut(tween(EXIT_MS)) },
        popEnterTransition = { fadeIn(tween(ENTER_MS)) },
        popExitTransition = { fadeOut(tween(EXIT_MS)) },
    ) {
        composable(Routes.SERVER) {
            ServerScreen(app.prefs) { nav.navigate(Routes.PAIR) { popUpTo(0) } }
        }
        composable(Routes.PAIR) {
            PairScreen(
                prefs = app.prefs,
                repository = app.repository,
                onPaired = { nav.navigate(Routes.PROFILES) { popUpTo(0) } },
                onChangeServer = { nav.navigate(Routes.SERVER) { popUpTo(0) } },
            )
        }
        composable(Routes.PROFILES) {
            ProfilesScreen(
                repository = app.repository,
                current = viewer,
                onHasProfiles = { app.hasProfiles = it },
                onChosen = { chosen ->
                    scope.launch {
                        // Autre spectateur : son vu / reprise, son « Pour toi », ses demandes
                        if (chosen?.id != app.prefs.profileId) {
                            app.prefs.setProfile(chosen)
                            app.repository.forgetViewer()
                        }
                        nav.navigate(Routes.HOME) { popUpTo(0) }
                    }
                },
            )
        }
        composable(Routes.HOME) {
            val viewModel: HomeViewModel = viewModel { HomeViewModel(app.repository) }
            HomeScreen(
                viewModel = viewModel,
                api = app.api,
                actions = HomeActions(
                    open = ::openItem,
                    openMovieId = { nav.navigate(Routes.movie(it.toString())) },
                    openSeriesId = { nav.navigate(Routes.show(it.toString())) },
                    resume = { entry -> nav.navigate(Routes.play(resumeRequest(entry))) },
                    request = ::openTmdb,
                    go = ::go,
                    prefetch = prefetcher::focus,
                    viewer = if (app.hasProfiles) viewer ?: FamilyProfile(name = "Famille", isDefault = true) else null,
                ),
            )
        }
        composable(Routes.LIBRARY, arguments = listOf(navArgument("type") { type = NavType.StringType })) { entry ->
            LibraryScreen(entry.arguments?.getString("type") ?: "movie", app.repository, app.api, ::openItem, prefetcher::focus)
        }
        composable(Routes.DISCOVER) {
            DiscoverScreen(app.repository, ::openTmdb)
        }
        composable(Routes.SEARCH, arguments = listOf(navArgument("voice") { type = NavType.BoolType; defaultValue = false })) { entry ->
            SearchScreen(
                repository = app.repository,
                absolute = app.api::absolute,
                startWithVoice = entry.arguments?.getBoolean("voice") == true,
                onOpen = ::openItem,
                onOpenTracked = ::openLookup,
                onRequest = ::openLookup,
            )
        }
        composable(Routes.DOWNLOAD) {
            val target = remember { app.pendingDownload }
            if (target == null) {
                MessageScreen("Rien à télécharger", null, "Retour") { nav.popBackStack() }
            } else {
                DownloadScreen(target, app.repository, app.api::absolute) { nav.popBackStack() }
            }
        }
        composable(
            Routes.MOVIE,
            arguments = listOf(
                navArgument("radarrId") { type = NavType.StringType },
                navArgument("tmdb") { type = NavType.LongType; defaultValue = -1L },
            ),
        ) { entry ->
            val radarrId = entry.arguments?.getString("radarrId").orEmpty()
            MovieScreen(
                radarrId = radarrId,
                tmdbId = entry.arguments?.getLong("tmdb")?.takeIf { it > 0 },
                repository = app.repository,
                api = app.api,
                onPlay = { movie, start ->
                    val tmdb = movie.tmdbId
                    if (tmdb == null) {
                        Toast.makeText(context, "Film sans identifiant TMDB", Toast.LENGTH_SHORT).show()
                    } else {
                        nav.navigate(Routes.play(PlayRequest("movie", tmdb, radarrId = radarrId, startSeconds = start)))
                    }
                },
                onDownload = { openDownload(DownloadTarget.of(it)) },
            )
        }
        composable(Routes.SHOW, arguments = listOf(navArgument("sonarrId") { type = NavType.StringType })) { entry ->
            val sonarrId = entry.arguments?.getString("sonarrId").orEmpty()
            SeriesScreen(
                sonarrId = sonarrId,
                repository = app.repository,
                absolute = app.api::absolute,
                onPlay = { series, season, episode, start ->
                    val tvdb = series.tvdbId
                    if (tvdb == null) {
                        Toast.makeText(context, "Série sans identifiant TVDB", Toast.LENGTH_SHORT).show()
                    } else {
                        nav.navigate(Routes.play(PlayRequest("episode", tvdb, season, episode, sonarrId = sonarrId, startSeconds = start)))
                    }
                },
                onDownload = { openDownload(DownloadTarget.of(it)) },
            )
        }
        composable(
            Routes.PLAY,
            arguments = listOf(
                navArgument("kind") { type = NavType.StringType },
                navArgument("id") { type = NavType.LongType },
                navArgument("season") { type = NavType.IntType },
                navArgument("episode") { type = NavType.IntType },
                navArgument("start") { type = NavType.IntType },
                navArgument("radarr") { type = NavType.StringType; defaultValue = "" },
                navArgument("sonarr") { type = NavType.StringType; defaultValue = "" },
            ),
        ) { entry ->
            val args = requireNotNull(entry.arguments)
            val request = PlayRequest(
                kind = args.getString("kind").orEmpty(),
                id = args.getLong("id"),
                season = args.getInt("season"),
                episode = args.getInt("episode"),
                radarrId = args.getString("radarr")?.takeIf { it.isNotBlank() },
                sonarrId = args.getString("sonarr")?.takeIf { it.isNotBlank() },
                startSeconds = args.getInt("start"),
            )
            PlayerScreen(
                request = request,
                app = app,
                onExit = { nav.popBackStack() },
                // Épisode suivant : remplace le lecteur (Retour ramène à l'écran Série)
                onPlayNext = { next ->
                    nav.navigate(Routes.play(next)) {
                        popUpTo(Routes.PLAY) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.DOWNLOADS) {
            DownloadsScreen(
                repository = app.repository,
                absolute = app.api::absolute,
                onOpenMovie = { nav.navigate(Routes.movie(it.toString())) },
                onOpenSeries = { nav.navigate(Routes.show(it.toString())) },
            )
        }
        composable(Routes.BOARD) {
            DashboardScreen(app.repository, app.api::absolute, ::openItem, onDownloads = { nav.navigate(Routes.DOWNLOADS) })
        }
        composable(Routes.APPS) {
            AppsScreen()
        }
        composable(Routes.TONIGHT) {
            TonightScreen(app.repository, app.api::absolute) { row -> nav.navigate(Routes.play(tonightRequest(row))) }
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

    // Par-dessus tous les écrans : bulles, « Prêt à regarder », caméra
    if (paired) EventOverlays(app.events, app.api::absolute, onWatch = ::playAnnounced)

    if (showIntro) {
        IntroAnimation(BuildConfig.VERSION_NAME, skip = skipIntro) {
            if (showIntro) {
                showIntro = false
                app.introSeen = true
            }
        }
    }
    }
}

/** « Ce soir » : reprise du titre commencé, ou film depuis le début. */
private fun tonightRequest(row: TonightLogic.Row): PlayRequest {
    val s = row.state
    if (s == null) return PlayRequest("movie", row.item?.tmdbId ?: 0, radarrId = row.item?.externalId)
    val episode = s.mediaType == "episode"
    return PlayRequest(
        kind = if (episode) "episode" else "movie",
        id = s.id.toLongOrNull() ?: 0,
        season = s.season ?: 0,
        episode = s.episode ?: 0,
        radarrId = row.item?.externalId?.takeIf { !episode },
        sonarrId = row.item?.externalId?.takeIf { episode },
        startSeconds = s.position,
    )
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
        sonarrId = entry.item?.externalId?.takeIf { entry.isEpisode },
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
