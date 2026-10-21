package fr.arrmada.app.data

import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.doubleOrNull
import java.time.Duration
import java.time.LocalDateTime
import java.time.ZoneId

/**
 * Événements du serveur (imports, « Prêt à regarder », caméra…) : ce que la
 * TV en affiche. Mêmes règles que l'add-on (feeds.py, remote_data.py).
 *
 * La TV interroge `/api/events/recent?since_id=N` toutes les 5 s, comme un
 * `tail -f` qui retiendrait la dernière ligne lue : seul ce qui est arrivé
 * depuis est renvoyé.
 */
object EventLogic {

    /** Bulle en bas à droite de l'écran. */
    data class Bubble(
        val heading: String,
        val message: String,
        val icon: String? = null,
        val error: Boolean = false,
        val title: String = message, // nom court repris dans un résumé
    )

    /** Au-delà, une seule bulle de résumé plutôt qu'une rafale. */
    const val MAX_SEPARATE = 2

    /** Une annonce vise une TV pendant 2 min (horloges décalées d'une minute tolérées). */
    private const val MAX_AGE_SECONDS = 120L
    private const val CLOCK_SKEW_SECONDS = 60L

    /**
     * Curseur de lecture des événements. Premier passage : on note la
     * position sans rien afficher (pas de rafale d'anciennes nouvelles au
     * démarrage). Serveur redémarré (`boot_id` change) : on relit depuis 0.
     */
    class Cursor {
        var sinceId: Long = 0
            private set
        private var bootId: String? = null

        /** Événements à traiter dans cette page (vide au premier passage). */
        fun accept(page: EventsPage): List<ServerEvent> {
            val first = bootId == null
            val restarted = !first && page.bootId.isNotEmpty() && page.bootId != bootId
            bootId = page.bootId
            if (restarted) {
                // Les numéros repartent de 1 : tout ce que renvoie le serveur est neuf
                sinceId = page.lastId
                return page.events
            }
            sinceId = maxOf(sinceId, page.lastId)
            return if (first) emptyList() else page.events
        }
    }

    private fun sizeLabel(raw: JsonPrimitive?): String {
        val value = raw?.doubleOrNull ?: return ""
        if (value <= 0) return ""
        var v = value
        for (unit in listOf("o", "Ko", "Mo", "Go", "To")) {
            if (v < 1024 || unit == "To") {
                return if (v >= 10 || unit == "o" || unit == "Ko") "%.0f $unit".format(java.util.Locale.ROOT, v)
                else Fr.decimal(v) + " " + unit
            }
            v /= 1024
        }
        return ""
    }

    private fun details(vararg parts: String) = parts.map { it.trim() }.filter { it.isNotEmpty() }.joinToString(" · ")

    /** Bulle d'un événement, ou null s'il ne s'affiche pas. */
    fun bubble(event: ServerEvent): Bubble? {
        val title = event.text("title").trim()
        val kind = event.text("event")
        val quality = event.text("quality").trim()
        val poster = event.text("poster").takeIf { it.startsWith("http://") || it.startsWith("https://") }
        val episodeTitle = event.text("episode_title").trim()
        val size = sizeLabel(event.data["size"] as? JsonPrimitive)
        return when (event.type) {
            "new_import" -> when {
                title.isEmpty() -> null
                kind == "MovieAdded" || kind == "SeriesAdd" -> {
                    val year = (event.data["year"] as? JsonPrimitive)?.intOrNull
                    val label = if (year != null && year > 0) "$title ($year)" else title
                    Bubble("Nouveau titre suivi", details(label, if (kind == "MovieAdded") "Radarr" else "Sonarr"), poster, title = title)
                }
                else -> {
                    val upgrade = (event.data["upgrade"] as? JsonPrimitive)?.booleanOrNull == true
                    Bubble(if (upgrade) "Mise à niveau sur le NAS" else "Importé sur le NAS", details(title, episodeTitle, quality, size), poster, title = title)
                }
            }
            "download_grab" -> if (title.isEmpty()) null else Bubble("Téléchargement lancé", details(title, episodeTitle, quality, size), poster, title = title)
            "import_blocked" -> if (title.isEmpty()) {
                null
            } else {
                val service = event.text("service").replaceFirstChar { it.uppercase() }.ifBlank { "Radarr/Sonarr" }
                Bubble("Import bloqué", "$title : à régler dans $service (web app)", poster, error = true, title = title)
            }
            "health_alert" -> Bubble("Alerte ArrMada", title.ifBlank { event.text("message").ifBlank { "Un service a un problème" } }, error = true)
            else -> null
        }
    }

    /**
     * Bulles telles quelles s'il y en a peu, sinon un résumé « 3 nouveautés
     * ArrMada ». [heading] force un résumé (« Pendant ta séance »), même pour
     * une seule bulle.
     */
    fun merge(items: List<Bubble>, heading: String? = null): List<Bubble> {
        if (items.isEmpty()) return emptyList()
        if (heading == null && items.size <= MAX_SEPARATE) return items
        if (heading != null && items.size == 1) return listOf(items[0].copy(heading = "$heading · ${items[0].heading}"))
        val titles = items.map { it.title.ifBlank { it.message } }
        val shown = titles.take(3).joinToString(", ") + if (titles.size > 3) " et ${titles.size - 3} autre(s)" else ""
        val count = items.size
        return listOf(
            Bubble(
                heading = heading ?: "$count nouveautés ArrMada",
                message = if (heading == null) shown else "$count nouveauté(s) : $shown",
                icon = items.lastOrNull { it.icon != null }?.icon,
                title = shown,
            )
        )
    }

    /** L'annonce (« Prêt à regarder », « Lire sur la TV ») vise cette TV et date de moins de 2 min. */
    fun forMe(deviceId: Int?, myId: Int, at: String, now: LocalDateTime, zone: ZoneId = ZoneId.systemDefault()): Boolean {
        if (myId <= 0 || deviceId != myId) return false
        val sent = Fr.parseIso(at, zone) ?: return false
        val age = Duration.between(sent, now).seconds
        return age in -CLOCK_SKEW_SECONDS..MAX_AGE_SECONDS
    }

    /** Ligne de détail de « Prêt à regarder » : « Bluray-2160p · sous-titres français ». */
    fun readyDetail(ready: PlayAnnounce): String =
        listOf(ready.quality.orEmpty(), BoardLogic.subtitlesLabel(ready.subtitles)).filter { it.isNotBlank() }.joinToString(" · ")

    /** Titre affiché : « Dune », « Severance S02E05 ». */
    fun readyTitle(ready: PlayAnnounce): String =
        if (ready.isEpisode && ready.season != null && ready.episode != null) {
            "%s S%02dE%02d".format(ready.title, ready.season, ready.episode)
        } else {
            ready.title
        }

    /** « Entrée · 21:42 » sous l'alerte caméra (heure de la détection, sinon de la TV). */
    fun cameraSubtitle(camera: CameraEvent, now: LocalDateTime, zone: ZoneId = ZoneId.systemDefault()): String {
        val at = Fr.parseIso(camera.at, zone) ?: now
        return details(camera.camera, "%02d:%02d".format(at.hour, at.minute))
    }

    /** Libellé d'une détection quand le serveur n'en donne pas. */
    fun cameraLabel(camera: CameraEvent): String = camera.label.ifBlank {
        when (camera.detection) {
            "person" -> "Personne détectée"
            "motion" -> "Mouvement détecté"
            "ring" -> "On sonne à la porte"
            "pet" -> "Animal détecté"
            "vehicle" -> "Véhicule détecté"
            "package" -> "Colis livré"
            else -> "Caméra"
        }
    }
}
