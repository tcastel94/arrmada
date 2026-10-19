package fr.arrmada.app

import android.graphics.drawable.ColorDrawable
import androidx.media3.common.Tracks
import coil.Coil
import coil.ImageLoader
import coil.decode.DataSource
import coil.intercept.Interceptor
import coil.request.ImageResult
import coil.request.SuccessResult
import com.github.takahirom.roborazzi.captureRoboImage
import fr.arrmada.app.data.CalendarEntry
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
import fr.arrmada.app.ui.home.HomeContent
import fr.arrmada.app.ui.home.HomeState
import fr.arrmada.app.ui.player.PauseMenu
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
            ArrMadaTheme { HomeContent(state, noAbsolute, {}, {}, {}, {}, {}, {}) }
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
                    detail = dune,
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
    fun appairage() {
        val pairing = PairStart(deviceCode = "x".repeat(20), userCode = "K7M4QX", qrUrl = "/api/devices/pair/qr/K7M4QX.png", expiresIn = 600)
        captureRoboImage(shot("04-appairage")) {
            ArrMadaTheme { PairContent(pairing, null, 540, "https://img/qr", {}, {}) }
        }
    }
}
