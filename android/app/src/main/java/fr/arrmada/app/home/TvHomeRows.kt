package fr.arrmada.app.home

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.database.Cursor
import android.net.Uri
import android.os.Build
import android.os.ParcelFileDescriptor
import android.util.Log
import androidx.core.content.ContextCompat
import androidx.core.graphics.drawable.toBitmap
import androidx.tvprovider.media.tv.PreviewChannel
import androidx.tvprovider.media.tv.PreviewChannelHelper
import androidx.tvprovider.media.tv.PreviewProgram
import androidx.tvprovider.media.tv.TvContractCompat
import androidx.tvprovider.media.tv.WatchNextProgram
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import fr.arrmada.app.ArrMadaApplication
import fr.arrmada.app.MainActivity
import fr.arrmada.app.R
import fr.arrmada.app.data.HomeCard
import fr.arrmada.app.data.HomeRowsLogic
import fr.arrmada.app.data.ImageSizes
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.Request
import java.io.File
import java.io.FileNotFoundException
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

private const val TAG = "ArrMadaHomeRows"

/**
 * Rangées d'ArrMada sur l'écran d'accueil d'Android TV (celui de la Shield),
 * sans remplacer cet accueil :
 *
 *  - **À suivre** (rangée du système) : les films et épisodes commencés, avec
 *    leur barre de progression ; un clic reprend la lecture dans ArrMada ;
 *  - **chaîne « ArrMada »** : les derniers ajouts ; un clic ouvre la fiche.
 *
 * Le lanceur lit ces cartes dans une base du système (le « TvProvider »),
 * comme un tableau de bord lit une table qu'un collecteur alimente : ArrMada
 * écrit, le lanceur affiche. Les affiches sont téléchargées ici (avec le
 * jeton d'appareil si elles viennent du serveur ArrMada) puis servies au
 * lanceur par [HomeArtProvider].
 */
class TvHomeRows(private val context: Context) {

    private val helper = PreviewChannelHelper(context)
    private val resolver get() = context.contentResolver

    /** Remplace le contenu des deux rangées par [resume] et [recent] (cartes inchangées : mises à jour). */
    suspend fun sync(resume: List<HomeCard>, recent: List<HomeCard>) = withContext(Dispatchers.IO) {
        val art = ArtCache(context)
        val posters = art.fetch((resume + recent).mapNotNull { it.poster })
        runCatching { syncWatchNext(resume, posters) }.onFailure { Log.w(TAG, "À suivre", it) }
        runCatching { syncChannel(recent, posters) }.onFailure { Log.w(TAG, "Chaîne ArrMada", it) }
        art.keepOnly(posters.values.toSet())
    }

    /** Option coupée (Réglages) : retire la chaîne et les cartes « À suivre » d'ArrMada. */
    suspend fun clear() = withContext(Dispatchers.IO) {
        runCatching { ownWatchNext().keys.forEach { deleteWatchNext(it) } }
        runCatching { findChannel()?.let { helper.deletePreviewChannel(it.id) } }
        ArtCache(context).keepOnly(emptySet())
    }

    // ── À suivre ──

    private fun syncWatchNext(cards: List<HomeCard>, posters: Map<String, String>) {
        val existing = ownWatchNext() // identifiant système → clé ArrMada
        val wanted = cards.associateBy { it.key }
        existing.filterValues { it !in wanted }.keys.forEach { deleteWatchNext(it) }
        val byKey = existing.entries.associate { (id, key) -> key to id }
        cards.forEach { card ->
            val program = WatchNextProgram.Builder()
                .setWatchNextType(TvContractCompat.WatchNextPrograms.WATCH_NEXT_TYPE_CONTINUE)
                .setLastEngagementTimeUtcMillis(card.lastWatchedMs.takeIf { it > 0 } ?: System.currentTimeMillis())
                .setType(if (card.kind == "episode") TvContractCompat.PreviewProgramColumns.TYPE_TV_EPISODE else TvContractCompat.PreviewProgramColumns.TYPE_MOVIE)
                .setTitle(card.title)
                .apply {
                    card.episodeTitle?.let { setEpisodeTitle(it) }
                    card.season?.let { setSeasonNumber(it) }
                    card.episode?.let { setEpisodeNumber(it) }
                    card.description?.let { setDescription(it) }
                    posters[card.poster]?.let {
                        setPosterArtUri(Uri.parse(it))
                        setPosterArtAspectRatio(TvContractCompat.PreviewProgramColumns.ASPECT_RATIO_2_3)
                    }
                    if (card.durationMs > 0) setDurationMillis(card.durationMs.toInt())
                }
                .setLastPlaybackPositionMillis(card.positionMs.toInt())
                .setIntentUri(intentUri(card.link))
                .setInternalProviderId(card.key)
                .build()
            val id = byKey[card.key]
            if (id != null) helper.updateWatchNextProgram(program, id) else helper.publishWatchNextProgram(program)
        }
    }

