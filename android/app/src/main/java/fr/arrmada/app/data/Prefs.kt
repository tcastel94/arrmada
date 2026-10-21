package fr.arrmada.app.data

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * Réglages de l'appli, stockés dans les « SharedPreferences » d'Android :
 * un petit fichier clé=valeur privé à l'appli (l'équivalent d'un .conf).
 *
 * Le jeton d'appareil est lié à l'adresse du serveur, comme dans l'add-on
 * (device.json) : changer de serveur oublie le jeton.
 */
class Prefs(context: Context) {

    private val prefs = context.getSharedPreferences("arrmada", Context.MODE_PRIVATE)

    private val _paired = MutableStateFlow(prefs.getString(KEY_TOKEN, null) != null)

    /** Vrai tant que la TV a un jeton ; repasse à faux si le serveur la révoque (401). */
    val paired: StateFlow<Boolean> = _paired

    /** Adresse de l'API ArrMada (ex. http://192.168.1.10:8420), ou null. */
    var serverUrl: String?
        get() = prefs.getString(KEY_URL, null)?.takeIf { it.isNotBlank() }
        set(value) {
            if (value != serverUrl) {
                prefs.edit().putString(KEY_URL, value).remove(KEY_TOKEN).remove(KEY_DEVICE).apply()
                _paired.value = false
            }
        }

    /** Jeton remis par le serveur à l'appairage (en-tête X-Device-Token). */
    var token: String?
        get() = prefs.getString(KEY_TOKEN, null)?.takeIf { it.isNotBlank() }
        set(value) {
            prefs.edit().putString(KEY_TOKEN, value).apply()
            _paired.value = value != null
        }

    /** Nom de l'appareil choisi dans la web app (« Shield Salon »). */
    var deviceName: String?
        get() = prefs.getString(KEY_DEVICE, null)
        set(value) = prefs.edit().putString(KEY_DEVICE, value).apply()

    /** Décodage auto : l'ampli prend le programme conseillé pour le son du film. */
    var autoSound: Boolean
        get() = prefs.getBoolean(KEY_AUTO_SOUND, true)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_SOUND, value).apply()

    fun forgetPairing() {
        prefs.edit().remove(KEY_TOKEN).remove(KEY_DEVICE).apply()
        _paired.value = false
    }

    private companion object {
        const val KEY_URL = "server_url"
        const val KEY_TOKEN = "device_token"
        const val KEY_DEVICE = "device_name"
        const val KEY_AUTO_SOUND = "auto_sound"
    }
}
