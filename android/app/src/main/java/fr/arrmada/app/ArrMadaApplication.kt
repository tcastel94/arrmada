package fr.arrmada.app

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import fr.arrmada.app.data.Api
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
     */
    override fun newImageLoader(): ImageLoader =
        ImageLoader.Builder(this)
            .okHttpClient(api.http)
            .crossfade(220) // fondu du skin (200 à 450 ms)
            .build()
}