    /** Cartes « À suivre » posées par ArrMada (le système ne renvoie que celles de l'appli). */
    private fun ownWatchNext(): Map<Long, String> =
        readKeys(TvContractCompat.WatchNextPrograms.CONTENT_URI).filterValues { it.startsWith("resume:") }

    private fun deleteWatchNext(id: Long) {
        resolver.delete(TvContractCompat.buildWatchNextProgramUri(id), null, null)
    }

    // ── Chaîne « ArrMada » ──

    private fun syncChannel(cards: List<HomeCard>, posters: Map<String, String>) {
        val channelId = findChannel()?.id ?: publishChannel()
        val existing = readKeys(TvContractCompat.buildPreviewProgramsUriForChannel(channelId))
        val wanted = cards.map { it.key }.toSet()
        existing.filterValues { it !in wanted }.keys.forEach { helper.deletePreviewProgram(it) }
        val byKey = existing.entries.associate { (id, key) -> key to id }
        cards.forEachIndexed { index, card ->
            val program = PreviewProgram.Builder()
                .setChannelId(channelId)
                .setType(if (card.kind == "movie") TvContractCompat.PreviewProgramColumns.TYPE_MOVIE else TvContractCompat.PreviewProgramColumns.TYPE_TV_SERIES)
                .setTitle(card.title)
                .apply {
                    card.description?.let { setDescription(it) }
                    posters[card.poster]?.let {
                        setPosterArtUri(Uri.parse(it))
                        setPosterArtAspectRatio(TvContractCompat.PreviewProgramColumns.ASPECT_RATIO_2_3)
                    }
                }
                .setWeight(cards.size - index) // ordre de la rangée : le plus récent d'abord
                .setIntentUri(intentUri(card.link))
                .setInternalProviderId(card.key)
                .build()
            val id = byKey[card.key]
            if (id != null) helper.updatePreviewProgram(id, program) else helper.publishPreviewProgram(program)
        }
    }

    private fun findChannel(): PreviewChannel? =
        helper.allChannels.firstOrNull { it.internalProviderId == CHANNEL_KEY }

    /** Première chaîne de l'appli : « par défaut », donc affichée sans demander à l'utilisateur. */
    private fun publishChannel(): Long {
        val logo = ContextCompat.getDrawable(context, R.mipmap.ic_launcher)!!.toBitmap(160, 160)
        val channel = PreviewChannel.Builder()
            .setDisplayName("ArrMada · Ajouts récents")
            .setDescription("Les derniers films et séries arrivés sur le NAS")
            .setAppLinkIntentUri(intentUri("${HomeRowsLogic.SCHEME}://home"))
            .setInternalProviderId(CHANNEL_KEY)
            .setLogo(logo)
            .build()
        return helper.publishDefaultChannel(channel)
    }

    // ── Outils ──

    /** Lignes (identifiant, clé ArrMada) d'une table du TvProvider. */
    private fun readKeys(uri: Uri): Map<Long, String> {
        val keys = mutableMapOf<Long, String>()
        resolver.query(uri, arrayOf(COLUMN_ID, COLUMN_KEY), null, null, null)?.use { cursor: Cursor ->
            while (cursor.moveToNext()) {
                val key = cursor.getString(1) ?: continue
                keys[cursor.getLong(0)] = key
            }
        }
        return keys
    }

    /**
     * Lien d'une carte : intent adressé à ArrMada par son nom (pas par un
     * filtre d'URL), pour que la version normale et la version de test,
     * installées côte à côte, ne se répondent pas l'une à la place de l'autre.
     */
    private fun intentUri(link: String): Uri =
        Uri.parse(
            Intent(context, MainActivity::class.java)
                .setAction(Intent.ACTION_VIEW)
                .setData(Uri.parse(link))
                .toUri(Intent.URI_INTENT_SCHEME)
        )

    companion object {
        private const val CHANNEL_KEY = "arrmada-recent"

        // Colonnes du TvProvider (noms fixes de l'API Android TV)
        private const val COLUMN_ID = "_id"
        private const val COLUMN_KEY = "internal_provider_id"

        /** Accueil Android TV avec TvProvider : TV (leanback), Android 8 ou plus. */
        fun supported(context: Context): Boolean =
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
                context.packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)
    }
}

/**
 * Affiches des cartes, rangées dans le cache de l'appli sous un nom tiré de
 * leur adresse (empreinte SHA-1, comme un cache de proxy). Téléchargées une
 * fois, avec le client HTTP de l'appli : celles du serveur ArrMada reçoivent
 * le jeton d'appareil, que le lanceur n'a pas.
 */
private class ArtCache(private val context: Context) {

    private val dir = File(context.cacheDir, HomeArtProvider.DIR).apply { mkdirs() }

