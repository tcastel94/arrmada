package fr.arrmada.app.data

import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeParseException
import java.time.temporal.ChronoUnit

/**
 * Petite étiquette posée sur une carte de l'accueil, tirée des vraies
 * données (Radarr / Sonarr), comme les « n° 1 en séries » des plateformes :
 * elle dit en un coup d'œil pourquoi la carte est là.
 */
object CardTagLogic {

    /**
     * Rangée « Ajouts récents » : « Aujourd’hui », « Hier », « Il y a 3 j »
     * pendant une semaine ; plus vieux, date illisible ou future → null
     * (pas d'étiquette, la carte reste sobre).
     * [added] : « 2026-10-29T21:14:00Z » ou simplement « 2026-10-29 ».
     */
    fun added(added: String?, today: LocalDate, zone: ZoneId = ZoneId.systemDefault()): String? {
        val day = Fr.parseIso(added, zone)?.toLocalDate() ?: dateOnly(added) ?: return null
        val days = ChronoUnit.DAYS.between(day, today)
        return when {
            days < 0 -> null
            days == 0L -> "Aujourd’hui"
            days == 1L -> "Hier"
            days < 7 -> "Il y a $days j"
            else -> null
        }
    }

    private fun dateOnly(value: String?): LocalDate? {
        if (value == null || value.length < 10) return null
        return try {
            LocalDate.parse(value.take(10))
        } catch (_: DateTimeParseException) {
            null
        }
    }
}
