package fr.arrmada.app

import android.graphics.drawable.ColorDrawable
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.TrackGroup
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.media3.common.Tracks
import coil.Coil
import coil.ImageLoader
import coil.decode.DataSource
import coil.intercept.Interceptor
import coil.request.ImageResult
import coil.request.SuccessResult
import com.github.takahirom.roborazzi.captureRoboImage
import fr.arrmada.app.data.BecauseGroup
import fr.arrmada.app.data.CalendarEntry
import fr.arrmada.app.data.DownloadTarget
import fr.arrmada.app.data.EpisodeInfo
import fr.arrmada.app.data.JellyfinEpisode
import fr.arrmada.app.data.LookupItem
import fr.arrmada.app.data.Recommendations
import fr.arrmada.app.data.SeasonCount
import fr.arrmada.app.data.SeasonEpisode
import fr.arrmada.app.data.SeasonInfo
import fr.arrmada.app.data.SeasonsInfo
import fr.arrmada.app.data.SeriesDetail
import fr.arrmada.app.data.SeriesLogic
import fr.arrmada.app.data.Chapter
import fr.arrmada.app.data.FileInfo
import fr.arrmada.app.data.Images
import fr.arrmada.app.data.LibraryItem
import fr.arrmada.app.data.MovieDetail
import fr.arrmada.app.data.PairStart
import fr.arrmada.app.data.Person
import fr.arrmada.app.data.PlayInfo
import fr.arrmada.app.data.Ratings
import fr.arrmada.app.data.Resume
import fr.arrmada.app.data.ResumeEntry
import fr.arrmada.app.data.TmdbItem
import fr.arrmada.app.data.WatchState
import fr.arrmada.app.ui.components.Motion
import fr.arrmada.app.ui.detail.MovieContent
import fr.arrmada.app.ui.detail.SeriesContent
import fr.arrmada.app.ui.home.DiscoverContent
import fr.arrmada.app.ui.home.HomeActions
import fr.arrmada.app.ui.home.HomeContent
import fr.arrmada.app.ui.home.HomeState
import fr.arrmada.app.ui.home.LibraryContent
import fr.arrmada.app.ui.player.PauseMenu
import fr.arrmada.app.ui.player.PlayRequest
import fr.arrmada.app.ui.player.SkipButton
import fr.arrmada.app.ui.player.UpNext
import fr.arrmada.app.ui.player.UpNextCard
import fr.arrmada.app.ui.player.toMeta
import fr.arrmada.app.ui.request.DownloadContent
import fr.arrmada.app.ui.request.SearchContent
import fr.arrmada.app.ui.request.SearchState
import fr.arrmada.app.ui.setup.PairContent
import fr.arrmada.app.ui.theme.ArrMadaTheme
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import kotlin.math.abs

