package fr.arrmada.app.data

import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeParseException

/**
 * Mise en forme à la française, reprise de l'add-on (home_data.py) : mêmes
 * libellés sur la TV, la web app et l'appli.
 */
object Fr {
    private const val NBSP = ' '

    /** 3412 → « 3 412 » (espace insécable). */
    fun int(value: Int): String =
        value.toString().reversed().chunked(3).joinToString(NBSP.toString()).reversed()

    /** « 1 film », « 2 films », « 0 film » (0 et 1 au singulier). */
    fun plural(n: Int, singular: String, pluralForm: String = singular + "s"): String =
        "${int(n)} ${if (n <= 1) singular else pluralForm}"

    /** 42.13 → « 42,1 ». */
    fun decimal(value: Double, decimals: Int = 1): String =
        "%.${decimals}f".format(java.util.Locale.ROOT, value).replace('.', ',')

    /** Octets → « 12,3 To » (unités françaises, comme le serveur). */
    fun bytes(value: Double): String {
        var num = value
        for (unit in listOf("o", "Ko", "Mo", "Go", "To", "Po")) {
            if (kotlin.math.abs(num) < 1024 || unit == "Po") {
                val text = if (unit == "o" || unit == "Ko") "%.0f".format(java.util.Locale.ROOT, num) else decimal(num)
                return "$text$NBSP$unit"
            }
            num /= 1024
        }
        return ""
    }

    private val TIMESPAN = Regex("""^(?:(\d+)\.)?(\d{1,2}):(\d{2}):(\d{2})""")

    /** Temps restant de *arr (« 01:02:03 », « 1.02:03:04 ») → « 1 h 02 », « 10 min », « < 1 min ». */
    fun timeLeft(raw: String?): String {
        if (raw.isNullOrBlank()) return ""
        val m = TIMESPAN.find(raw) ?: return raw
        val hours = m.groupValues[2].toInt() + (m.groupValues[1].toIntOrNull() ?: 0) * 24
        val minutes = m.groupValues[3].toInt()
        return when {
            hours > 0 -> "$hours h ${"%02d".format(minutes)}"
            minutes > 0 -> "$minutes min"
            else -> "< 1 min"
        }
    }

    /** « 2026-10-17T20:41:05+00:00 » → heure locale ; illisible → null. */
    fun parseIso(value: String?, zone: ZoneId = ZoneId.systemDefault()): LocalDateTime? {
        if (value.isNullOrBlank()) return null
        return try {
            OffsetDateTime.parse(value.replace("Z", "+00:00")).atZoneSameInstant(zone).toLocalDateTime()
        } catch (_: DateTimeParseException) {
            try {
                LocalDateTime.parse(value)
            } catch (_: DateTimeParseException) {
                null
            }
        }
    }

    /** « à l'instant », « il y a 4 min », « il y a 2 h », sinon « à 19:02 ». */
    fun ago(value: String?, now: LocalDateTime, zone: ZoneId = ZoneId.systemDefault()): String {
        val moment = parseIso(value, zone) ?: return ""
        val minutes = java.time.Duration.between(moment, now).toMinutes()
        return when {
            minutes < 1 -> "à l’instant"
            minutes < 60 -> "il y a $minutes min"
            minutes < 6 * 60 -> "il y a ${minutes / 60} h"
            else -> "à %02d:%02d".format(moment.hour, moment.minute)
        }
    }

    /** Salutation selon l'heure. */
    fun greeting(hour: Int): String = when {
        hour < 5 -> "Bonne nuit"
        hour < 12 -> "Bonjour"
        hour < 18 -> "Bon après-midi"
        else -> "Bonsoir"
    }
}
