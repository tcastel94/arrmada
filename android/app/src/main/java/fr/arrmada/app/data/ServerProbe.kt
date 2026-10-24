package fr.arrmada.app.data

import java.io.IOException
import java.net.HttpURLConnection
import java.net.SocketTimeoutException
import java.net.URL
import java.net.UnknownHostException
import javax.net.ssl.SSLException

/**
 * Test de l'adresse saisie avant de l'enregistrer : équivalent d'un
 * « curl -m 5 <adresse>/api/health | grep arrmada ».
 *
 * À appeler hors du fil principal (Android interdit le réseau sur le fil qui
 * dessine l'écran : l'appli planterait avec NetworkOnMainThreadException).
 */
object ServerProbe {

    enum class Outcome { OK, NOT_ARRMADA, HTTP_ERROR, UNKNOWN_HOST, TIMEOUT, SSL, UNREACHABLE }

    data class Result(val outcome: Outcome, val detail: String = "")

    private const val TIMEOUT_MS = 5_000
    private const val MAX_BYTES = 4 * 1024

    fun check(baseUrl: String): Result {
        var connection: HttpURLConnection? = null
        return try {
            val conn = (URL("$baseUrl/api/health").openConnection() as HttpURLConnection).apply {
                connectTimeout = TIMEOUT_MS
                readTimeout = TIMEOUT_MS
                setRequestProperty("User-Agent", "ArrMada-Android")
            }
            connection = conn
            val code = conn.responseCode
            // 404 : quelque chose répond, mais pas l'API ArrMada (port de la web app ?)
            if (code == 404) return Result(Outcome.NOT_ARRMADA)
            if (code >= 400) return Result(Outcome.HTTP_ERROR, code.toString())

            val body = conn.inputStream.use { stream ->
                val buffer = ByteArray(MAX_BYTES)
                var total = 0
                while (total < buffer.size) {
                    val read = stream.read(buffer, total, buffer.size - total)
                    if (read < 0) break
                    total += read
                }
                String(buffer, 0, total, Charsets.UTF_8)
            }
            // Réponse attendue : {"status":"ok","service":"arrmada","version":"…"}
            if (body.contains("arrmada", ignoreCase = true)) Result(Outcome.OK)
            else Result(Outcome.NOT_ARRMADA)
        } catch (e: UnknownHostException) {
            Result(Outcome.UNKNOWN_HOST, e.message ?: baseUrl)
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