/**
 * Captures d'écran de l'appli, sans appareil ni émulateur : Robolectric
 * simule Android sur la machine de build, Roborazzi enregistre chaque écran
 * en PNG (build/outputs/roborazzi/). La CI les publie pour relecture.
 *
 * Écran simulé : TV 1080p (960 × 540 dp, densité ×2 → 1920 × 1080 pixels).
 * Les images (affiches, fonds) sont remplacées par des aplats de couleur :
 * pas de réseau pendant les tests.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w960dp-h540dp-land-television-xhdpi")
class ScreenshotTest {

    @Before
    fun setUp() {
        Motion.enabled = false
        // Images factices : un aplat de couleur stable par adresse
        Coil.setImageLoader(
            ImageLoader.Builder(RuntimeEnvironment.getApplication())
                .components { add(FakeImages) }
                .build()
        )
    }

    private object FakeImages : Interceptor {
        private val palette = intArrayOf(0xFF2B4C7E.toInt(), 0xFF6B3A5B.toInt(), 0xFF2E6B5E.toInt(), 0xFF7A5C2E.toInt(), 0xFF3F3F7F.toInt(), 0xFF5E2E2E.toInt())
        override suspend fun intercept(chain: Interceptor.Chain): ImageResult = SuccessResult(
            drawable = ColorDrawable(palette[abs(chain.request.data.toString().hashCode()) % palette.size]),
            request = chain.request,
            dataSource = DataSource.MEMORY,
        )
    }

    private fun shot(name: String) = "build/outputs/roborazzi/$name.png"

    private val noAbsolute: (String?) -> String? = { it }

    // ── Données factices ──

    private fun movie(id: Int, title: String, year: Int, logo: Boolean = false) = LibraryItem(
        externalId = id.toString(), tmdbId = 1000L + id, title = title, type = "movie", year = year,
        genres = listOf("Science-fiction", "Aventure"), posterUrl = "https://img/p$id", fanartUrl = "https://img/f$id",
        clearlogoUrl = if (logo) "https://img/l$id" else null, hasFile = true, rating = 7.8, runtime = 155,
        overview = "Paul Atréides, un jeune homme brillant au destin hors du commun, doit se rendre sur la planète la plus dangereuse de l’univers afin d’assurer l’avenir de sa famille et de son peuple.",
    )

    private val titles = listOf("Dune", "Oppenheimer", "Interstellar", "Blade Runner 2049", "Arrival", "Tenet", "Mad Max: Fury Road", "The Batman", "Gravity", "Prisoners")

    private val dune = MovieDetail(
        id = 1, title = "Dune", year = 2021, runtime = 155, certification = "Tous publics",
        genres = listOf("Science-fiction", "Aventure", "Drame"), tmdbId = 438631, trailerId = "n9xhJrPXop4", hasFile = true,
        overview = "Paul Atréides, un jeune homme brillant au destin hors du commun, doit se rendre sur la planète la plus dangereuse de l’univers afin d’assurer l’avenir de sa famille et de son peuple. Alors que des forces maléfiques se disputent le contrôle de la plus précieuse ressource qui soit, seuls ceux qui parviendront à dominer leur peur pourront survivre.",
        ratings = Ratings(tmdb = 7.8, imdb = 8.0, rottenTomatoes = 83.0),
        images = Images(fanart = "https://img/fanart-dune"),
        file = FileInfo(quality = "Bluray-2160p", resolution = JsonPrimitive(2160), dynamicRangeType = "DV HDR10", audioCodec = "TrueHD Atmos", audioChannels = 7.1),
        cast = listOf(
            "Timothée Chalamet" to "Paul Atréides", "Rebecca Ferguson" to "Lady Jessica", "Oscar Isaac" to "Duc Leto",
            "Zendaya" to "Chani", "Jason Momoa" to "Duncan Idaho", "Josh Brolin" to "Gurney Halleck",
            "Stellan Skarsgård" to "Baron Harkonnen", "Javier Bardem" to "Stilgar",
        ).map { (name, role) -> Person(name = name, character = role, photo = "https://img/$name") },
        crew = listOf(Person(name = "Denis Villeneuve", job = "Director")),
    )

    private val play = PlayInfo(
        status = "ok", itemId = "0123456789abcdef0123456789abcdef", title = "Dune", duration = 9300,
        stream = "/api/tv/stream/0123456789abcdef0123456789abcdef",
        chapters = listOf("Ouverture", "Caladan", "L’épreuve du Gom Jabbar", "Arrakis", "La moissonneuse", "Trahison", "Le désert", "Les Fremen")
            .mapIndexed { i, name -> Chapter(index = i, name = name, start = i * 1150.0, image = "https://img/ch$i") },
        resume = Resume(position = 2530, watched = false),
    )

    // ── Écrans ──

    @Test
    fun accueil() {
        val state = HomeState(
            loading = false,
            resume = listOf(
                ResumeEntry(WatchState(mediaType = "movie", id = "1001", position = 2530, total = 9300), movie(1, "Dune", 2021)),
                ResumeEntry(WatchState(mediaType = "episode", idType = "tvdb", id = "305288", season = 4, episode = 3, title = "La traque", position = 1200, total = 3000), movie(11, "Stranger Things", 2016).copy(type = "series")),
                ResumeEntry(WatchState(mediaType = "movie", id = "1003", position = 5000, total = 10140), movie(3, "Interstellar", 2014)),
            ),
            recent = titles.mapIndexed { i, t -> movie(i + 1, t, 2010 + i) },
            forYou = titles.take(6).mapIndexed { i, t -> TmdbItem(tmdbId = 5000L + i, title = "$t 2", posterUrl = "https://img/r$i", year = "2026") },
            upcoming = titles.take(5).mapIndexed { i, t -> CalendarEntry(id = "c$i", title = t, label = "2026", posterUrl = "https://img/u$i", airDate = "2026-11-0${i + 1}T00:00:00Z") },
        )
        captureRoboImage(shot("01-accueil")) {
            ArrMadaTheme { HomeContent(state, noAbsolute, {}, HomeActions()) }
        }
    }

    @Test
    fun fiche() {
        captureRoboImage(shot("02-fiche-film")) {
            ArrMadaTheme { MovieContent(dune, play, noAbsolute) { _, _ -> } }
        }
    }

    @Test
    fun menuPause() {
        captureRoboImage(shot("03-menu-pause")) {
            ArrMadaTheme {
                PauseMenu(
                    info = play,
                    meta = dune.toMeta(),
                    position = 2530_000L,
                    duration = 9300_000L,
                    tracks = Tracks.EMPTY,
                    absolute = noAbsolute,
                    onResume = {},
                    onSeek = {},
                    onSelectTrack = { _, _ -> },
                )
            }
        }
    }

    @Test
    fun menuPauseAudio() {
        fun audio(mime: String, lang: String, channels: Int, label: String? = null) =
            Format.Builder().setSampleMimeType(mime).setLanguage(lang).setChannelCount(channels).setLabel(label).build()
        fun text(mime: String, lang: String, forced: Boolean = false) =
            Format.Builder().setSampleMimeType(mime).setLanguage(lang)
                .setSelectionFlags(if (forced) C.SELECTION_FLAG_FORCED else 0).build()
        val tracks = Tracks(
            listOf(
                Tracks.Group(
                    TrackGroup(
                        audio(MimeTypes.AUDIO_TRUEHD, "en", 8, "Dolby Atmos"),
                        audio(MimeTypes.AUDIO_E_AC3, "fr", 6, "VFF"),
                        audio(MimeTypes.AUDIO_DTS_HD, "fr", 8, "VFQ"),
                    ),
                    false,
                    intArrayOf(C.FORMAT_HANDLED, C.FORMAT_HANDLED, C.FORMAT_UNSUPPORTED_SUBTYPE),
                    booleanArrayOf(false, true, false),
                ),
                Tracks.Group(
                    TrackGroup(text(MimeTypes.APPLICATION_PGS, "fr", forced = true), text(MimeTypes.APPLICATION_SUBRIP, "en")),
                    false,
                    intArrayOf(C.FORMAT_HANDLED, C.FORMAT_HANDLED),
                    booleanArrayOf(true, false),
                ),
            )
        )
        captureRoboImage(shot("05-menu-pause-audio")) {
            ArrMadaTheme {
                PauseMenu(
                    info = play,
                    meta = dune.toMeta(),
                    position = 2530_000L,
                    duration = 9300_000L,
                    tracks = tracks,
                    absolute = noAbsolute,
                    onResume = {},
                    onSeek = {},
                    onSelectTrack = { _, _ -> },
                    initialTab = "Audio",
                )
            }
        }
    }

    @Test
    fun grilleFilms() {
        val items = (titles + titles.map { "$it II" } + titles.map { "$it III" }).mapIndexed { i, t -> movie(i + 1, t, 2000 + i % 25).copy(added = "2026-10-${10 + i % 9}") }
        captureRoboImage(shot("06-grille-films")) {
            ArrMadaTheme { LibraryContent("Films", items, noAbsolute) {} }
        }
    }

    @Test
    fun appairage() {
        val pairing = PairStart(deviceCode = "x".repeat(20), userCode = "K7M4QX", qrUrl = "/api/devices/pair/qr/K7M4QX.png", expiresIn = 600)
        captureRoboImage(shot("07-appairage")) {
            ArrMadaTheme { PairContent(pairing, null, 540, "https://img/qr", {}, {}) }
        }
    }

    // ── Phase 2 ──

    private val expanse = SeriesDetail(
        id = 42, title = "The Expanse", year = 2015, network = "Amazon", tvdbId = 280619, status = "ended",
        genres = listOf("Science-fiction", "Drame"),
        overview = "Dans un futur où l’humanité a colonisé le système solaire, une inspectrice et le second d’un vaisseau de transport de glace se retrouvent mêlés à une conspiration qui menace la paix.",
        images = Images(fanart = "https://img/expanse"),
        seasons = (1..4).map { s ->
            SeasonInfo(
                seasonNumber = s,
                episodes = (1..10).map { e ->
                    EpisodeInfo(
                        seasonNumber = s, episodeNumber = e, title = listOf("Dulcinea", "The Big Empty", "Remember the Cant", "CQB", "Back to the Butcher", "Rock Bottom", "Windmills", "Salvage", "Critical Mass", "Leviathan Wakes")[e - 1],
                        overview = "Holden et l’équipage du Canterbury répondent à un signal de détresse.",
                        airDate = if (s == 4 && e > 6) "2099-01-0$e" else "2016-0${(e % 9) + 1}-10", hasFile = !(s == 4 && e > 5),
                    )
                },
            )
        },
    )

    @Test
    fun serie() {
        val states = SeriesLogic.statesBySeries(
            (1..10).map { WatchState(mediaType = "episode", idType = "tvdb", id = "280619", season = 2, episode = it, watched = it < 4) } +
                WatchState(mediaType = "episode", idType = "tvdb", id = "280619", season = 2, episode = 4, position = 1300, total = 2700, updatedAt = "2026-10-20T20:00:00+00:00"),
            280619,
        )
        val season = expanse.seasons.first { it.seasonNumber == 2 }
        val jellyfin = (1..10).map { JellyfinEpisode(season = 2, episode = it, itemId = "x$it", image = "https://img/ep$it", runtime = 2700) }
        captureRoboImage(shot("08-serie")) {
            ArrMadaTheme {
                SeriesContent(
                    series = expanse, season = 2, rows = SeriesLogic.rows(season, jellyfin, states),
                    nextUp = SeriesLogic.nextUp(expanse, states), seasonSubtitle = { "${it.episodes.size} épisodes" },
                    absolute = noAbsolute, onSeason = {}, onPlay = { _, _ -> }, onMissing = {}, onMark = { _, _ -> }, onDownload = {},
                )
            }
        }
    }

    @Test
    fun serieManquants() {
        val season = expanse.seasons.first { it.seasonNumber == 4 }
        captureRoboImage(shot("09-serie-manquants")) {
            ArrMadaTheme {
                SeriesContent(
                    series = expanse, season = 4, rows = SeriesLogic.rows(season, emptyList(), emptyMap()),
                    nextUp = null, seasonSubtitle = { "6/10 sur le NAS" },
                    absolute = noAbsolute, onSeason = {}, onPlay = { _, _ -> }, onMissing = {}, onMark = { _, _ -> }, onDownload = {},
                )
            }
        }
    }

    @Test
    fun recherche() {
        val state = SearchState(
            query = "dune",
            library = listOf(movie(1, "Dune", 2021), movie(2, "Dune : Deuxième partie", 2024)),
            toRequest = listOf(
                LookupItem(title = "Dune", year = 1984, type = "movie", tmdbId = 841, posterUrl = "https://img/d84"),
                LookupItem(title = "Dune : Prophecy", year = 2024, type = "series", tvdbId = 389597, posterUrl = "https://img/dp"),
                LookupItem(title = "Les Enfants de Dune", year = 2003, type = "series", tvdbId = 72187, posterUrl = "https://img/ed"),
            ),
        )
        captureRoboImage(shot("10-recherche")) {
            ArrMadaTheme { SearchContent("dune", {}, state, noAbsolute, {}, {}, {}, {}) }
        }
    }

    @Test
    fun telechargerSerie() {
        val target = DownloadTarget(kind = "series", title = "Severance", year = 2022, tvdbId = 371980, overview = "Les employés de Lumon ont accepté une procédure qui sépare leurs souvenirs professionnels de leur vie privée.", poster = "https://img/sev", fanart = "https://img/sevf")
        val info = SeasonsInfo(
            status = "ok", season = 2, source = "sonarr",
            seasons = listOf(SeasonCount(1, 9, 9, 9), SeasonCount(2, 10, 10, 4)),
            episodes = (1..10).map { SeasonEpisode(season = 2, number = it, title = "Épisode $it", hasFile = it <= 4, runtime = 52, aired = it <= 8, airDate = "2026-11-0${it % 9 + 1}") },
        )
        captureRoboImage(shot("11-telecharger-serie")) {
            ArrMadaTheme { DownloadContent(target, info, null, { info }, {}, false, noAbsolute, {}, {}) }
        }
    }

    @Test
    fun telechargerFilm() {
        val target = DownloadTarget(kind = "movie", title = "Dune : Deuxième partie", year = 2024, tmdbId = 693134, overview = "Paul Atréides s’unit à Chani et aux Fremen pour mener la révolte.", poster = "https://img/d2", fanart = "https://img/d2f")
        captureRoboImage(shot("12-telecharger-film")) {
            ArrMadaTheme { DownloadContent(target, null, null, { null }, {}, false, noAbsolute, {}, {}) }
        }
    }

    @Test
    fun lecteurIntroEtSuivant() {
        val next = UpNext(PlayRequest("episode", 280619, 2, 5), "S02E05", "Home", "https://img/next")
        captureRoboImage(shot("13-lecteur-intro-suivant")) {
            ArrMadaTheme {
                Box(Modifier.fillMaxSize().background(Color(0xFF203040))) {
                    Column(Modifier.align(Alignment.BottomEnd).padding(end = 48.dp, bottom = 48.dp)) {
                        SkipButton("Passer l’intro")
                        Box(Modifier.padding(top = 24.dp)) { UpNextCard(next, 7) { it } }
                    }
                }
            }
        }
    }

    @Test
    fun decouvrir() {
        val recos = Recommendations(
            trendingMovies = titles.mapIndexed { i, t -> TmdbItem(tmdbId = 7000L + i, title = t, posterUrl = "https://img/tm$i", backdropUrl = "https://img/tb$i", year = "2026", rating = 7.5, overview = "Un film du moment.") },
            trendingSeries = titles.take(6).mapIndexed { i, t -> TmdbItem(tmdbId = 8000L + i, title = "$t, la série", type = "series", posterUrl = "https://img/ts$i") },
            becauseYouHave = listOf(BecauseGroup("Dune", titles.take(4).mapIndexed { i, t -> TmdbItem(tmdbId = 9000L + i, title = t, posterUrl = "https://img/b$i") })),
        )
        captureRoboImage(shot("14-decouvrir")) {
            ArrMadaTheme { DiscoverContent(recos) {} }
        }
    }
}
