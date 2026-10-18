package fr.arrmada.app

import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException
import javax.net.ssl.SSLException

/**
 * Test de connexion lancé par l'écran de connexion avant d'enregistrer
 * l'adresse : équivalent d'un « curl -m 5 <url> | grep -i arrmada ».
 *
 * À appeler hors du fil principal (Android interdit le réseau sur le fil qui
 * dessine l'écran, l'appli planterait avec NetworkOnMainThreadException).
 */
object ServerProbe {

    enum class Outcome { OK, NOT_ARRMADA, HTTP_ERROR, UNKNOWN_HOST, TIMEOUT, SSL, UNREACHABLE }

    data class Result(val outcome: Outcome, val detail: String = "")

    private const val TIMEOUT_MS = 5_000

    // On lit au plus 64 Ko : le <title>ArrMada…</title> est dans l'en-tête de la page.
    private const val MAX_BYTES = 64 * 1024

    fun check(url: String): Result {
        var connection: HttpURLConnection? = null
        return try {
            val conn = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                instanceFollowRedirects = true // « / » redirige vers « /login »
                setRequestProperty("User-Agent", "ArrMadaAndroid-probe")
            }
            connection = conn
            val code = conn.responseCode
            if (code >= 400) return Result(Outcome.HTTP_ERROR, code.toString())

            val head = conn.inputStream.use { stream ->
                val buffer = ByteArray(MAX_BYTES)
                var total = 0
                while (total < buffer.size) {
                    val read = stream.read(buffer, total, buffer.size - total)
                    if (read < 0) break
                    total += read
                }
                String(buffer, 0, total, Charsets.UTF_8)
            }
            if (head.contains("ArrMada", ignoreCase = true)) Result(Outcome.OK)
            else Result(Outcome.NOT_ARRMADA)
        } catch (e: UnknownHostException) {
            Result(Outcome.UNKNOWN_HOST, e.message ?: url)
        } catch (e: SocketTimeoutException) {
            Result(Outcome.TIMEOUT)
        } catch (e: SSLException) {
            Result(Outcome.SSL, e.message ?: "")
        } catch (e: IOException) {
            // Connexion refusée (mauvais port, conteneur arrêté), réseau absent…
            Result(Outcome.UNREACHABLE, e.message ?: e.javaClass.simpleName)
        } finally {
            connection?.disconnect()
        }
    }
}
