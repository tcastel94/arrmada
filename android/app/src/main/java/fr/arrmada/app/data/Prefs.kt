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

    /**
     * Profil famille qui regarde (ADR-008), envoyé au serveur à chaque appel
     * (en-tête X-Profile-Id). null : profil « Famille », celui des TV sous Kodi.
     */
    private val _profile = MutableStateFlow(readProfile())
    val profile: StateFlow<FamilyProfile?> = _profile

    val profileId: Int? get() = _profile.value?.id

    fun setProfile(profile: FamilyProfile?) {
        val chosen = profile?.takeIf { !it.isDefault }
        prefs.edit().apply {
            if (chosen == null) {
                remove(KEY_PROFILE_ID).remove(KEY_PROFILE_NAME).remove(KEY_PROFILE_COLOR).remove(KEY_PROFILE_EMOJI)
            } else {
                putInt(KEY_PROFILE_ID, chosen.id).putString(KEY_PROFILE_NAME, chosen.name)
                    .putString(KEY_PROFILE_COLOR, chosen.color).putString(KEY_PROFILE_EMOJI, chosen.emoji)
            }
        }.apply()
        _profile.value = chosen
    }

    private fun readProfile(): FamilyProfile? {
        val id = prefs.getInt(KEY_PROFILE_ID, 0).takeIf { it > 0 } ?: return null
        return FamilyProfile(
            id = id,
            name = prefs.getString(KEY_PROFILE_NAME, null).orEmpty(),
            color = prefs.getString(KEY_PROFILE_COLOR, null) ?: "#4A9EFF",
            emoji = prefs.getString(KEY_PROFILE_EMOJI, null).orEmpty(),
        )
    }

    /** Décodage auto : l'ampli prend le programme conseillé pour le son du film. */
    var autoSound: Boolean
        get() = prefs.getBoolean(KEY_AUTO_SOUND, true)
        set(value) = prefs.edit().putBoolean(KEY_AUTO_SOUND, value).apply()

    /** Rangées « À suivre » et chaîne ArrMada sur l'accueil Android TV (Réglages). */
    var homeRows: Boolean
        get() = prefs.getBoolean(KEY_HOME_ROWS, true)
        set(value) = prefs.edit().putBoolean(KEY_HOME_ROWS, value).apply()

    /**
     * Qualité de lecture par défaut de cette TV (ADR-012) : l'original, ou
     * d'emblée le 1080p converti par Jellyfin (TV en Wi-Fi, câble lent).
     */
    var defaultQuality: DefaultQuality
        get() = prefs.getString(KEY_DEFAULT_QUALITY, null)
            ?.let { saved -> DefaultQuality.entries.firstOrNull { it.name == saved } } ?: DefaultQuality.ORIGINAL
        set(value) = prefs.edit().putString(KEY_DEFAULT_QUALITY, value.name).apply()

    /** « Toujours lire en 1080p sur cette TV ? » déjà posée (une seule fois). */
    var qualityAsked: Boolean
        get() = prefs.getBoolean(KEY_QUALITY_ASKED, false)
        set(value) = prefs.edit().putBoolean(KEY_QUALITY_ASKED, value).apply()

    fun forgetPairing() {
        setProfile(null) // autre maison, autres profils
        prefs.edit().remove(KEY_TOKEN).remove(KEY_DEVICE).apply()
        _paired.value = false
    }

    private companion object {
        const val KEY_URL = "server_url"
        const val KEY_TOKEN = "device_token"
        const val KEY_DEVICE = "device_name"
        const val KEY_AUTO_SOUND = "auto_sound"
        const val KEY_HOME_ROWS = "home_rows"
        const val KEY_DEFAULT_QUALITY = "default_quality"
        const val KEY_QUALITY_ASKED = "quality_asked"
        const val KEY_PROFILE_ID = "profile_id"
        const val KEY_PROFILE_NAME = "profile_name"
        const val KEY_PROFILE_COLOR = "profile_color"
        const val KEY_PROFILE_EMOJI = "profile_emoji"
    }
}
