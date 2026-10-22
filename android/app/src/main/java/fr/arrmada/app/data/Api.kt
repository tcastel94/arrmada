package fr.arrmada.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Erreur d'appel à l'API, avec un message prêt à afficher. */
class ApiException(val code: Int, message: String) : IOException(message)

/**
 * Client de l'API ArrMada.
 *
 * Analogie : un `curl` préconfiguré. Chaque requête part vers l'adresse du
 * serveur avec l'en-tête `X-Device-Token` (jeton remis à l'appairage). Les
 * appels réseau tournent sur un fil d'arrière-plan (Dispatchers.IO) : l'écran
 * ne se fige jamais pendant une requête.
 */
class Api(private val prefs: Prefs) {

    /** Lecture tolérante du JSON : champs inconnus ignorés, nulls acceptés. */
    val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false // champ null : ni attendu en lecture, ni envoyé en écriture
        encodeDefaults = true // valeurs par défaut envoyées (ex. media_type = "episode")
        isLenient = true
    }

    /**
     * Client HTTP partagé (connexions réutilisées) par l'API, les images et
     * le lecteur vidéo. Le jeton n'est ajouté que vers le serveur ArrMada :
     * jamais vers TMDB ou un autre site.
     */
    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .addInterceptor(Interceptor { chain ->
            val request = chain.request()
            val server = prefs.serverUrl
            val token = prefs.token
            val sameServer = server != null && ServerUrl.sameHost(server, request.url.toString())
            chain.proceed(
                if (sameServer && token != null) {
                    request.newBuilder()
                        .header("X-Device-Token", token)
                        // Profil qui regarde (ADR-008) : sans en-tête, « Famille »
                        .apply { prefs.profileId?.let { header("X-Profile-Id", it.toString()) } }
                        .build()
                } else {
                    request
                }
            )
        })
        .build()

    val baseUrl: String get() = prefs.serverUrl ?: error("Adresse du serveur non configurée")

    /** Adresse absolue : « /api/… » est préfixé par l'adresse du serveur. */
    fun absolute(url: String?): String? = when {
        url.isNullOrBlank() -> null
        url.startsWith("http://") || url.startsWith("https://") -> url
        // Chemin relatif d'une image ArrMada ; les autres (chemins Radarr
        // « /MediaCover/… ») ne sont pas joignables depuis la TV.
        url.startsWith("/api/") -> baseUrl + url
        else -> null
    }

    suspend inline fun <reified T> get(path: String, slow: Boolean = false): T =
        decode(call(Request.Builder().url(baseUrl + path).get().build(), if (slow) slowHttp else http))

    suspend inline fun <reified T, reified B> post(path: String, body: B, slow: Boolean = false): T {
        val payload = json.encodeToString(kotlinx.serialization.serializer<B>(), body)
        val request = Request.Builder()
            .url(baseUrl + path)
            .post(payload.toRequestBody(JSON))
            .build()
        return decode(call(request, if (slow) slowHttp else http))
    }

    /**
     * Même client, avec un délai de réponse de 45 s : pour les actions que le
     * serveur met longtemps à finir (« Débloquer » relance Radarr / Sonarr).
     */
    val slowHttp: OkHttpClient by lazy { http.newBuilder().readTimeout(45, TimeUnit.SECONDS).build() }

    inline fun <reified T> decode(text: String): T =
        json.decodeFromString(kotlinx.serialization.serializer<T>(), text)

    /** Exécute la requête hors du fil de l'écran ; renvoie le corps de la réponse. */
    suspend fun call(request: Request, client: OkHttpClient = http): String = withContext(Dispatchers.IO) {
        client.newCall(request).execute().use { response ->
            val text = response.body?.string().orEmpty()
            if (!response.isSuccessful) {
                if (response.code == 401) prefs.forgetPairing() // TV révoquée dans la web app
                throw ApiException(response.code, serverMessage(response.code, text) ?: messageFor(response.code))
            }
            text
        }
    }

    /**
     * Message lisible renvoyé par le serveur (« detail » de FastAPI), pour
     * les refus métier (409 « Pas dans la file SABnzbd… », 403…).
     */
    private fun serverMessage(code: Int, body: String): String? {
        if (code == 401 || code >= 500) return null
        return runCatching {
            val detail = json.parseToJsonElement(body).let { (it as? kotlinx.serialization.json.JsonObject)?.get("detail") }
            (detail as? kotlinx.serialization.json.JsonPrimitive)?.takeIf { it.isString }?.content
        }.getOrNull()?.takeIf { it.isNotBlank() }
    }

    private fun messageFor(code: Int): String = when (code) {
        401 -> "Cette TV n’est plus appairée : relance l’appairage."
        403 -> "Accès refusé par le serveur (réseau local uniquement)."
        404 -> "Introuvable sur le serveur."
        in 500..599 -> "Le serveur ArrMada a rencontré une erreur ($code)."
        else -> "Erreur HTTP $code."
    }

    companion object {
        val JSON = "application/json; charset=utf-8".toMediaType()
    }
}
