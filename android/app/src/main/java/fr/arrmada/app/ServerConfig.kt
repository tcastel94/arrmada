package fr.arrmada.app

import android.app.UiModeManager
import android.content.Context
import android.content.pm.PackageManager
import android.content.res.Configuration

/**
 * Réglages de l'appli, stockés dans les « SharedPreferences » d'Android :
 * un petit fichier clé=valeur privé à l'appli (l'équivalent d'un .conf).
 */
object ServerConfig {

    private const val PREFS = "arrmada"
    private const val KEY_URL = "server_url"
    private const val KEY_TV_WIDTH = "tv_viewport_width"

    // Largeur de mise en page de la web app sur TV, en pixels CSS. Une TV
    // 1080p se présente comme un écran de 960 px de large : la web app s'y
    // affiche en mode « tablette », gros mais serré. 1280 donne la mise en
    // page « ordinateur portable », lisible depuis le canapé.
    const val TV_WIDTH_LARGE = 960
    const val TV_WIDTH_NORMAL = 1280
    const val TV_WIDTH_COMPACT = 1600

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Adresse du serveur, ou null tant que l'écran de connexion n'a pas été rempli. */
    fun url(context: Context): String? =
        prefs(context).getString(KEY_URL, null)?.takeIf { it.isNotBlank() }

    fun tvWidth(context: Context): Int =
        prefs(context).getInt(KEY_TV_WIDTH, TV_WIDTH_NORMAL)

    fun save(context: Context, url: String, tvWidth: Int) {
        prefs(context).edit()
            .putString(KEY_URL, url)
            .putInt(KEY_TV_WIDTH, tvWidth)
            .apply()
    }

    /**
     * Vrai sur Android TV (Shield, Chromecast avec Google TV…). Deux tests,
     * car certains boîtiers ne déclarent que l'un des deux.
     */
    fun isTv(context: Context): Boolean {
        val uiMode = context.getSystemService(UiModeManager::class.java)
        return uiMode?.currentModeType == Configuration.UI_MODE_TYPE_TELEVISION ||
            context.packageManager.hasSystemFeature(PackageManager.FEATURE_LEANBACK)
    }
}
