package fr.arrmada.app

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.intercept.Interceptor
import coil.request.ErrorResult
import coil.request.ImageResult
import coil.size.Dimension
import fr.arrmada.app.data.Api
import fr.arrmada.app.data.ImageSizes
import fr.arrmada.app.data.Prefs
import fr.arrmada.app.data.Repository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob

/**
 * Point de départ de l'appli : crée une seule fois les objets partagés
 * (réglages, client HTTP, accès à l'API). Les écrans les récupèrent ici.
 */
class ArrMadaApplication : Application(), ImageLoaderFactory {

    lateinit var prefs: Prefs
        private set
    lateinit var api: Api
        private set
    lateinit var repository: Repository
        private set

    /**
     * Tâches qui doivent aller au bout même quand l'écran qui les a lancées
     * se ferme (ex. : enregistrer la position de lecture en quittant le film).
     */
    val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    /**
     * Titre à afficher dans la feuille « Télécharger » : passé d'un écran à
     * l'autre ici plutôt que dans l'adresse de l'écran (trop de champs).
     */
    var pendingDownload: fr.arrmada.app.data.DownloadTarget? = null

    /** Événements du serveur (bulles, « Prêt à regarder », caméra), relevés toutes les 5 s. */
    val events: fr.arrmada.app.notify.EventCenter by lazy {
        fr.arrmada.app.notify.EventCenter(repository, prefs, appScope, api.json)
    }

    /** Mises à jour de l'appli proposées par le serveur (ADR-009). */
    val updates: fr.arrmada.app.update.UpdateCenter by lazy { fr.arrmada.app.update.UpdateCenter(this) }

    /** La maison a des profils famille : avatar du profil dans le menu du haut. */
    var hasProfiles = false

    /** L'intro animée ne se joue qu'une fois par lancement de l'appli (comme l'add-on). */
    var introSeen = false

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        api = Api(prefs)
        repository = Repository(api)
    }

    /**
     * Chargeur d'images (Coil) branché sur le même client HTTP que l'API :
     * les images servies par ArrMada (vignettes de chapitres, logos locaux)
     * reçoivent le jeton d'appareil, les autres (TMDB) non.
     * Les images TMDB sont demandées à la taille où elles s'affichent.
     */
    override fun newImageLoader(): ImageLoader =
        ImageLoader.Builder(this)
            .okHttpClient(api.http)
            .components { add(TmdbSizeInterceptor) }
            .crossfade(220) // fondu du skin (200 à 450 ms)
            .build()
}

/**
 * Remplace une image TMDB « taille d'origine » par la taille affichée
 * (voir [ImageSizes]). Si TMDB refuse la taille réduite, on reprend l'image
 * d'origine : jamais d'affiche manquante à cause de ce raccourci.
 */
private object TmdbSizeInterceptor : Interceptor {
    override suspend fun intercept(chain: Interceptor.Chain): ImageResult {
        val url = chain.request.data as? String ?: return chain.proceed(chain.request)
        val width = (chain.size.width as? Dimension.Pixels)?.px
        val smaller = ImageSizes.tmdb(url, width) ?: return chain.proceed(chain.request)
        val result = chain.proceed(chain.request.newBuilder().data(smaller).build())
        return if (result is ErrorResult) chain.proceed(chain.request) else result
    }
}
