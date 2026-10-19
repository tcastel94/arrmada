package fr.arrmada.app.data

import java.net.URI
import java.net.URISyntaxException

/**
 * Règles sur l'adresse du serveur ArrMada.
 *
 * Code volontairement « pur » (aucune dépendance Android) : il est testé sur
 * n'importe quelle machine par ServerUrlTest, sans téléphone ni émulateur.
 */
object ServerUrl {

    /**
     * Nettoie une adresse saisie à la télécommande ou au clavier.
     *
     *  - « 192.168.1.10:3000 »        → « http://192.168.1.10:3000 » (http par défaut)
     *  - « http://Tower:3000/ »       → « http://tower:3000 » (casse, / final)
     *  - « https://h/arrmada/?x=1 »   → « https://h/arrmada » (chemin gardé pour un
     *                                    reverse proxy ; paramètres retirés)
     *
     * Renvoie null si l'adresse est inutilisable (vide, autre protocole que
     * http/https, sans nom d'hôte, port hors 1-65535, caractères invalides).
     */
    fun normalize(input: String): String? {
        var text = input.trim()
        if (text.isEmpty()) return null
        if (!text.contains("://")) text = "http://$text"

        val uri = try {
            URI(text)
        } catch (e: URISyntaxException) {
            return null
        }

        val scheme = uri.scheme?.lowercase() ?: return null
        if (scheme != "http" && scheme != "https") return null

        // host est null quand l'adresse ne se lit pas comme hôte[:port]
        // (ex. « http://h:abc »).
        val host = uri.host?.lowercase()?.takeIf { it.isNotBlank() } ?: return null

        val port = when {
            uri.port == -1 -> ""
            uri.port in 1..65535 -> ":${uri.port}"
            else -> return null
        }
        val path = (uri.rawPath ?: "").trimEnd('/')
        return "$scheme://$host$port$path"
    }

    /**
     * Origine (protocole + hôte + port) d'une adresse déjà normalisée :
     * « http://192.168.1.10:3000/x » → « http://192.168.1.10:3000 ».
     * C'est la règle que WebView attend pour injecter un script dans les pages.
     */
    fun origin(url: String): String {
        val uri = URI(url)
        val port = if (uri.port == -1) "" else ":${uri.port}"
        return "${uri.scheme}://${uri.host}$port"
    }

    /**
     * Vrai si [other] pointe sur la même machine que le serveur, quel que soit
     * le port : l'interface (3000) et l'API (8420) restent dans l'appli, un
     * lien vers TMDB ou YouTube part dans le navigateur.
     */
    fun sameHost(serverUrl: String, other: String): Boolean {
        return try {
            val serverHost = URI(serverUrl).host ?: return false
            val otherHost = URI(other).host ?: return false
            serverHost.equals(otherHost, ignoreCase = true)
        } catch (e: URISyntaxException) {
            false
        }
    }
}
