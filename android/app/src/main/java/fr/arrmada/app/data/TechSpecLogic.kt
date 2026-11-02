package fr.arrmada.app.data

import java.util.Locale

/**
 * Carte « technique » de la fiche film : trois lignes lisibles (Vidéo,
 * Audio, Sous-titres) au lieu d'une file de pastilles, comme la fiche
 * d'Infuse. Tout vient de l'analyse du fichier par Radarr (mediaInfo).
 * Une ligne sans information n'est pas affichée.
 */
object TechSpecLogic {

    data class Line(val label: String, val value: String)

    fun lines(file: FileInfo?): List<Line> {
        if (file == null) return emptyList()
        return listOfNotNull(
            line("Vidéo", listOfNotNull(resolution(file), dynamicRange(file), videoCodec(file.videoCodec))),
            line("Audio", listOfNotNull(audioCodec(file.audioCodec), channels(file.audioChannels), languages(file.audioLanguages))),
            line("Sous-titres", listOfNotNull(languages(file.subtitleLanguages))),
        )
    }

    private fun line(label: String, parts: List<String>): Line? =
        parts.filter { it.isNotBlank() }.takeIf { it.isNotEmpty() }?.let { Line(label, it.joinToString(" · ")) }

    /** « 2160p », « 1080p »… d'après la hauteur de l'image, sinon le nom de la qualité. */
    private fun resolution(file: FileInfo): String? {
        val height = file.height
        val quality = file.quality.orEmpty()
        return when {
            height != null && height >= 2000 -> "2160p"
            height != null && height >= 1000 -> "1080p"
            height != null && height > 0 -> "${height}p"
            "2160" in quality -> "2160p"
            "1080" in quality -> "1080p"
            "720" in quality -> "720p"
            else -> null
        }
    }

    private fun dynamicRange(file: FileInfo): String? {
        val hdr = (file.dynamicRangeType ?: file.dynamicRange).orEmpty()
        return when {
            "DV" in hdr -> "Dolby Vision"
            "HDR10+" in hdr || "HDR10Plus" in hdr -> "HDR10+"
            "HLG" in hdr -> "HLG"
            "HDR" in hdr -> "HDR10"
            else -> null
        }
    }

    /** Codecs vidéo sous leur nom courant (x265 et h265 sont du HEVC…). */
    private fun videoCodec(raw: String?): String? {
        val codec = raw?.trim().orEmpty()
        val lower = codec.lowercase(Locale.ROOT)
        return when {
            codec.isEmpty() -> null
            lower in setOf("x265", "h265", "h.265", "hevc") -> "HEVC"
            lower in setOf("x264", "h264", "h.264", "avc") -> "H.264"
            lower == "av1" -> "AV1"
            lower == "vc1" || lower == "vc-1" -> "VC-1"
            else -> codec
        }
    }

    /** Codecs audio sous leur nom commercial (EAC3 = Dolby Digital Plus…). */
    private fun audioCodec(raw: String?): String? {
        val codec = raw?.trim().orEmpty()
        if (codec.isEmpty()) return null
        val atmos = "atmos" in codec.lowercase(Locale.ROOT)
        val base = codec.replace("Atmos", "", ignoreCase = true).trim()
        val name = when (base.uppercase(Locale.ROOT)) {
            "EAC3", "E-AC-3", "DDP" -> "Dolby Digital Plus"
            "AC3", "AC-3", "DD" -> "Dolby Digital"
            "TRUEHD" -> "TrueHD"
            "DTS-HD MA" -> "DTS-HD MA"
            "DTS-X", "DTS:X" -> "DTS:X"
            "" -> null
            else -> base
        }
        return listOfNotNull(name, "Atmos".takeIf { atmos }).joinToString(" ").ifBlank { null }
    }

    /** 7.1, 5.1, Stéréo, Mono. */
    private fun channels(value: Double?): String? = when {
        value == null || value <= 0.0 -> null
        value < 1.5 -> "Mono"
        value < 2.5 -> "Stéréo"
        else -> "%.1f".format(Locale.ROOT, value)
    }

    /** « French / English » ou « fre/eng » → « Français, Anglais » (sans doublon). */
    fun languages(raw: String?): String? {
        if (raw.isNullOrBlank()) return null
        val names = raw.split("/", ",")
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .map { LANGUAGES[it.lowercase(Locale.ROOT)] ?: it.replaceFirstChar { c -> c.titlecase(Locale.FRANCE) } }
            .distinct()
        return names.joinToString(", ").ifBlank { null }
    }

    private val LANGUAGES = mapOf(
        "french" to "Français", "fre" to "Français", "fra" to "Français", "fr" to "Français",
        "english" to "Anglais", "eng" to "Anglais", "en" to "Anglais",
        "german" to "Allemand", "ger" to "Allemand", "deu" to "Allemand", "de" to "Allemand",
        "spanish" to "Espagnol", "spa" to "Espagnol", "es" to "Espagnol",
        "italian" to "Italien", "ita" to "Italien", "it" to "Italien",
        "japanese" to "Japonais", "jpn" to "Japonais", "ja" to "Japonais",
        "korean" to "Coréen", "kor" to "Coréen", "ko" to "Coréen",
        "chinese" to "Chinois", "chi" to "Chinois", "zho" to "Chinois", "zh" to "Chinois",
        "portuguese" to "Portugais", "por" to "Portugais", "pt" to "Portugais",
        "dutch" to "Néerlandais", "dut" to "Néerlandais", "nld" to "Néerlandais", "nl" to "Néerlandais",
        "russian" to "Russe", "rus" to "Russe", "ru" to "Russe",
    )
}