    /** Adresse de l'affiche → adresse content:// lisible par le lanceur (absentes si échec). */
    fun fetch(urls: List<String>): Map<String, String> {
        val http = (context.applicationContext as ArrMadaApplication).api.http
        return urls.distinct().mapNotNull { url ->
            val name = sha1(url) + ".img"
            val file = File(dir, name)
            if (!file.exists()) {
                // Taille d'affiche TMDB raisonnable pour une carte (pas l'original de 2 000 px)
                val source = ImageSizes.tmdb(url, 400) ?: url
                val ok = runCatching {
                    http.newCall(Request.Builder().url(source).build()).execute().use { response ->
                        if (!response.isSuccessful) return@use false
                        val tmp = File(dir, "$name.part")
                        tmp.outputStream().use { out -> response.body?.byteStream()?.copyTo(out) }
                        tmp.renameTo(file)
                    }
                }.getOrDefault(false)
                if (!ok) return@mapNotNull null
            }
            url to HomeArtProvider.uri(context, name).toString()
        }.toMap()
    }

    /** Supprime les affiches qui ne servent plus à aucune carte. */
    fun keepOnly(used: Set<String>) {
        val names = used.map { Uri.parse(it).lastPathSegment }.toSet()
        dir.listFiles()?.filter { it.name !in names }?.forEach { it.delete() }
    }

    private fun sha1(text: String): String =
        MessageDigest.getInstance("SHA-1").digest(text.toByteArray()).joinToString("") { "%02x".format(it) }
}

/**
 * Sert les affiches du cache au lanceur Android TV (qui ne peut pas lire les
 * fichiers privés de l'appli). Lecture seule, uniquement les fichiers du
 * dossier des affiches au nom « empreinte.img » : rien d'autre n'est exposé.
 */
class HomeArtProvider : ContentProvider() {

    override fun onCreate(): Boolean = true

    override fun openFile(uri: Uri, mode: String): ParcelFileDescriptor {
        if (mode != "r") throw SecurityException("Lecture seule")
        val name = uri.lastPathSegment?.takeIf { NAME.matches(it) } ?: throw FileNotFoundException(uri.toString())
        val file = File(File(context!!.cacheDir, DIR), name)
        if (!file.isFile) throw FileNotFoundException(uri.toString())
        return ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_ONLY)
    }

    override fun getType(uri: Uri): String = "image/jpeg"

    override fun query(uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?, sortOrder: String?): Cursor? = null
    override fun insert(uri: Uri, values: ContentValues?): Uri? = null
    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0
    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0

    companion object {
        const val DIR = "home-art"
        private val NAME = Regex("[0-9a-f]{40}\\.img")

        /** content://<appli>.homeart/<nom> (l'appli de test a son propre nom : fr.arrmada.app.debug). */
        fun uri(context: Context, name: String): Uri = Uri.parse("content://${context.packageName}.homeart/$name")
    }
}

/**
 * Mise à jour des rangées en tâche de fond (WorkManager : une « crontab »
 * Android qui survit aux redémarrages de la TV) : toutes les 30 minutes, et
 * juste après qu'on quitte l'appli (pour qu'« À suivre » montre le film qu'on
 * vient d'arrêter).
 */
class HomeRowsWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val app = applicationContext as ArrMadaApplication
        if (!TvHomeRows.supported(app)) return Result.success()
        val rows = TvHomeRows(app)
        if (!app.prefs.homeRows || !app.prefs.paired.value) {
            rows.clear()
            return Result.success()
        }
        val repository = app.repository
        runCatching {
            val states = repository.watchStates()
            val movies = repository.allLibrary("movie")
            val series = repository.allLibrary("series")
            val resume = repository.resumeRow(states, movies, series).map { it.state to it.item }
            val recent = runCatching { repository.recent() }.getOrDefault(emptyList())
            rows.sync(
                HomeRowsLogic.resumeCards(resume, app.api::absolute),
                HomeRowsLogic.recentCards(recent, app.api::absolute),
            )
        }.onFailure { Log.w(TAG, "Synchro des rangées", it) } // serveur injoignable : la prochaine passe réessaiera
        return Result.success()
    }

    companion object {
        private const val PERIODIC = "home-rows"
        private const val NOW = "home-rows-now"
        private val network = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        /** Passe toutes les 30 minutes (posée une fois ; KEEP : un relancement de l'appli ne la décale pas). */
        fun schedule(context: Context) {
            if (!TvHomeRows.supported(context)) return
            val request = PeriodicWorkRequestBuilder<HomeRowsWorker>(30, TimeUnit.MINUTES).setConstraints(network).build()
            WorkManager.getInstance(context).enqueueUniqueWork(NOW, ExistingWorkPolicy.KEEP, OneTimeWorkRequestBuilder<HomeRowsWorker>().setConstraints(network).build())
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.KEEP, request)
        }

        /** Passe dans quelques secondes (position de lecture enregistrée entre-temps). */
        fun syncSoon(context: Context) {
            if (!TvHomeRows.supported(context)) return
            val request = OneTimeWorkRequestBuilder<HomeRowsWorker>()
                .setInitialDelay(5, TimeUnit.SECONDS)
                .setConstraints(network)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(NOW, ExistingWorkPolicy.REPLACE, request)
        }
    }
}
